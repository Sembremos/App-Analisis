# -*- coding: utf-8 -*-
# Streamlit — 5 Formularios (5 hojas) + Visor (capas) + Gráficas — Google Sheets como DB
# ✅ Formulario 1: Provincia, Cantón, Barrio (opcional) + Estructuras (1..11) + map
# ✅ Se elimina N
# ✅ Dashboard dentro de Form 1 con filtros (Provincia/Cantón/Pandilla) + gráficas
# ✅ Visor sin parpadeo + pines tipo Google (BeautifyIcon)
# ✅ Gráficas pro (barras/donut/sunburst) para todo el sistema

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import random, re

import gspread
from google.oauth2.service_account import Credentials

import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, LocateControl, HeatMap, BeautifyIcon

import plotly.express as px

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(page_title="CR – Formularios + Visor + Gráficas", layout="wide")
TZ = ZoneInfo("America/Costa_Rica")

SHEET_ID = "1pCUXSJ_hvQzpzBTaJ-h0ntcdhYwMTyWomxXMjmi7lyg"

# ====== Nombre del Form 1 (Tab 1 + Hoja 1) ======
FORM1_TITLE = "Pandillas de trafico transnacional Costa Rica 2025"
FORM1_SHEET = FORM1_TITLE

FORM_SHEETS = {
    FORM1_TITLE: FORM1_SHEET,   # Form 1 (Excel)
    "Formulario 2": "Prueba_2",
    "Formulario 3": "Prueba_3",
    "Formulario 4": "Prueba_4",
    "Formulario 5": "Prueba_5",
}

# ==========================================================
# SCHEMAS
# ==========================================================
# Formulario 1: Provincia, Cantón, Barrio (opcional) + 11 estructuras + maps_link + date
FORM1_HEADERS = [
    "provincia",
    "canton",
    "barrio",
    "estructura_1",
    "estructura_2",
    "estructura_3",
    "estructura_4",
    "estructura_5",
    "estructura_6",
    "estructura_7",
    "estructura_8",
    "estructura_9",
    "estructura_10",
    "estructura_11",
    "maps_link",
    "date",
]

# Formularios 2..5: encuesta original
SURVEY_HEADERS = [
    "date", "barrio", "factores", "delitos_relacionados",
    "ligado_estructura", "nombre_estructura", "observaciones", "maps_link"
]

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

_PALETTE = [
    "#e41a1c","#377eb8","#4daf4a","#984ea3","#ff7f00","#ffff33",
    "#a65628","#f781bf","#999999","#1b9e77","#d95f02","#7570b3",
    "#e7298a","#66a61e","#e6ab02","#a6761d","#1f78b4","#b2df8a",
    "#fb9a99","#cab2d6","#fdbf6f","#b15928"
]
FACTOR_COLORS = {f: _PALETTE[i % len(_PALETTE)] for i, f in enumerate(FACTORES)}
DEFAULT_PIN_ICON = "map-marker-alt"

# ==========================================================
# MAP CONFIG
# ==========================================================
CR_CENTER = [9.7489, -83.7534]
CR_ZOOM = 8

MAP_STYLE_OPTIONS = [
    "Esri Satélite",
    "Base gris (Carto)",
    "OpenStreetMap",
    "Terreno (Stamen)",
]

# ==========================================================
# GOOGLE SHEETS
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

def _get_or_create_ws(ws_name: str, headers: list):
    sh = _spreadsheet()
    try:
        ws = sh.worksheet(ws_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=ws_name, rows=5000, cols=max(26, len(headers) + 5))

    current = [h.strip() for h in ws.row_values(1)]
    if not current:
        ws.append_row(headers, value_input_option="USER_ENTERED")
    else:
        missing = [h for h in headers if h not in current]
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

def append_row_generic(ws_name: str, headers: list, row_dict: dict):
    ws = _get_or_create_ws(ws_name, headers)
    cols = _headers(ws)
    ws.append_row([row_dict.get(c, "") for c in cols], value_input_option="USER_ENTERED")

def append_rows_one_per_factor(ws_name: str, data: dict):
    headers = SURVEY_HEADERS
    ws = _get_or_create_ws(ws_name, headers)
    cols = _headers(ws)

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
        ws.append_row([row_dict.get(c, "") for c in cols], value_input_option="USER_ENTERED")
        saved += 1
    return saved

