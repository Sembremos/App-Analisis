# -*- coding: utf-8 -*-
# Streamlit — 5 Formularios (5 hojas) + Visor (capas) + Gráficas — Google Sheets como DB
# TODOS los formularios arrancan con el MISMO mapa base: ESRI SATÉLITE.
# Dentro de cada formulario podés cambiar el estilo desde un selector.
#
# Requisitos: streamlit, pandas, gspread, google-auth, folium, streamlit-folium, plotly
# Secrets: st.secrets["gcp_service_account"] con el JSON del service account

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import random, re

import gspread
from google.oauth2.service_account import Credentials

import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, LocateControl, HeatMap

import plotly.express as px

# ==========================================================
# CONFIG APP
# ==========================================================
st.set_page_config(page_title="CR – 5 Formularios + Visor + Gráficas", layout="wide")
TZ = ZoneInfo("America/Costa_Rica")

# 👉 TU SHEET (ya confirmada)
SHEET_ID = "1pCUXSJ_hvQzpzBTaJ-h0ntcdhYwMTyWomxXMjmi7lyg"

# 5 hojas distintas (una por formulario)
FORM_SHEETS = {
    "Formulario 1": "Prueba_1",
    "Formulario 2": "Prueba_2",
    "Formulario 3": "Prueba_3",
    "Formulario 4": "Prueba_4",
    "Formulario 5": "Prueba_5",
}

# Encabezados (schema)
HEADERS = [
    "date", "barrio", "factores", "delitos_relacionados",
    "ligado_estructura", "nombre_estructura", "observaciones", "maps_link"
]

# FACTORES (ejemplo — podés cambiar luego)
FACTORES = [
    "Calles sin iluminación adecuada por la noche.",
    "Calles con poca visibilidad por vegetación, muros o abandono.",
    "Zonas con lotes baldíos o propiedades abandonadas.",
    "Presencia de personas desconocidas merodeando sin razón aparente.",
    "Personas consumiendo drogas o alcohol en la vía pública.",
    "Posible venta de drogas en sitios privados (alerta comunitaria).",
    "Motocicletas sin placas o con conducta sospechosa.",
    "Ausencia de presencia policial visible o patrullajes limitados.",
    "Accesos rápidos de escape (callejones, ríos, rutas alternas).",
    "Espacios públicos deteriorados (parques, canchas, paradas).",
    "Falta de cámaras o videovigilancia comunitaria.",
    "Reportes de robos, tacha de vehículos o riñas.",
    "Percepción de inseguridad y acoso callejero.",
    "Otro: especificar.",
]

# Paleta (color por factor) — usada en marcadores
_PALETTE = [
    "#e41a1c","#377eb8","#4daf4a","#984ea3","#ff7f00","#ffff33",
    "#a65628","#f781bf","#999999","#1b9e77","#d95f02","#7570b3",
    "#e7298a","#66a61e","#e6ab02","#a6761d","#1f78b4","#b2df8a",
    "#fb9a99","#cab2d6","#fdbf6f","#b15928"
]
FACTOR_COLORS = {f: _PALETTE[i % len(_PALETTE)] for i, f in enumerate(FACTORES)}

# ==========================================================
# MAP CONFIG — vista general CR (igual para todos)
# ==========================================================
CR_CENTER = [9.7489, -83.7534]
CR_ZOOM = 8

# Selector de estilos por formulario (todos arrancan en ESRI)
MAP_STYLE_OPTIONS = [
    "Esri Satélite",
    "Base gris (Carto)",
    "OpenStreetMap",
    "Terreno (Stamen)",
]

# ==========================================================
# GOOGLE SHEETS (DB)
# ==========================================================
@st.cache_resource(show_spinner=False)
def _client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

@st.cache_resource(show_spinner=False)
def _spreadsheet():
    return _client().open_by_key(SHEET_ID)

