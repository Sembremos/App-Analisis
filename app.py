# ==========================================================
# PARTE 1/10
# Imports, configuración general y constantes globales
# ==========================================================

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import random, re, json
from urllib.request import urlopen

import gspread
from google.oauth2.service_account import Credentials

import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, LocateControl, HeatMap, BeautifyIcon

import plotly.express as px

# ---------- Config de Streamlit ----------
st.set_page_config(page_title="CR – Formularios + Visor + Gráficas", layout="wide")

# Zona horaria CR
TZ = ZoneInfo("America/Costa_Rica")

# ---------- Google Sheets (DB) ----------
SHEET_ID = "1pCUXSJ_hvQzpzBTaJ-h0ntcdhYwMTyWomxXMjmi7lyg"

# ---------- Tab 1 / Hoja 1 (Formulario 1) ----------
FORM1_TITLE = "Pandillas de trafico transnacional Costa Rica 2025"
FORM1_SHEET = FORM1_TITLE

# ---------- Formularios 2..5 (hojas separadas) ----------
FORM_SHEETS = {
    FORM1_TITLE: FORM1_SHEET,  # Form 1
    "Formulario 2": "Prueba_2",
    "Formulario 3": "Prueba_3",
    "Formulario 4": "Prueba_4",
    "Formulario 5": "Prueba_5",
}

# ---------- Esquema Formulario 1 ----------
FORM1_HEADERS = [
    "provincia", "canton", "barrio",
    "estructura_1", "estructura_2", "estructura_3", "estructura_4", "estructura_5",
    "estructura_6", "estructura_7", "estructura_8", "estructura_9", "estructura_10",
    "estructura_11",
    "maps_link", "date"
]

# ---------- Esquema Formularios 2..5 ----------
SURVEY_HEADERS = [
    "date", "barrio", "factores", "delitos_relacionados",
    "ligado_estructura", "nombre_estructura", "observaciones", "maps_link"
]

# ---------- Catálogo factores ----------
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

# Paleta para colorear factores (si querés usarla en puntos)
_PALETTE = [
    "#e41a1c","#377eb8","#4daf4a","#984ea3","#ff7f00","#ffff33",
    "#a65628","#f781bf","#999999","#1b9e77","#d95f02","#7570b3",
    "#e7298a","#66a61e","#e6ab02","#a6761d","#1f78b4","#b2df8a",
    "#fb9a99","#cab2d6","#fdbf6f","#b15928"
]
FACTOR_COLORS = {f: _PALETTE[i % len(_PALETTE)] for i, f in enumerate(FACTORES)}

# Icono tipo Google Maps (pin)
DEFAULT_PIN_ICON = "map-marker-alt"

# ---------- Config mapa general Costa Rica ----------
CR_CENTER = [9.7489, -83.7534]
CR_ZOOM = 8
MAP_STYLE_OPTIONS = ["Esri Satélite", "Base gris (Carto)", "OpenStreetMap", "Terreno (Stamen)"]

# ---------- GeoJSON (Provincias/Cantones) ----------
# Ojo: son fuentes públicas. Si cambian columnas, el código igual aguanta.
CR_PROVINCIAS_GEOJSON_URL = "https://raw.githubusercontent.com/maufonsecasdfg/costa-rica-geojson/main/costaricaprovincias.geojson"
CR_CANTONES_GEOJSON_URL   = "https://raw.githubusercontent.com/maufonsecasdfg/costa-rica-geojson/main/costaricacantones.geojson"
# ==========================================================
# PARTE 2/10
# Google Sheets: conexión + CRUD básico
# ==========================================================