@st.cache_data(ttl=25, show_spinner=False)
def read_df_generic(ws_name: str, headers: list) -> pd.DataFrame:
    ws = _get_or_create_ws(ws_name, headers)
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=headers + ["lat", "lng", "source_form", "form_label"])

    df_raw = pd.DataFrame(records)
    for c in headers:
        if c not in df_raw.columns:
            df_raw[c] = ""

    url_pat = re.compile(r"https?://.*maps\?q=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")
    lat_list, lng_list = [], []
    for v in df_raw.get("maps_link", pd.Series([""] * len(df_raw))):
        m = url_pat.search(str(v))
        lat_list.append(float(m.group(1)) if m else None)
        lng_list.append(float(m.group(2)) if m else None)

    df_raw["lat"] = pd.to_numeric(lat_list, errors="coerce")
    df_raw["lng"] = pd.to_numeric(lng_list, errors="coerce")
    df_raw["source_form"] = ws_name
    return df_raw

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

def make_pin_icon(color_hex: str):
    return BeautifyIcon(
        icon=DEFAULT_PIN_ICON,
        icon_shape="marker",
        background_color=color_hex,
        border_color="#111",
        text_color="#fff"
    )

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
        'border-radius:6px; max-height:320px; overflow:auto; width:360px; color:#000;">'
        '<div style="font-weight:700; margin-bottom:6px; color:#000;">Leyenda – Factores</div>'
        f'{items}</div>'
    )

# ==========================================================
# FORM 1 DASHBOARD UTILS
# ==========================================================
def extract_all_structures(df1: pd.DataFrame) -> pd.DataFrame:
    """Devuelve tabla normalizada: provincia, canton, barrio, estructura (una por fila) + maps_link + date."""
    if df1.empty:
        return pd.DataFrame(columns=["provincia","canton","barrio","estructura","maps_link","date","lat","lng"])
    rows = []
    for _, r in df1.iterrows():
        prov = str(r.get("provincia","")).strip()
        cant = str(r.get("canton","")).strip()
        barr = str(r.get("barrio","")).strip()
        date = str(r.get("date","")).strip()
        maps_link = str(r.get("maps_link","")).strip()
        lat = r.get("lat")
        lng = r.get("lng")
        for i in range(1, 12):
            val = str(r.get(f"estructura_{i}", "")).strip()
            if val and val.lower() != "nan":
                rows.append({
                    "provincia": prov,
                    "canton": cant,
                    "barrio": barr,
                    "estructura": val,
                    "maps_link": maps_link,
                    "date": date,
                    "lat": lat,
                    "lng": lng
                })
    return pd.DataFrame(rows)