def _get_or_create_ws(ws_name: str):
    sh = _spreadsheet()
    try:
        ws = sh.worksheet(ws_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=ws_name, rows=5000, cols=max(26, len(HEADERS) + 5))

    current = [h.strip() for h in ws.row_values(1)]
    if not current:
        ws.append_row(HEADERS, value_input_option="USER_ENTERED")
    else:
        missing = [h for h in HEADERS if h not in current]
        if missing:
            start_col = len(current) + 1
            end_col = start_col + len(missing) - 1
            ws.update(
                f"{gspread.utils.rowcol_to_a1(1, start_col)}:{gspread.utils.rowcol_to_a1(1, end_col)}",
                [missing]
            )
    return ws

def _headers(ws):
    return [h.strip() for h in ws.row_values(1)]

def _split_factores(factores):
    if isinstance(factores, list):
        return [x.strip() for x in factores if str(x).strip()]
    if isinstance(factores, str):
        return [s.strip() for s in factores.split("|") if s.strip()]
    return []

def append_rows_one_per_factor(ws_name: str, data: dict):
    ws = _get_or_create_ws(ws_name)
    headers = _headers(ws)

    factores_list = _split_factores(data.get("factores", []))
    if not factores_list:
        return 0

    maps_url = f'https://www.google.com/maps?q={data["lat"]},{data["lng"]}'

    saved = 0
    for f in factores_list:
        row_dict = {
            "date": data.get("date", ""),
            "barrio": data.get("barrio", ""),
            "factores": f,
            "delitos_relacionados": data.get("delitos_relacionados", ""),
            "ligado_estructura": data.get("ligado_estructura", ""),
            "nombre_estructura": data.get("nombre_estructura", ""),
            "observaciones": data.get("observaciones", ""),
            "maps_link": maps_url,
        }
        ws.append_row([row_dict.get(h, "") for h in headers], value_input_option="USER_ENTERED")
        saved += 1
    return saved

@st.cache_data(ttl=25, show_spinner=False)
def read_df(ws_name: str) -> pd.DataFrame:
    ws = _get_or_create_ws(ws_name)
    records = ws.get_all_records()
    if not records:
        cols = HEADERS + ["lat", "lng", "source_form"]
        return pd.DataFrame(columns=cols)

    df_raw = pd.DataFrame(records)
    for c in HEADERS:
        if c not in df_raw.columns:
            df_raw[c] = ""

    url_pat = re.compile(r"https?://.*maps\?q=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")
    out = []

    for _, r in df_raw.iterrows():
        factores_list = _split_factores(r.get("factores", ""))
        if not factores_list:
            factores_list = [""]

        m = url_pat.search(str(r.get("maps_link", "")))
        lat = float(m.group(1)) if m else None
        lng = float(m.group(2)) if m else None

        for f in factores_list:
            out.append({
                "date": r.get("date", ""),
                "barrio": r.get("barrio", ""),
                "factores": f,
                "delitos_relacionados": r.get("delitos_relacionados", ""),
                "ligado_estructura": r.get("ligado_estructura", ""),
                "nombre_estructura": r.get("nombre_estructura", ""),
                "observaciones": r.get("observaciones", ""),
                "maps_link": r.get("maps_link", ""),
                "lat": lat,
                "lng": lng,
                "source_form": ws_name,
            })

    df = pd.DataFrame(out)
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    return df

# ==========================================================
# MAP UTILS
# ==========================================================
def _jitter(idx: int, base: float = 0.00008) -> float:
    random.seed(idx)
    return (random.random() - 0.5) * base

def _add_panes(m):
    folium.map.CustomPane("markers", z_index=400).add_to(m)
    folium.map.CustomPane("heatmap", z_index=650).add_to(m)

def _add_tile_by_name(m, style_name: str):
    if style_name == "Esri Satélite":
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="Esri Satélite",
            overlay=False,
            control=True
        ).add_to(m)

    elif style_name == "Base gris (Carto)":
        folium.TileLayer("CartoDB positron", name="Base gris (Carto)", overlay=False, control=True).add_to(m)

    elif style_name == "OpenStreetMap":
        folium.TileLayer("OpenStreetMap", name="OpenStreetMap", overlay=False, control=True).add_to(m)

    elif style_name == "Terreno (Stamen)":
        folium.TileLayer(
            tiles="https://stamen-tiles.a.ssl.fastly.net/terrain/{z}/{x}/{y}.png",
            attr="Map tiles by Stamen Design, under CC BY 3.0. Data by OpenStreetMap, under ODbL.",
            name="Terreno (Stamen)",
            overlay=False,
            control=True
        ).add_to(m)

    else:
        folium.TileLayer("CartoDB positron", name="Base gris (Carto)", overlay=False, control=True).add_to(m)