@st.cache_resource(show_spinner=False)
def _client():
    """Crea cliente de gspread usando service account desde st.secrets."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

@st.cache_resource(show_spinner=False)
def _spreadsheet():
    """Abre el Spreadsheet por ID."""
    return _client().open_by_key(SHEET_ID)

def _get_or_create_ws(ws_name: str, headers: list):
    """
    Obtiene una hoja por nombre. Si no existe, la crea.
    Además asegura que el header (fila 1) tenga al menos las columnas esperadas.
    """
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
    """Devuelve el header actual de la hoja (fila 1)."""
    return [h.strip() for h in ws.row_values(1)]

def _split_factores(factores):
    """Convierte lista o string 'A|B' a lista limpia."""
    if isinstance(factores, list):
        return [x.strip() for x in factores if str(x).strip()]
    if isinstance(factores, str):
        return [s.strip() for s in factores.split("|") if s.strip()]
    return []

def append_row_generic(ws_name: str, headers: list, row_dict: dict):
    """Agrega una fila simple a la hoja, respetando el orden de columnas actual."""
    ws = _get_or_create_ws(ws_name, headers)
    cols = _headers(ws)
    ws.append_row([row_dict.get(c, "") for c in cols], value_input_option="USER_ENTERED")

def append_rows_one_per_factor(ws_name: str, data: dict):
    """
    Para Formularios 2..5:
    - si el usuario selecciona N factores, se crean N filas (1 por factor).
    """
    ws = _get_or_create_ws(ws_name, SURVEY_HEADERS)
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
    """
    Lee una hoja y crea DF.
    - Intenta extraer lat/lng desde maps_link (maps?q=lat,lng)
    """
    ws = _get_or_create_ws(ws_name, headers)
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=headers + ["lat", "lng", "source_form", "form_label"])

    df = pd.DataFrame(records)
    for c in headers:
        if c not in df.columns:
            df[c] = ""

    url_pat = re.compile(r"https?://.*maps\?q=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")
    lat_list, lng_list = [], []
    for v in df.get("maps_link", pd.Series([""] * len(df))):
        m = url_pat.search(str(v))
        lat_list.append(float(m.group(1)) if m else None)
        lng_list.append(float(m.group(2)) if m else None)

    df["lat"] = pd.to_numeric(lat_list, errors="coerce")
    df["lng"] = pd.to_numeric(lng_list, errors="coerce")
    df["source_form"] = ws_name
    return df
# ==========================================================
# PARTE 3/10
# MAPA: utilidades (tiles, iconos, panes, jitter) +
#       capas administrativas (Provincias/Cantones con hover)
#
# ✅ FIX 1: Evita AssertionError (Folium exige fields=list/tuple, nunca None)
# ✅ FIX 2: Tooltip muestra NOMBRE (string) y evita códigos numéricos (ej. 56)
# ✅ FIX 3: GeoJSON cacheado para reducir recargas
# ==========================================================

import math
import json
from urllib.request import urlopen

# ---------- Pequeño jitter para puntos (evita que se monten exactos) ----------
def _jitter(idx: int, base: float = 0.00008) -> float:
    random.seed(idx)
    return (random.random() - 0.5) * base

# ---------- Panes para controlar orden de capas ----------
def _add_panes(m):
    """
    admin: provincias/cantones (debajo)
    markers: puntos y clusters (arriba)
    heatmap: mapa de calor (encima de tiles, debajo/encima según z-index)
    """
    folium.map.CustomPane("admin", z_index=250).add_to(m)
    folium.map.CustomPane("markers", z_index=400).add_to(m)
    folium.map.CustomPane("heatmap", z_index=650).add_to(m)

# ---------- Tiles / estilos base ----------
def _add_tile_by_name(m, style_name: str):
    """
    Agrega el basemap según nombre.
    Nota: 'Esri Satélite' requiere attr sí o sí (Folium lo exige).
    """
    if style_name == "Esri Satélite":
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="Esri Satélite",
            overlay=False,
            control=True
        ).add_to(m)

    elif style_name == "Base gris (Carto)":
        folium.TileLayer(
            "CartoDB positron",
            name="Base gris (Carto)",
            overlay=False,
            control=True
        ).add_to(m)

    elif style_name == "OpenStreetMap":
        folium.TileLayer(
            "OpenStreetMap",
            name="OpenStreetMap",
            overlay=False,
            control=True
        ).add_to(m)

    elif style_name == "Terreno (Stamen)":
        folium.TileLayer(
            tiles="https://stamen-tiles.a.ssl.fastly.net/terrain/{z}/{x}/{y}.png",
            attr="Map tiles by Stamen Design, under CC BY 3.0. Data by OpenStreetMap, under ODbL.",
            name="Terreno (Stamen)",
            overlay=False,
            control=True
        ).add_to(m)

# ---------- Icono tipo pin (estilo Google) ----------
def make_pin_icon(color_hex: str):
    """
    Pin por defecto para marcadores.
    Requiere: from folium.plugins import BeautifyIcon
    """
    return BeautifyIcon(
        icon=DEFAULT_PIN_ICON,      # ej. "map-marker-alt"
        icon_shape="marker",
        background_color=color_hex,
        border_color="#111",
        text_color="#fff"
    )

# ---------- Cargar GeoJSON (cacheado) ----------
@st.cache_data(show_spinner=False)
def _load_geojson(url: str) -> dict:
    """
    Descarga GeoJSON una vez y lo guarda en cache.
    Esto reduce muchísimo las recargas y parpadeos.
    """
    with urlopen(url) as r:
        return json.loads(r.read().decode("utf-8"))

# ---------- Elegir el campo correcto para tooltip ----------
def _pick_prop_key(geojson: dict, candidates: list[str], prefer_text: bool = True):
    """
    Devuelve la key más adecuada dentro de 'properties' del primer feature.

    - candidates: lista de nombres posibles (por si el GeoJSON cambia)
    - prefer_text=True: evita seleccionar campos numéricos (códigos) como 56
      y prefiere strings (nombres tipo "San José", "Alajuela", etc.)

    ✅ IMPORTANTE:
    Folium exige que GeoJsonTooltip(fields=...) reciba SIEMPRE list/tuple,
    jamás None. Por eso esta función devuelve None solo si no hay props.
    """
    try:
        props = (geojson.get("features", [{}])[0].get("properties", {}) or {})
        if not props:
            return None

        # 1) Intentar candidatos (en orden)
        for k in candidates:
            if k in props and props.get(k) is not None:
                v = props.get(k)
                if prefer_text and isinstance(v, (int, float)):
                    continue
                return k

        # 2) Si prefer_text: buscar el primer string “decente”
        if prefer_text:
            for k, v in props.items():
                if isinstance(v, str) and len(v.strip()) >= 3:
                    return k

        # 3) Último fallback (lo que exista)
        return list(props.keys())[0]

    except Exception:
        return None

# ---------- Capas administrativas (Provincias / Cantones) ----------
def add_admin_layers(m: folium.Map, show_provincias: bool = True, show_cantones: bool = True):
    """
    Agrega GeoJson de provincias y cantones con hover (tooltip).

    ✅ FIX: Nunca pasamos fields=None a GeoJsonTooltip (evita AssertionError).
    ✅ Además: Preferimos campos string (NOMBRES) para que no salga "Cantón: 56".
    """

    # ===== Provincias =====
    if show_provincias:
        prov = _load_geojson(CR_PROVINCIAS_GEOJSON_URL)

        # Preferimos nombres (strings)
        prov_key = _pick_prop_key(
            prov,
            [
                "NOM_PROV", "nom_prov",
                "provincia", "Provincia", "PROVINCIA",
                "name", "NAME",
                "nombre", "NOMBRE"
            ],
            prefer_text=True
        )

        gj = folium.GeoJson(
            prov,
            name="Provincias (hover)",
            pane="admin",
            style_function=lambda f: {"color": "#00E5FF", "weight": 2, "fillOpacity": 0.0},
            highlight_function=lambda f: {"weight": 4, "color": "#00E5FF"},
        )

        # ✅ Solo si existe key (y fields siempre list)
        if prov_key:
            gj.add_child(
                folium.GeoJsonTooltip(
                    fields=[prov_key],
                    aliases=["Provincia:"],
                    sticky=True
                )
            )

        gj.add_to(m)

    # ===== Cantones =====
    if show_cantones:
        cant = _load_geojson(CR_CANTONES_GEOJSON_URL)

        # Preferimos nombres (strings)
        canton_key = _pick_prop_key(
            cant,
            [
                "NOM_CANT", "nom_cant",
                "CANTON_NOM", "canton_name",
                "canton", "cantón", "CANTON", "Canton",
                "name", "NAME",
                "nombre", "NOMBRE"
            ],
            prefer_text=True
        )

        gj2 = folium.GeoJson(
            cant,
            name="Cantones (hover)",
            pane="admin",
            style_function=lambda f: {"color": "#FFFFFF", "weight": 1, "fillOpacity": 0.0},
            highlight_function=lambda f: {"weight": 3, "color": "#FFFFFF"},
        )

        # ✅ Solo si existe key (y fields siempre list)
        if canton_key:
            gj2.add_child(
                folium.GeoJsonTooltip(
                    fields=[canton_key],
                    aliases=["Cantón:"],
                    sticky=True
                )
            )

        gj2.add_to(m)

# ==========================================================
# PARTE 4/10
# Utilidades para Formulario 1 (estructuras) + carga general
# ==========================================================

def extract_all_structures(df1: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza Form1:
    - Por cada fila (punto) puede haber estructura_1..estructura_11
    - Devuelve un DF con UNA estructura por fila (para dashboard).
    """
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
    """Parsea fecha dd-mm-YYYY si existe."""
    return pd.to_datetime(series, errors="coerce", dayfirst=True)