def parse_date_safe(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", dayfirst=True)

# ==========================================================
# LOAD ALL (para visor y gráficas globales)
# ==========================================================
def load_all_data() -> pd.DataFrame:
    dfs = []

    # Form 1
    df1 = read_df_generic(FORM1_SHEET, FORM1_HEADERS).copy()
    df1["form_label"] = FORM1_TITLE
    # Normalizamos campo "factores" para que el visor pueda filtrar/contar
    df1["factores"] = "(Form1 – estructuras)"
    dfs.append(df1)

    # Forms 2..5
    for label in ["Formulario 2", "Formulario 3", "Formulario 4", "Formulario 5"]:
        ws_name = FORM_SHEETS[label]
        df = read_df_generic(ws_name, SURVEY_HEADERS).copy()
        df["form_label"] = label
        dfs.append(df)

    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# ==========================================================
# UI
# ==========================================================
st.title("📍 Costa Rica — Formularios + Visor + Gráficas")
st.caption("Cada pestaña guarda en su hoja. Formulario 1 ya está adaptado a Provincia/Cantón/Barrio + estructuras.")

tab_labels = list(FORM_SHEETS.keys()) + ["Visor (capas)", "📊 Gráficas"]
tabs = st.tabs(tab_labels)

# ==========================================================
# FORM 1 — ACTUALIZADO
# ==========================================================
with tabs[0]:
    st.subheader(f"{FORM1_TITLE} — Guardando en hoja: {FORM1_SHEET}")

    style = st.selectbox("Estilo de mapa", MAP_STYLE_OPTIONS, index=0, key="style_form1")

    left, right = st.columns([0.58, 0.42], gap="large")

    with left:
        st.markdown("### Selecciona un punto en el mapa")
        key_clicked = "clicked_form1"
        clicked = st.session_state.get(key_clicked) or {}
        center = [clicked.get("lat", CR_CENTER[0]), clicked.get("lng", CR_CENTER[1])]

        m = folium.Map(location=center, zoom_start=CR_ZOOM, control_scale=True, tiles=None)
        _add_panes(m)
        _add_tile_by_name(m, "Esri Satélite")
        if style != "Esri Satélite":
            _add_tile_by_name(m, style)
        LocateControl(auto_start=False, flyTo=True).add_to(m)

        if clicked.get("lat") is not None and clicked.get("lng") is not None:
            folium.Marker(
                [clicked["lat"], clicked["lng"]],
                icon=make_pin_icon("#2dd4bf"),
                tooltip="Ubicación seleccionada",
                pane="markers"
            ).add_to(m)

        folium.LayerControl(collapsed=False).add_to(m)
        map_ret = st_folium(m, height=520, use_container_width=True, key="map_form1")

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
        if cols[2].button("Limpiar selección", key="clear_form1"):
            st.session_state.pop(key_clicked, None)
            st.rerun()

    with right:
        st.markdown("### Formulario (Provincia / Cantón / Barrio opcional + estructuras)")

        with st.form("form_excel_1", clear_on_submit=True):
            provincia = st.text_input("Provincia *")
            canton = st.text_input("Cantón *")
            barrio = st.text_input("Barrio (opcional)")

            st.markdown("#### Estructuras / Pandillas (podés llenar varias)")
            e1 = st.text_input("Estructura 1")
            e2 = st.text_input("Estructura 2")
            e3 = st.text_input("Estructura 3")
            e4 = st.text_input("Estructura 4")
            e5 = st.text_input("Estructura 5")
            e6 = st.text_input("Estructura 6")
            e7 = st.text_input("Estructura 7")
            e8 = st.text_input("Estructura 8")
            e9 = st.text_input("Estructura 9")
            e10 = st.text_input("Estructura 10")
            e11 = st.text_input("Estructura 11")

            submit = st.form_submit_button("Guardar en Google Sheets")

        if submit:
            errs = []
            if lat_val is None or lng_val is None:
                errs.append("Selecciona un **punto en el mapa**.")
            if not provincia.strip():
                errs.append("Provincia es requerida.")
            if not canton.strip():
                errs.append("Cantón es requerido.")

            # al menos una estructura (si querés permitir 0, quitá esto)
            estructuras = [e1,e2,e3,e4,e5,e6,e7,e8,e9,e10,e11]
            if not any([str(x).strip() for x in estructuras]):
                errs.append("Agrega al menos **una estructura/pandilla** (Estructura 1..11).")

            if errs:
                st.error("• " + "\n• ".join(errs))
            else:
                maps_url = f"https://www.google.com/maps?q={lat_val},{lng_val}"
                row = {
                    "provincia": provincia.strip(),
                    "canton": canton.strip(),
                    "barrio": (barrio or "").strip(),
                    "estructura_1": e1.strip(),
                    "estructura_2": e2.strip(),
                    "estructura_3": e3.strip(),
                    "estructura_4": e4.strip(),
                    "estructura_5": e5.strip(),
                    "estructura_6": e6.strip(),
                    "estructura_7": e7.strip(),
                    "estructura_8": e8.strip(),
                    "estructura_9": e9.strip(),
                    "estructura_10": e10.strip(),
                    "estructura_11": e11.strip(),
                    "maps_link": maps_url,
                    "date": datetime.now(TZ).strftime("%d-%m-%Y"),
                }
                try:
                    append_row_generic(FORM1_SHEET, FORM1_HEADERS, row)
                    st.success("✅ Registro guardado en Formulario 1.")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ No se pudo guardar.\n\n{e}")

    st.divider()
    st.markdown("## 📋 Datos registrados (Formulario 1)")
    df1 = read_df_generic(FORM1_SHEET, FORM1_HEADERS)
    st.dataframe(df1[FORM1_HEADERS].tail(300), use_container_width=True)

    st.download_button(
        "⬇️ Descargar CSV (Formulario 1)",
        data=df1[FORM1_HEADERS].to_csv(index=False).encode("utf-8"),
        file_name=f"{FORM1_SHEET}.csv",
        mime="text/csv",
        key="dl_form1"
    )

    # ===============================
    # DASHBOARD FORM 1
    # ===============================
    st.divider()
    st.markdown("## 📊 Dashboard (Formulario 1) — filtros y gráficas")

    df_struct = extract_all_structures(df1)

    if df_struct.empty:
        st.info("Aún no hay estructuras registradas para graficar.")
    else:
        colf1, colf2, colf3 = st.columns([0.34, 0.33, 0.33])

        provincias = sorted([p for p in df_struct["provincia"].dropna().unique() if str(p).strip()])
        with colf1:
            f_prov = st.selectbox("Provincia", options=["(Todas)"] + provincias, index=0, key="f1_prov")

        df_tmp = df_struct.copy()
        if f_prov != "(Todas)":
            df_tmp = df_tmp[df_tmp["provincia"] == f_prov]

        cantones = sorted([c for c in df_tmp["canton"].dropna().unique() if str(c).strip()])
        with colf2:
            f_cant = st.selectbox("Cantón", options=["(Todos)"] + cantones, index=0, key="f1_cant")

        if f_cant != "(Todos)":
            df_tmp = df_tmp[df_tmp["canton"] == f_cant]

        # filtro por nombre de pandilla/estructura (buscador)
        with colf3:
            f_pand = st.text_input("Buscar pandilla/estructura (contiene)", value="", key="f1_pand")

        if f_pand.strip():
            df_tmp = df_tmp[df_tmp["estructura"].str.contains(f_pand.strip(), case=False, na=False)]

        m1, m2, m3 = st.columns(3)
        m1.metric("Registros (estructuras)", len(df_tmp))
        m2.metric("Pandillas únicas", df_tmp["estructura"].nunique())
        m3.metric("Cantones en vista", df_tmp["canton"].nunique())

        # Conteo por estructura (Top)
        top_n = st.slider("Top N pandillas", 5, 30, 10, key="f1_topn")
        counts = (
            df_tmp["estructura"]
            .value_counts()
            .head(top_n)
            .reset_index()
        )
        counts.columns = ["estructura", "conteo"]

        st.markdown("### 🔝 Top pandillas/estructuras (Barras)")
        fig_bar = px.bar(
            counts.sort_values("conteo", ascending=True),
            x="conteo", y="estructura", orientation="h", text="conteo",
            template="plotly_dark",
            title="Top pandillas/estructuras por frecuencia"
        )
        fig_bar.update_traces(textposition="outside", cliponaxis=False)
        fig_bar.update_layout(height=520, margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("### 🍩 Distribución (Donut)")
        fig_donut = px.pie(
            counts,
            names="estructura",
            values="conteo",
            hole=0.6,
            template="plotly_dark",
            title="Distribución (Top)"
        )
        fig_donut.update_traces(
            textinfo="percent",
            textposition="inside",
            hovertemplate="<b>%{label}</b><br>Conteo: %{value}<br>%{percent}<extra></extra>",
        )
        fig_donut.update_layout(height=520, margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig_donut, use_container_width=True)

        st.markdown("### 🧊 Capas (Sunburst) — Provincia → Cantón → Pandilla")
        grp = df_tmp.groupby(["provincia","canton","estructura"]).size().reset_index(name="conteo")
        fig_sun = px.sunburst(
            grp,
            path=["provincia","canton","estructura"],
            values="conteo",
            template="plotly_dark",
            title="Capas: Provincia → Cantón → Pandilla"
        )
        fig_sun.update_layout(height=600, margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig_sun, use_container_width=True)

# ==========================================================
# FORMULARIOS 2..5 — ENCUESTA
# ==========================================================
def render_survey_form(form_label: str):
    ws_name = FORM_SHEETS[form_label]
    st.subheader(f"{form_label} — Guardando en hoja: {ws_name}")

    style = st.selectbox("Estilo de mapa", MAP_STYLE_OPTIONS, index=0, key=f"style_{ws_name}")

    left, right = st.columns([0.58, 0.42], gap="large")
    with left:
        st.markdown("### Selecciona un punto en el mapa")
        key_clicked = f"clicked_{ws_name}"
        clicked = st.session_state.get(key_clicked) or {}
        center = [clicked.get("lat", CR_CENTER[0]), clicked.get("lng", CR_CENTER[1])]

        m = folium.Map(location=center, zoom_start=CR_ZOOM, control_scale=True, tiles=None)
        _add_panes(m)
        _add_tile_by_name(m, "Esri Satélite")
        if style != "Esri Satélite":
            _add_tile_by_name(m, style)
        LocateControl(auto_start=False, flyTo=True).add_to(m)

        if clicked.get("lat") is not None and clicked.get("lng") is not None:
            folium.Marker(
                [clicked["lat"], clicked["lng"]],
                icon=make_pin_icon("#2dd4bf"),
                tooltip="Ubicación seleccionada",
                pane="markers"
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
                    "factores": factores_sel,
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
    df_local = read_df_generic(ws_name, SURVEY_HEADERS)
    view = df_local[SURVEY_HEADERS].tail(200)
    st.dataframe(view, use_container_width=True)
    st.download_button(
        "⬇️ Descargar CSV de este formulario",
        data=view.to_csv(index=False).encode("utf-8"),
        file_name=f"{ws_name}.csv",
        mime="text/csv",
        key=f"dl_{ws_name}"
    )

with tabs[1]:
    render_survey_form("Formulario 2")
with tabs[2]:
    render_survey_form("Formulario 3")
with tabs[3]:
    render_survey_form("Formulario 4")
with tabs[4]:
    render_survey_form("Formulario 5")

# ==========================================================
# VISOR (capas) — SIN PARPADEO
# ==========================================================
with tabs[-2]:
    st.subheader("🗺️ Visor (capas) — Ver datos por formulario o todo junto")

    visor_style = st.selectbox("Estilo de mapa (Visor)", MAP_STYLE_OPTIONS, index=0, key="visor_style")

    df_all = load_all_data()
    if df_all.empty:
        st.info("Aún no hay registros.")
    else:
        c1, c2, c3 = st.columns([0.45, 0.25, 0.30])
        with c1:
            layer = st.selectbox("Capa (formulario) a visualizar", options=["(Todos)"] + list(FORM_SHEETS.keys()), index=0)
        with c2:
            show_heat = st.checkbox("Mostrar HeatMap", value=True)
        with c3:
            show_clusters = st.checkbox("Mostrar clusters", value=True)

        dfv = df_all.copy()
        if layer != "(Todos)":
            dfv = dfv[dfv["form_label"] == layer]

        factores_unicos = sorted([f for f in dfv.get("factores", pd.Series([])).dropna().unique() if str(f).strip()])
        factor_sel = st.selectbox("Filtrar por factor (opcional)", options=["(Todos)"] + factores_unicos, index=0)
        if factor_sel != "(Todos)" and "factores" in dfv.columns:
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

            form_label = r.get("form_label", "")
            factor = r.get("factores", "")
            color = FACTOR_COLORS.get(factor, "#2dd4bf") if factor in FACTOR_COLORS else "#2dd4bf"

            if form_label == FORM1_TITLE:
                estructuras = []
                for i in range(1, 12):
                    v = str(r.get(f"estructura_{i}", "")).strip()
                    if v and v.lower() != "nan":
                        estructuras.append(v)
                estructuras_txt = "<br>".join([f"• {x}" for x in estructuras]) if estructuras else "(sin estructuras)"
                popup = (
                    f"<b>Formulario:</b> {FORM1_TITLE}<br>"
                    f"<b>Provincia:</b> {r.get('provincia','')}<br>"
                    f"<b>Cantón:</b> {r.get('canton','')}<br>"
                    f"<b>Barrio:</b> {r.get('barrio','')}<br>"
                    f"<b>Estructuras:</b><br>{estructuras_txt}<br>"
                    f"<b>Fecha:</b> {r.get('date','')}<br>"
                    f"<b>Maps:</b> <a href='{r.get('maps_link','')}' target='_blank'>Abrir</a>"
                )
            else:
                popup = (
                    f"<b>Formulario:</b> {form_label}<br>"
                    f"<b>Fecha:</b> {r.get('date','')}<br>"
                    f"<b>Barrio:</b> {r.get('barrio','')}<br>"
                    f"<b>Factor:</b> {factor}<br>"
                    f"<b>Delitos:</b> {r.get('delitos_relacionados','')}<br>"
                    f"<b>Estructura:</b> {r.get('ligado_estructura','')} {r.get('nombre_estructura','')}<br>"
                    f"<b>Obs:</b> {r.get('observaciones','')}<br>"
                    f"<b>Maps:</b> <a href='{r.get('maps_link','')}' target='_blank'>Abrir</a>"
                )

            jlat = float(lat) + _jitter(idx)
            jlng = float(lng) + _jitter(idx + 101)

            folium.Marker(
                [jlat, jlng],
                icon=make_pin_icon(color),
                popup=popup,
                pane="markers"
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

        st_folium(m, height=560, use_container_width=True, key="visor_map", returned_objects=[])

        if omitidos:
            st.caption(f"({omitidos} registro(s) omitidos por coordenadas inválidas)")

        st.divider()
        st.markdown("#### Tabla (según filtros)")
        if layer == FORM1_TITLE:
            show_cols = ["provincia","canton","barrio"] + [f"estructura_{i}" for i in range(1, 12)] + ["maps_link","date"]
        elif layer == "(Todos)":
            show_cols = ["form_label","date","barrio","factores","maps_link"]
        else:
            show_cols = ["form_label","date","barrio","factores","delitos_relacionados","ligado_estructura","nombre_estructura","observaciones","maps_link"]

        show_cols = [c for c in show_cols if c in dfv.columns]
        show_df = dfv[show_cols].copy()
        st.dataframe(show_df, use_container_width=True)

        st.download_button(
            "⬇️ Descargar CSV (visor)",
            data=show_df.to_csv(index=False).encode("utf-8"),
            file_name="visor_formularios.csv",
            mime="text/csv"
        )

# ==========================================================
# GRÁFICAS (global)
# ==========================================================
with tabs[-1]:
    st.subheader("📊 Gráficas (Plus) — Resumen global con filtros")

    df_all = load_all_data()
    if df_all.empty:
        st.info("Aún no hay registros para graficar.")
    else:
        c1, c2, c3 = st.columns([0.35, 0.35, 0.30])
        with c1:
            layer = st.selectbox("Fuente (formulario)", options=["(Todos)"] + list(FORM_SHEETS.keys()), index=0, key="g_layer")
        with c2:
            factores_unicos = sorted([f for f in df_all.get("factores", pd.Series([])).dropna().unique() if str(f).strip()])
            factor_sel = st.selectbox("Factor (opcional)", options=["(Todos)"] + factores_unicos, index=0, key="g_factor")
        with c3:
            top_n = st.slider("Top N", 5, 25, 10, key="g_top")

        dfg = df_all.copy()
        if layer != "(Todos)":
            dfg = dfg[dfg["form_label"] == layer]
        if factor_sel != "(Todos)" and "factores" in dfg.columns:
            dfg = dfg[dfg["factores"] == factor_sel]

        if "date" in dfg.columns:
            dfg["date_dt"] = parse_date_safe(dfg["date"])
            min_d = dfg["date_dt"].min()
            max_d = dfg["date_dt"].max()
            if pd.notna(min_d) and pd.notna(max_d):
                r = st.date_input("Rango de fechas (opcional)", value=(min_d.date(), max_d.date()), key="g_date")
                if isinstance(r, tuple) and len(r) == 2:
                    d1 = pd.to_datetime(r[0])
                    d2 = pd.to_datetime(r[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
                    dfg = dfg[(dfg["date_dt"] >= d1) & (dfg["date_dt"] <= d2)]

        if dfg.empty:
            st.warning("No hay datos con esos filtros.")
        else:
            counts = (
                dfg["factores"].fillna("").replace("", pd.NA).dropna()
                .value_counts().head(top_n).reset_index()
            )
            counts.columns = ["categoria", "conteo"]

            fig_bar = px.bar(
                counts.sort_values("conteo", ascending=True),
                x="conteo", y="categoria", orientation="h", text="conteo",
                template="plotly_dark",
                title="Frecuencias (categoría / factor)"
            )
            fig_bar.update_traces(textposition="outside", cliponaxis=False)
            fig_bar.update_layout(height=520, margin=dict(l=10, r=10, t=60, b=10))
            st.plotly_chart(fig_bar, use_container_width=True)

            fig_donut = px.pie(
                counts, names="categoria", values="conteo", hole=0.6,
                template="plotly_dark", title="Distribución"
            )
            fig_donut.update_traces(textinfo="percent", textposition="inside")
            fig_donut.update_layout(height=520, margin=dict(l=10, r=10, t=60, b=10))
            st.plotly_chart(fig_donut, use_container_width=True)

            grp = dfg.groupby(["form_label", "factores"]).size().reset_index(name="conteo")
            fig_sun = px.sunburst(
                grp, path=["form_label", "factores"], values="conteo",
                template="plotly_dark", title="Capas: Formulario → Categoría/Factor"
            )
            fig_sun.update_layout(height=560, margin=dict(l=10, r=10, t=60, b=10))
            st.plotly_chart(fig_sun, use_container_width=True)

            st.divider()
            st.markdown("#### Datos base (según filtros)")
            st.dataframe(dfg.head(500), use_container_width=True)