def _legend_html():
    items = "".join(
        f'<div style="display:flex;align-items:flex-start;margin-bottom:6px">'
        f'<span style="width:12px;height:12px;background:{FACTOR_COLORS.get(f,"#555")};'
        f'display:inline-block;margin-right:8px;border:1px solid #333;"></span>'
        f'<span style="font-size:12px;color:#000;line-height:1.2;">{f}</span></div>'
        for f in FACTORES
    )
    return (
        '<div style="position: fixed; bottom: 20px; right: 20px; z-index:9999; '
        'background: rgba(255,255,255,0.98); padding:10px; border:1px solid #666; '
        'border-radius:6px; max-height:320px; overflow:auto; width:340px; color:#000;">'
        '<div style="font-weight:700; margin-bottom:6px; color:#000;">Leyenda – Factores</div>'
        f'{items}</div>'
    )

# ==========================================================
# DATA UTILS (para gráficas)
# ==========================================================
def load_all_data() -> pd.DataFrame:
    dfs = []
    for label, ws_name in FORM_SHEETS.items():
        df = read_df(ws_name).copy()
        df["form_label"] = label
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def parse_date_safe(series: pd.Series) -> pd.Series:
    # formato esperado: dd-mm-YYYY, pero tolerante
    return pd.to_datetime(series, errors="coerce", dayfirst=True)

# ==========================================================
# UI – TABS
# ==========================================================
st.title("📍 Costa Rica — 5 Formularios + Visor + Gráficas")
st.caption("DB en Google Sheets. 5 formularios guardan en hojas distintas. Visor por capas + pestaña de gráficas.")

tab_labels = list(FORM_SHEETS.keys()) + ["Visor (capas)", "📊 Gráficas"]
tabs = st.tabs(tab_labels)