def load_all_data() -> pd.DataFrame:
    """
    Carga TODO para visor y gráficas globales:
    - Form1 (estructura)
    - Forms 2..5 (encuesta)
    """
    dfs = []

    df1 = read_df_generic(FORM1_SHEET, FORM1_HEADERS).copy()
    df1["form_label"] = FORM1_TITLE
    df1["factores"] = "(Form1 – estructuras)"  # para compatibilidad en visor
    dfs.append(df1)

    for label in ["Formulario 2", "Formulario 3", "Formulario 4", "Formulario 5"]:
        ws_name = FORM_SHEETS[label]
        df = read_df_generic(ws_name, SURVEY_HEADERS).copy()
        df["form_label"] = label
        dfs.append(df)

    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
# ==========================================================
# PARTE 5/10
# UI: Título + Tabs
# ==========================================================

st.title("📍 Costa Rica — Formularios + Visor + Gráficas")
st.caption("Mapas con nombres de provincias y cantones (hover) para ubicarte mejor.")

tab_labels = list(FORM_SHEETS.keys()) + ["Visor (capas)", "📊 Gráficas"]
tabs = st.tabs(tab_labels)
# ==========================================================
# PARTE 6/10
# TAB 1 — Formulario 1 (Provincia/Cantón/Barrio + Estructuras)
# ==========================================================