# ==========================================================
# 5 FORMULARIOS
# ==========================================================
def render_form(form_label: str):
    ws_name = FORM_SHEETS[form_label]
    st.subheader(f"{form_label} — Guardando en hoja: {ws_name}")

    # Selector de estilo (cada tab decide como verlo)
    style = st.selectbox(
        "Estilo de mapa",
        options=MAP_STYLE_OPTIONS,
        index=0,  # siempre arranca en ESRI
        key=f"style_{ws_name}"
    )

    left, right = st.columns([0.58, 0.42], gap="large")

    # ---------- MAPA (clic para lat/lng) ----------
    with left:
        st.markdown("### Selecciona un punto en el mapa")
        st.caption("Usa el ícono 🎯 (Localizar) si querés centrarte donde estás, luego haz clic para marcar.")

        key_clicked = f"clicked_{ws_name}"
        clicked = st.session_state.get(key_clicked) or {}
        center = [
            clicked.get("lat", CR_CENTER[0]),
            clicked.get("lng", CR_CENTER[1])
        ]

        m = folium.Map(location=center, zoom_start=CR_ZOOM, control_scale=True, tiles=None)
        _add_panes(m)

        # Siempre incluye ESRI + el estilo elegido
        _add_tile_by_name(m, "Esri Satélite")
        if style != "Esri Satélite":
            _add_tile_by_name(m, style)

        LocateControl(auto_start=False, flyTo=True).add_to(m)

        if clicked.get("lat") is not None and clicked.get("lng") is not None:
            folium.CircleMarker(
                [clicked["lat"], clicked["lng"]],
                radius=8, color="#000", weight=1,
                fill=True, fill_color="#2dd4bf", fill_opacity=0.9,
                tooltip="Ubicación seleccionada", pane="markers"
            ).add_to(m)

        folium.LayerControl(collapsed=False).add_to(m)
        map_ret = st_folium(m, height=520, use_container_width=True, key=f"map_{ws_name}")

        if map_ret and map_ret.get("last_clicked"):
            st.session_state[key_clicked] = {
                "lat": round(map_ret["last_clicked"]["lat"], 6),
                "lng": round(map_ret["last_clicked"]["lng"], 6),
            }
            clicked = st.session_state[key_clicked]

        cols = st.columns(3)
        lat_val, lng_val = clicked.get("lat"), clicked.get("lng")
        cols[0].metric("Latitud", lat_val if lat_val is not None else "—")
        cols[1].metric("Longitud", lng_val if lng_val is not None else "—")
        if cols[2].button("Limpiar selección", key=f"clear_{ws_name}"):
            st.session_state.pop(key_clicked, None)
            st.rerun()

    # ---------- FORMULARIO ----------
    with right:
        st.markdown("### Formulario de encuesta")
        with st.form(f"form_{ws_name}", clear_on_submit=True):
            barrio = st.text_input("Barrio (opcional)")
            factores_sel = st.multiselect("Factor(es) de riesgo *", options=FACTORES, default=[])
            delitos = st.text_area("Delitos relacionados (opcional)", height=70)
            ligado = st.radio("Ligado a estructura (opcional)", ["No", "Sí"], index=0, horizontal=True)
            nombre_estructura = st.text_input("Nombre de la estructura (opcional)")
            observ = st.text_area("Observaciones (opcional)", height=90)
            submit = st.form_submit_button("Guardar en Google Sheets")

        if submit:
            errs = []
            if lat_val is None or lng_val is None:
                errs.append("Selecciona un **punto en el mapa**.")
            if not factores_sel:
                errs.append("Selecciona al menos **un factor de riesgo**.")
            if errs:
                st.error("• " + "\n• ".join(errs))
            else:
                payload = {
                    "date": datetime.now(TZ).strftime("%d-%m-%Y"),
                    "barrio": (barrio or "").strip(),
                    "factores": factores_sel,  # lista -> se guardan N filas
                    "delitos_relacionados": (delitos or "").strip(),
                    "ligado_estructura": (ligado or "").strip(),
                    "nombre_estructura": (nombre_estructura or "").strip(),
                    "observaciones": (observ or "").strip(),
                    "lat": lat_val, "lng": lng_val,
                }
                try:
                    n = append_rows_one_per_factor(ws_name, payload)
                    st.success(f"✅ Guardado: {n} fila(s) en {ws_name} (una por factor).")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ No se pudo guardar.\n\n{e}")

    st.divider()
    st.markdown("#### Últimos registros (hoja actual)")
    df_local = read_df(ws_name)
    view = df_local[["date","barrio","factores","delitos_relacionados","ligado_estructura","nombre_estructura","observaciones","maps_link"]]
    st.dataframe(view.tail(200), use_container_width=True)
    st.download_button(
        "⬇️ Descargar CSV de este formulario",
        data=view.to_csv(index=False).encode("utf-8"),
        file_name=f"{ws_name}.csv",
        mime="text/csv",
        key=f"dl_{ws_name}"
    )

# Render de 5 tabs
for i, form_label in enumerate(FORM_SHEETS.keys()):
    with tabs[i]:
        render_form(form_label)

# ==========================================================
# TAB 6 — VISOR POR CAPAS (ver 1..5 o todos)
# ==========================================================
with tabs[-2]:
    st.subheader("🗺️ Visor (capas) — Ver datos por formulario o todo junto")

    visor_style = st.selectbox(
        "Estilo de mapa (Visor)",
        options=MAP_STYLE_OPTIONS,
        index=0,
        key="visor_style"
    )

    df_all = load_all_data()

    if df_all.empty:
        st.info("Aún no hay registros en los 5 formularios.")
    else:
        c1, c2, c3 = st.columns([0.45, 0.25, 0.30])
        with c1:
            layer = st.selectbox(
                "Capa (formulario) a visualizar",
                options=["(Todos)"] + list(FORM_SHEETS.keys()),
                index=0
            )
        with c2:
            show_heat = st.checkbox("Mostrar HeatMap", value=True)
        with c3:
            show_clusters = st.checkbox("Mostrar clusters", value=True)

        dfv = df_all.copy()
        if layer != "(Todos)":
            dfv = dfv[dfv["form_label"] == layer]

        factores_unicos = sorted([f for f in dfv["factores"].dropna().unique() if str(f).strip()])
        factor_sel = st.selectbox("Filtrar por factor (opcional)", options=["(Todos)"] + factores_unicos, index=0)
        if factor_sel != "(Todos)":
            dfv = dfv[dfv["factores"] == factor_sel]

        m = folium.Map(location=CR_CENTER, zoom_start=CR_ZOOM, control_scale=True, tiles=None)
        _add_panes(m)

        _add_tile_by_name(m, "Esri Satélite")
        if visor_style != "Esri Satélite":
            _add_tile_by_name(m, visor_style)

        LocateControl(auto_start=False).add_to(m)
        m.get_root().html.add_child(folium.Element(_legend_html()))

        group = (MarkerCluster(name="Marcadores", overlay=True, control=True, pane="markers")
                 if show_clusters else folium.FeatureGroup(name="Marcadores", overlay=True, control=True))
        group.add_to(m)

        heat_points = []
        idx = 0
        omitidos = 0

        for _, r in dfv.iterrows():
            lat, lng = r.get("lat"), r.get("lng")
            if pd.isna(lat) or pd.isna(lng):
                omitidos += 1
                continue

            factor = r.get("factores", "")
            color = FACTOR_COLORS.get(factor, "#555555")
            popup = (
                f"<b>Formulario:</b> {r.get('form_label','')}<br>"
                f"<b>Fecha:</b> {r.get('date','')}<br>"
                f"<b>Barrio:</b> {r.get('barrio','')}<br>"
                f"<b>Factor:</b> {factor}<br>"
                f"<b>Delitos:</b> {r.get('delitos_relacionados','')}<br>"
                f"<b>Estructura:</b> {r.get('ligado_estructura','')} {r.get('nombre_estructura','')}<br>"
                f"<b>Obs:</b> {r.get('observaciones','')}<br>"
                f"<b>Maps:</b> <a href='{r.get('maps_link','')}' target='_blank'>Abrir</a>"
            )

            jlat = float(lat) + (random.random() - 0.5) * 0.00008
            jlng = float(lng) + (random.random() - 0.5) * 0.00008

            folium.CircleMarker(
                [jlat, jlng],
                radius=7, color="#000", weight=1,
                fill=True, fill_color=color, fill_opacity=0.9,
                popup=popup, pane="markers"
            ).add_to(group)

            heat_points.append([float(lat), float(lng), 1.0])
            idx += 1

        if show_heat and heat_points:
            red_gradient = {0.2: "pink", 0.5: "red", 1.0: "darkred"}
            HeatMap(
                heat_points,
                radius=18, blur=22, max_zoom=16, min_opacity=0.25,
                gradient=red_gradient
            ).add_to(folium.FeatureGroup(name="Mapa de calor", overlay=True, control=True, pane="heatmap").add_to(m))

        folium.LayerControl(collapsed=False).add_to(m)
        st_folium(m, height=560, use_container_width=True, key="visor_map")

        if omitidos:
            st.caption(f"({omitidos} registro(s) omitidos por coordenadas inválidas)")

        st.divider()
        st.markdown("#### Tabla (según filtros)")
        show_cols = ["form_label", "date","barrio","factores","delitos_relacionados","ligado_estructura","nombre_estructura","observaciones","maps_link"]
        show_df = dfv[show_cols].copy()
        st.dataframe(show_df, use_container_width=True)

        st.download_button(
            "⬇️ Descargar CSV (visor)",
            data=show_df.to_csv(index=False).encode("utf-8"),
            file_name="visor_formularios.csv",
            mime="text/csv"
        )