with tabs[0]:
    st.subheader(f"{FORM1_TITLE} — Hoja: {FORM1_SHEET}")

    style = st.selectbox("Estilo de mapa", MAP_STYLE_OPTIONS, index=0, key="style_form1")
    show_prov = st.checkbox("Mostrar Provincias (hover)", value=True, key="form1_prov")
    show_cant = st.checkbox("Mostrar Cantones (hover)", value=True, key="form1_cant")

    left, right = st.columns([0.58, 0.42], gap="large")

    # ---------- Mapa ----------
    with left:
        st.markdown("### Selecciona un punto en el mapa")
        st.caption("Pasa el mouse sobre un polígono para ver Provincia/Cantón.")

        key_clicked = "clicked_form1"
        clicked = st.session_state.get(key_clicked) or {}
        center = [clicked.get("lat", CR_CENTER[0]), clicked.get("lng", CR_CENTER[1])]

        m = folium.Map(location=center, zoom_start=CR_ZOOM, control_scale=True, tiles=None)
        _add_panes(m)

        # Siempre Esri satélite y opcional otro (si querés)
        _add_tile_by_name(m, "Esri Satélite")
        if style != "Esri Satélite":
            _add_tile_by_name(m, style)

        # ✅ Provincias/Cantones
        add_admin_layers(m, show_provincias=show_prov, show_cantones=show_cant)

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

    # ---------- Formulario ----------
    with right:
        st.markdown("### Formulario")
        with st.form("form_excel_1", clear_on_submit=True):
            provincia = st.text_input("Provincia *")
            canton = st.text_input("Cantón *")
            barrio = st.text_input("Barrio (opcional)")

            st.markdown("#### Estructuras / Pandillas (podés llenar varias)")
            e = [st.text_input(f"Estructura {i}") for i in range(1, 12)]

            submit = st.form_submit_button("Guardar en Google Sheets")

        if submit:
            errs = []
            if lat_val is None or lng_val is None:
                errs.append("Selecciona un **punto en el mapa**.")
            if not provincia.strip():
                errs.append("Provincia es requerida.")
            if not canton.strip():
                errs.append("Cantón es requerido.")
            if not any([str(x).strip() for x in e]):
                errs.append("Agrega al menos **una estructura/pandilla**.")

            if errs:
                st.error("• " + "\n• ".join(errs))
            else:
                maps_url = f"https://www.google.com/maps?q={lat_val},{lng_val}"
                row = {
                    "provincia": provincia.strip(),
                    "canton": canton.strip(),
                    "barrio": (barrio or "").strip(),
                    **{f"estructura_{i}": (e[i-1] or "").strip() for i in range(1, 12)},
                    "maps_link": maps_url,
                    "date": datetime.now(TZ).strftime("%d-%m-%Y"),
                }
                append_row_generic(FORM1_SHEET, FORM1_HEADERS, row)
                st.success("✅ Registro guardado en Formulario 1.")
                st.cache_data.clear()
                st.rerun()