# ==========================================================
# TAB 7 — GRÁFICAS (PLUS)
# ==========================================================
with tabs[-1]:
    st.subheader("📊 Gráficas (Plus) — Resumen visual con filtros")
    st.caption("No modifica nada: solo lee los datos de las 5 hojas y construye gráficos filtrables.")

    df_all = load_all_data()
    if df_all.empty:
        st.info("Aún no hay registros para graficar.")
    else:
        # Filtros principales
        c1, c2, c3 = st.columns([0.35, 0.35, 0.30])
        with c1:
            layer = st.selectbox(
                "Fuente (formulario)",
                options=["(Todos)"] + list(FORM_SHEETS.keys()),
                index=0,
                key="g_layer"
            )
        with c2:
            factores_unicos = sorted([f for f in df_all["factores"].dropna().unique() if str(f).strip()])
            factor_sel = st.selectbox(
                "Factor (opcional)",
                options=["(Todos)"] + factores_unicos,
                index=0,
                key="g_factor"
            )
        with c3:
            top_n = st.slider("Top N factores", 5, 25, 10, key="g_top")

        dfg = df_all.copy()
        if layer != "(Todos)":
            dfg = dfg[dfg["form_label"] == layer]
        if factor_sel != "(Todos)":
            dfg = dfg[dfg["factores"] == factor_sel]

        # Fechas (si hay)
        dfg["date_dt"] = parse_date_safe(dfg["date"])
        min_d = dfg["date_dt"].min()
        max_d = dfg["date_dt"].max()

        if pd.notna(min_d) and pd.notna(max_d):
            r = st.date_input(
                "Rango de fechas (opcional)",
                value=(min_d.date(), max_d.date()),
                key="g_date"
            )
            if isinstance(r, tuple) and len(r) == 2:
                d1, d2 = pd.to_datetime(r[0]), pd.to_datetime(r[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
                dfg = dfg[(dfg["date_dt"] >= d1) & (dfg["date_dt"] <= d2)]

        if dfg.empty:
            st.warning("No hay datos con esos filtros.")
        else:
            # Conteo de factores
            counts = (
                dfg["factores"]
                .fillna("")
                .replace("", pd.NA)
                .dropna()
                .value_counts()
                .head(top_n)
                .reset_index()
            )
            counts.columns = ["factor", "conteo"]

            # Métricas rápidas
            m1, m2, m3 = st.columns(3)
            m1.metric("Registros (filas)", len(dfg))
            m2.metric("Factores únicos", dfg["factores"].nunique(dropna=True))
            m3.metric("Formularios en vista", dfg["form_label"].nunique())

            st.divider()

            # --- Gráfico 1: Barras (tipo imagen)
            st.markdown("### 📌 Top factores (Barras)")
            fig_bar = px.bar(
                counts,
                x="factor",
                y="conteo",
                text="conteo",
                title="Top factores por frecuencia"
            )
            fig_bar.update_layout(xaxis_title="", yaxis_title="Cantidad", xaxis_tickangle=-25)
            st.plotly_chart(fig_bar, use_container_width=True)

            # --- Gráfico 2: Donut (tipo imagen)
            st.markdown("### 🍩 Distribución (Donut)")
            fig_pie = px.pie(
                counts,
                names="factor",
                values="conteo",
                hole=0.55,
                title="Distribución de los factores (Top)"
            )
            st.plotly_chart(fig_pie, use_container_width=True)

            # --- Gráfico 3 (extra): Ligado a estructura (Sí/No)
            st.markdown("### 🧩 Ligado a estructura (Sí/No)")
            by_struct = (
                dfg["ligado_estructura"]
                .fillna("No indicado")
                .replace("", "No indicado")
                .value_counts()
                .reset_index()
            )
            by_struct.columns = ["respuesta", "conteo"]
            fig_struct = px.bar(by_struct, x="respuesta", y="conteo", text="conteo", title="Registros por respuesta")
            fig_struct.update_layout(xaxis_title="", yaxis_title="Cantidad")
            st.plotly_chart(fig_struct, use_container_width=True)

            st.divider()
            st.markdown("#### Datos base (según filtros)")
            show_cols = ["form_label","date","barrio","factores","delitos_relacionados","ligado_estructura","nombre_estructura","observaciones","maps_link"]
            st.dataframe(dfg[show_cols].copy(), use_container_width=True)