# ==========================================================
# PARTE 7/10
# TAB 1 — Tabla + Dashboard (filtros provincia/cantón/pandilla)
# ==========================================================

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

    st.divider()
    st.markdown("## 📊 Dashboard (Formulario 1)")

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

        with colf3:
            f_pand = st.text_input("Buscar pandilla/estructura (contiene)", value="", key="f1_pand")

        if f_pand.strip():
            df_tmp = df_tmp[df_tmp["estructura"].str.contains(f_pand.strip(), case=False, na=False)]

        m1, m2, m3 = st.columns(3)
        m1.metric("Registros (estructuras)", len(df_tmp))
        m2.metric("Pandillas únicas", df_tmp["estructura"].nunique())
        m3.metric("Cantones en vista", df_tmp["canton"].nunique())

        top_n = st.slider("Top N pandillas", 5, 30, 10, key="f1_topn")
        counts = df_tmp["estructura"].value_counts().head(top_n).reset_index()
        counts.columns = ["estructura", "conteo"]

        fig_bar = px.bar(
            counts.sort_values("conteo", ascending=True),
            x="conteo", y="estructura", orientation="h", text="conteo",
            template="plotly_dark",
            title="Top pandillas/estructuras por frecuencia"
        )
        fig_bar.update_traces(textposition="outside", cliponaxis=False)
        fig_bar.update_layout(height=520, margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig_bar, use_container_width=True)

        fig_donut = px.pie(
            counts, names="estructura", values="conteo", hole=0.6,
            template="plotly_dark", title="Distribución (Top)"
        )
        fig_donut.update_traces(textinfo="percent", textposition="inside")
        fig_donut.update_layout(height=520, margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig_donut, use_container_width=True)

        grp = df_tmp.groupby(["provincia","canton","estructura"]).size().reset_index(name="conteo")
        fig_sun = px.sunburst(
            grp, path=["provincia","canton","estructura"], values="conteo",
            template="plotly_dark", title="Capas: Provincia → Cantón → Pandilla"
        )
        fig_sun.update_layout(height=600, margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig_sun, use_container_width=True)
# ==========================================================
# PARTE 8/10
# Formularios 2..5 (misma lógica, mismas capas admin, hojas separadas)
# ==========================================================

def render_survey_form(form_label: str):
    ws_name = FORM_SHEETS[form_label]
    st.subheader(f"{form_label} — Hoja: {ws_name}")

    style = st.selectbox("Estilo de mapa", MAP_STYLE_OPTIONS, index=0, key=f"style_{ws_name}")
    show_prov = st.checkbox("Mostrar Provincias (hover)", value=True, key=f"{ws_name}_prov")
    show_cant = st.checkbox("Mostrar Cantones (hover)", value=True, key=f"{ws_name}_cant")

    left, right = st.columns([0.58, 0.42], gap="large")

    with left:
        st.markdown("### Selecciona un punto en el mapa")
        st.caption("Pasa el mouse por un polígono para ver Provincia/Cantón.")

        key_clicked = f"clicked_{ws_name}"
        clicked = st.session_state.get(key_clicked) or {}
        center = [clicked.get("lat", CR_CENTER[0]), clicked.get("lng", CR_CENTER[1])]

        m = folium.Map(location=center, zoom_start=CR_ZOOM, control_scale=True, tiles=None)
        _add_panes(m)
        _add_tile_by_name(m, "Esri Satélite")
        if style != "Esri Satélite":
            _add_tile_by_name(m, style)

        add_admin_layers(m, show_provincias=show_prov, show_cantones=show_cant)
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
                errs.append("Selecciona al menos **un factor**.")
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
                n = append_rows_one_per_factor(ws_name, payload)
                st.success(f"✅ Guardado: {n} fila(s) (una por factor).")
                st.cache_data.clear()
                st.rerun()

    st.divider()
    df_local = read_df_generic(ws_name, SURVEY_HEADERS)
    st.dataframe(df_local[SURVEY_HEADERS].tail(200), use_container_width=True)


with tabs[1]:
    render_survey_form("Formulario 2")
with tabs[2]:
    render_survey_form("Formulario 3")
with tabs[3]:
    render_survey_form("Formulario 4")
with tabs[4]:
    render_survey_form("Formulario 5")
# ==========================================================
# PARTE 9/10
# Visor (capas): ver datos de 1,2,3,4,5 o todos juntos
# ==========================================================

with tabs[-2]:
    st.subheader("🗺️ Visor (capas) — por formulario o todo junto")

    visor_style = st.selectbox("Estilo de mapa (Visor)", MAP_STYLE_OPTIONS, index=0, key="visor_style")
    show_prov = st.checkbox("Mostrar Provincias (hover)", value=True, key="visor_prov")
    show_cant = st.checkbox("Mostrar Cantones (hover)", value=True, key="visor_cant")

    df_all = load_all_data()
    if df_all.empty:
        st.info("Aún no hay registros.")
    else:
        c1, c2, c3 = st.columns([0.45, 0.25, 0.30])
        with c1:
            layer = st.selectbox("Capa (formulario)", options=["(Todos)"] + list(FORM_SHEETS.keys()), index=0)
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

        # ✅ Provincias/Cantones
        add_admin_layers(m, show_provincias=show_prov, show_cantones=show_cant)

        LocateControl(auto_start=False).add_to(m)
        m.get_root().html.add_child(folium.Element(_legend_html()))

        group = (MarkerCluster(name="Marcadores", overlay=True, control=True, pane="markers")
                 if show_clusters else folium.FeatureGroup(name="Marcadores", overlay=True, control=True))
        group.add_to(m)

        heat_points, idx, omitidos = [], 0, 0

        for _, r in dfv.iterrows():
            lat, lng = r.get("lat"), r.get("lng")
            if pd.isna(lat) or pd.isna(lng):
                omitidos += 1
                continue

            form_label = r.get("form_label", "")
            factor = r.get("factores", "")
            color = FACTOR_COLORS.get(factor, "#2dd4bf") if factor in FACTOR_COLORS else "#2dd4bf"

            # Popup (Form1 distinto)
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
            HeatMap(
                heat_points,
                radius=18, blur=22, max_zoom=16, min_opacity=0.25,
                gradient={0.2: "pink", 0.5: "red", 1.0: "darkred"}
            ).add_to(folium.FeatureGroup(name="Mapa de calor", overlay=True, control=True, pane="heatmap").add_to(m))

        folium.LayerControl(collapsed=False).add_to(m)

        # ✅ IMPORTANTÍSIMO: returned_objects=[] reduce parpadeo / recargas
        st_folium(m, height=560, use_container_width=True, key="visor_map", returned_objects=[])

        if omitidos:
            st.caption(f"({omitidos} registro(s) omitidos por coordenadas inválidas)")

        st.divider()
        st.markdown("#### Tabla (según filtros)")
        cols_show = [c for c in dfv.columns if c in (["form_label","date","barrio","factores","maps_link","provincia","canton"])]
        st.dataframe(dfv[cols_show].tail(500), use_container_width=True)
# ==========================================================
# PARTE 10/10
# Gráficas globales (PLUS) + requirements
# ==========================================================

with tabs[-1]:
    st.subheader("📊 Gráficas globales (Plus)")
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




