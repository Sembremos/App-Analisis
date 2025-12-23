# -*- coding: utf-8 -*-
# Streamlit — 5 Páginas (5 hojas) + Visor (capas) + Gráficas — Google Sheets como DB
# ✅ Página 1: Provincia, Cantón, Distrito (opcional) + Estructuras (1..11) + mapa
# ✅ Página 2: CPC (Beneficiaries, Canton, Community Prevention Centers) + mapa
# ✅ Página 3: Empleabilidad (Canton, Cursos, Matriculadas, Egresadas, Sexo egresadas) + mapa
# ✅ Página 4: Bandas municipales (provincia, Canton, Nombre banda, Beneficiarios) + mapa
# ✅ Página 5: Factores (provincia/canton/distrito + factores + obs + mapa)
# ✅ CRUD (editar/eliminar) en todas las páginas
# ✅ Cantones SIEMPRE despliegan: Provincia/Cantón FUERA del st.form (Streamlit no refresca dentro)
# ✅ Pines con color por provincia
# ✅ Gráficas SOLO en pestaña 📊 Gráficas (barras/donut/sunburst) por página
# ✅ Tablas sin índice (hide_index)

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import random, re, uuid

import gspread
from google.oauth2.service_account import Credentials

import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, LocateControl, HeatMap, BeautifyIcon

import plotly.express as px

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(page_title="CR – Páginas + Visor + Gráficas", layout="wide")
TZ = ZoneInfo("America/Costa_Rica")

SHEET_ID = "1pCUXSJ_hvQzpzBTaJ-h0ntcdhYwMTyWomxXMjmi7lyg"

# ==========================================================
# CATÁLOGO PROVINCIAS / CANTONES (precargado)
# ==========================================================
PROV_CANTONES = {
    "San José": [
        "San José","Escazú","Desamparados","Puriscal","Tarrazú","Aserrí","Mora","Goicoechea",
        "Santa Ana","Alajuelita","Vásquez de Coronado","Acosta","Tibás","Moravia","Montes de Oca",
        "Turrubares","Dota","Curridabat","Pérez Zeledón","León Cortés Castro"
    ],
    "Alajuela": [
        "Alajuela","San Ramón","Grecia","San Mateo","Atenas","Naranjo","Palmares","Poás",
        "Orotina","San Carlos","Zarcero","Valverde Vega","Upala","Los Chiles","Guatuso","Río Cuarto"
    ],
    "Cartago": [
        "Cartago","Paraíso","La Unión","Jiménez","Turrialba","Alvarado","Oreamuno","El Guarco"
    ],
    "Heredia": [
        "Heredia","Barva","Santo Domingo","Santa Bárbara","San Rafael","San Isidro","Belén","Flores",
        "San Pablo","Sarapiquí"
    ],
    "Guanacaste": [
        "Liberia","Nicoya","Santa Cruz","Bagaces","Carrillo","Cañas","Abangares","Tilarán",
        "Nandayure","La Cruz","Hojancha"
    ],
    "Puntarenas": [
        "Puntarenas","Esparza","Buenos Aires","Montes de Oro","Osa","Quepos","Golfito","Coto Brus",
        "Parrita","Corredores","Garabito","Monteverde","Puerto Jiménez"
    ],
    "Limón": [
        "Limón","Pococí","Siquirres","Talamanca","Matina","Guácimo"
    ],
}
PROVINCIAS = list(PROV_CANTONES.keys())

# Pines por provincia
PROV_COLORS = {
    "San José": "#2563eb",
    "Alajuela": "#16a34a",
    "Cartago": "#dc2626",
    "Heredia": "#7c3aed",
    "Guanacaste": "#f59e0b",
    "Puntarenas": "#0ea5e9",
    "Limón": "#db2777",
}
DEFAULT_PROV_COLOR = "#2dd4bf"

def color_by_provincia(prov: str) -> str:
    prov = (prov or "").strip()
    return PROV_COLORS.get(prov, DEFAULT_PROV_COLOR)

# ==========================================================
# NOMBRES DE PÁGINAS / HOJAS
# ==========================================================
P1_TITLE = "Pandillas de trafico transnacional Costa Rica 2025"   # Página 1
P2_TITLE = "Community Prevention Centers"                         # Página 2
P3_TITLE = "Programa de empleabilidad"                            # Página 3
P4_TITLE = "Bandas municipales"                                   # Página 4
P5_TITLE = "Formulario 5"                                         # Página 5

FORM_SHEETS = {
    P1_TITLE: P1_TITLE,
    P2_TITLE: P2_TITLE,
    P3_TITLE: P3_TITLE,
    P4_TITLE: P4_TITLE,
    P5_TITLE: "Prueba_5",
}

# ==========================================================
# HEADERS (con id para CRUD + maps_link/date para mapa)
# ==========================================================
P1_HEADERS = [
    "id",
    "provincia",
    "canton",
    "distrito",
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

P2_HEADERS = [
    "id",
    "Beneficiaries",
    "Canton",
    "Community Prevention Centers",
    "maps_link",
    "date",
]

P3_HEADERS = [
    "id",
    "Canton",
    "Cursos Brindados",
    "Cantidad de personas matriculadas",
    "Cantidad de personas egresadas",
    "sexo por personas egresadas",
    "maps_link",
    "date",
]

P4_HEADERS = [
    "id",
    "provincia",
    "Canton",
    "Nombre de club o banda",
    "Beneficiarios",
    "maps_link",
    "date",
]

P5_HEADERS = [
    "id",
    "provincia",
    "canton",
    "distrito",
    "factores",
    "delitos_relacionados",
    "ligado_estructura",
    "nombre_estructura",
    "observaciones",
    "maps_link",
    "date",
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
DEFAULT_PIN_ICON = "map-marker-alt"

# ==========================================================
# GOOGLE SHEETS — conexión + CRUD base
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

@st.cache_data(ttl=25, show_spinner=False)
def read_df_generic(ws_name: str, headers: list) -> pd.DataFrame:
    ws = _get_or_create_ws(ws_name, headers)
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=headers + ["lat", "lng", "form_label"])

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
    df["form_label"] = ws_name
    return df

def append_row_generic(ws_name: str, headers: list, row_dict: dict):
    ws = _get_or_create_ws(ws_name, headers)
    cols = _headers(ws)
    ws.append_row([row_dict.get(c, "") for c in cols], value_input_option="USER_ENTERED")

def _find_row_by_id(ws, record_id: str):
    cols = _headers(ws)
    if "id" not in cols:
        return None
    id_col = cols.index("id") + 1
    col_vals = ws.col_values(id_col)
    for idx, v in enumerate(col_vals[1:], start=2):
        if str(v).strip() == str(record_id).strip():
            return idx
    return None

def update_row_by_id(ws_name: str, headers: list, record_id: str, updated: dict):
    ws = _get_or_create_ws(ws_name, headers)
    row_num = _find_row_by_id(ws, record_id)
    if not row_num:
        raise ValueError("No se encontró el ID a editar.")
    cols = _headers(ws)
    values = [updated.get(c, "") for c in cols]
    ws.update(f"A{row_num}:{gspread.utils.rowcol_to_a1(row_num, len(cols))}", [values])

def delete_row_by_id(ws_name: str, headers: list, record_id: str):
    ws = _get_or_create_ws(ws_name, headers)
    row_num = _find_row_by_id(ws, record_id)
    if not row_num:
        raise ValueError("No se encontró el ID a eliminar.")
    ws.delete_rows(row_num)

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

def render_pick_map(map_key: str, style_key: str, clicked_key: str):
    style = st.selectbox("Estilo de mapa", MAP_STYLE_OPTIONS, index=0, key=style_key)

    clicked = st.session_state.get(clicked_key) or {}
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
    map_ret = st_folium(m, height=520, use_container_width=True, key=map_key)

    if map_ret and map_ret.get("last_clicked"):
        st.session_state[clicked_key] = {
            "lat": round(map_ret["last_clicked"]["lat"], 6),
            "lng": round(map_ret["last_clicked"]["lng"], 6),
        }
        clicked = st.session_state[clicked_key]

    cols = st.columns(3)
    lat_val, lng_val = clicked.get("lat"), clicked.get("lng")
    cols[0].metric("Latitud", lat_val if lat_val is not None else "—")
    cols[1].metric("Longitud", lng_val if lng_val is not None else "—")
    if cols[2].button("Limpiar selección", key=f"clear_{clicked_key}"):
        st.session_state.pop(clicked_key, None)
        st.rerun()

    return lat_val, lng_val

# ==========================================================
# ✅ SELECTOR Provincia -> Cantón (OBLIGATORIO fuera del st.form)
# ==========================================================
def ui_select_prov_canton(key_prefix: str):
    k_prov = f"{key_prefix}_prov"
    k_cant = f"{key_prefix}_canton"
    k_last = f"{key_prefix}_last_prov"

    prov_opts = ["(Seleccione)"] + PROVINCIAS
    prov = st.selectbox("Provincia *", options=prov_opts, index=0, key=k_prov)
    prov = (prov or "").strip()

    last_prov = st.session_state.get(k_last)
    if last_prov is None:
        st.session_state[k_last] = prov
    elif last_prov != prov:
        st.session_state[k_cant] = "(Seleccione)"
        st.session_state[k_last] = prov

    cantones = PROV_CANTONES.get(prov, []) if prov != "(Seleccione)" else []
    cant_opts = ["(Seleccione)"] + cantones

    cur = st.session_state.get(k_cant, "(Seleccione)")
    if cur not in cant_opts:
        st.session_state[k_cant] = "(Seleccione)"

    canton = st.selectbox(
        "Cantón *",
        options=cant_opts,
        index=cant_opts.index(st.session_state.get(k_cant, "(Seleccione)")),
        key=k_cant
    )
    return prov, canton

# ==========================================================
# HELPERS UI
# ==========================================================
def hide_df_index(df: pd.DataFrame):
    st.dataframe(df, use_container_width=True, hide_index=True)

def crud_block(ws_name: str, headers: list, df: pd.DataFrame, label: str, preview_cols: list):
    st.markdown(f"### 🛠️ CRUD — {label}")

    if df.empty:
        st.info("Aún no hay registros para editar/eliminar.")
        return

    if "id" not in df.columns:
        st.warning("No existe columna 'id' en la hoja.")
        return

    show_cols = [c for c in preview_cols if c in df.columns]
    view_df = df[show_cols].copy()

    def _label_row(r):
        parts = []
        for c in [
            "provincia","canton","distrito","Canton","date",
            "Nombre de club o banda","Cursos Brindados","Community Prevention Centers"
        ]:
            if c in r and str(r.get(c,"")).strip():
                parts.append(str(r.get(c)))
        return " | ".join(parts)[:160] if parts else "registro"

    options = [
        (str(r["id"]), f"{str(r['id'])} — {_label_row(r)}")
        for _, r in df.iterrows()
        if str(r.get("id","")).strip()
    ]

    if not options:
        st.info("No hay IDs válidos aún.")
        return

    selected = st.selectbox(
        "Selecciona un registro",
        options=options,
        format_func=lambda x: x[1],
        key=f"crud_sel_{ws_name}"
    )
    record_id = selected[0]
    row = df[df["id"].astype(str) == str(record_id)].iloc[0].to_dict()

    cA, cB = st.columns([0.7, 0.3], gap="large")
    with cA:
        with st.form(f"edit_form_{ws_name}", clear_on_submit=False):
            updated = dict(row)
            for h in headers:
                if h == "id":
                    continue
                if h in ["maps_link","date"]:
                    updated[h] = st.text_input(h, value=str(row.get(h,"")), disabled=True)
                elif h in ["Beneficiaries","Beneficiarios","Cantidad de personas matriculadas","Cantidad de personas egresadas"]:
                    try:
                        v0 = float(row.get(h) or 0)
                    except Exception:
                        v0 = 0.0
                    updated[h] = st.number_input(h, value=v0, step=1.0)
                    if float(updated[h]).is_integer():
                        updated[h] = int(updated[h])
                else:
                    updated[h] = st.text_input(h, value=str(row.get(h,"")))

            do_update = st.form_submit_button("💾 Guardar cambios")

        if do_update:
            try:
                updated["id"] = record_id
                update_row_by_id(ws_name, headers, record_id, updated)
                st.success("✅ Registro actualizado.")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al actualizar: {e}")

    with cB:
        st.markdown("**Eliminar**")
        if st.button("🗑️ Eliminar este registro", key=f"del_{ws_name}"):
            try:
                delete_row_by_id(ws_name, headers, record_id)
                st.success("✅ Registro eliminado.")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al eliminar: {e}")

    st.markdown("**Vista rápida (sin índice):**")
    hide_df_index(view_df.tail(200))

# ==========================================================
# LOAD ALL DATA
# ==========================================================
def load_all_data() -> pd.DataFrame:
    dfs = []

    df1 = read_df_generic(P1_TITLE, P1_HEADERS).copy()
    df1["page"] = "Página 1"
    dfs.append(df1)

    df2 = read_df_generic(P2_TITLE, P2_HEADERS).copy()
    df2["page"] = "Página 2"
    dfs.append(df2)

    df3 = read_df_generic(P3_TITLE, P3_HEADERS).copy()
    df3["page"] = "Página 3"
    dfs.append(df3)

    df4 = read_df_generic(P4_TITLE, P4_HEADERS).copy()
    df4["page"] = "Página 4"
    dfs.append(df4)

    df5 = read_df_generic(FORM_SHEETS[P5_TITLE], P5_HEADERS).copy()
    df5["page"] = "Página 5"
    dfs.append(df5)

    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# ==========================================================
# PEQUEÑAS UTILIDADES PARA GRÁFICAS
# ==========================================================
def split_pipe_values(s: str):
    if not isinstance(s, str):
        return []
    return [x.strip() for x in s.split("|") if x.strip()]

def safe_series(df: pd.DataFrame, col: str):
    if col not in df.columns:
        return pd.Series([], dtype=str)
    return df[col]

def parse_prov_from_canton_field(val: str):
    # Para P2/P3 que guardan "Provincia / Cantón"
    if not isinstance(val, str):
        return "", ""
    parts = [p.strip() for p in val.split("/") if p.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return "", val.strip()

# ==========================================================
# UI
# ==========================================================
st.title("📍 Costa Rica — Páginas + Visor + Gráficas")
st.caption("Cantones funcionan: Provincia/Cantón están fuera del form (Streamlit). CRUD en todas las páginas. Gráficas solo en 📊 Gráficas.")

tabs = st.tabs([P1_TITLE, P2_TITLE, P3_TITLE, P4_TITLE, P5_TITLE, "Visor (capas)", "📊 Gráficas"])

# ==========================================================
# PÁGINA 1
# ==========================================================
with tabs[0]:
    st.subheader(f"{P1_TITLE} — Hoja: {P1_TITLE}")

    left, right = st.columns([0.58, 0.42], gap="large")

    with left:
        st.markdown("### Selecciona un punto en el mapa")
        lat_val, lng_val = render_pick_map("map_p1", "style_p1", "clicked_p1")

    with right:
        st.markdown("### Formulario (Provincia / Cantón / Distrito + estructuras)")

        # ✅ FUERA del form
        prov, canton = ui_select_prov_canton("p1")

        with st.form("form_p1", clear_on_submit=True):
            st.caption(f"Seleccionado: **{prov} / {canton}**")
            distrito = st.text_input("Distrito (opcional)")

            st.markdown("#### Estructuras / Pandillas (podés llenar varias)")
            e = [st.text_input(f"Estructura {i}") for i in range(1, 12)]
            submit = st.form_submit_button("Guardar en Google Sheets")

        if submit:
            errs = []
            if lat_val is None or lng_val is None:
                errs.append("Selecciona un **punto en el mapa**.")
            if prov == "(Seleccione)":
                errs.append("Provincia es requerida.")
            if canton == "(Seleccione)":
                errs.append("Cantón es requerido.")
            if not any([str(x).strip() for x in e]):
                errs.append("Agrega al menos **una estructura/pandilla**.")
            if errs:
                st.error("• " + "\n• ".join(errs))
            else:
                maps_url = f"https://www.google.com/maps?q={lat_val},{lng_val}"
                row = {
                    "id": str(uuid.uuid4()),
                    "provincia": prov,
                    "canton": canton,
                    "distrito": (distrito or "").strip(),
                    **{f"estructura_{i}": (e[i-1] or "").strip() for i in range(1, 12)},
                    "maps_link": maps_url,
                    "date": datetime.now(TZ).strftime("%d-%m-%Y"),
                }
                append_row_generic(P1_TITLE, P1_HEADERS, row)
                st.success("✅ Registro guardado (Página 1).")
                st.cache_data.clear()
                st.rerun()

    st.divider()
    st.markdown("## 📋 Datos registrados (Página 1)")
    df1 = read_df_generic(P1_TITLE, P1_HEADERS)
    hide_df_index(df1[[c for c in P1_HEADERS if c in df1.columns]].tail(300))

    st.download_button(
        "⬇️ Descargar CSV (Página 1)",
        data=df1[[c for c in P1_HEADERS if c in df1.columns]].to_csv(index=False).encode("utf-8"),
        file_name=f"{P1_TITLE}.csv",
        mime="text/csv",
        key="dl_p1"
    )

    st.divider()
    crud_block(
        ws_name=P1_TITLE,
        headers=P1_HEADERS,
        df=df1,
        label="Página 1 (Pandillas/Estructuras)",
        preview_cols=["id","provincia","canton","distrito","date"] + [f"estructura_{i}" for i in range(1,12)] + ["maps_link"]
    )

# ==========================================================
# PÁGINA 2 — CPC
# ==========================================================
with tabs[1]:
    st.subheader(f"{P2_TITLE} — Hoja: {P2_TITLE}")

    left, right = st.columns([0.58, 0.42], gap="large")

    with left:
        st.markdown("### Selecciona un punto en el mapa")
        lat_val, lng_val = render_pick_map("map_p2", "style_p2", "clicked_p2")

    with right:
        st.markdown("### Formulario (CPC)")

        # ✅ FUERA del form
        prov, canton = ui_select_prov_canton("p2")

        with st.form("form_p2", clear_on_submit=True):
            st.caption(f"Seleccionado: **{prov} / {canton}**")
            beneficiaries = st.number_input("Beneficiaries", min_value=0, step=1)
            cpc_name = st.text_input("Community Prevention Centers *")
            submit = st.form_submit_button("Guardar en Google Sheets")

        if submit:
            errs = []
            if lat_val is None or lng_val is None:
                errs.append("Selecciona un **punto en el mapa**.")
            if prov == "(Seleccione)":
                errs.append("Provincia es requerida.")
            if canton == "(Seleccione)":
                errs.append("Cantón es requerido.")
            if not cpc_name.strip():
                errs.append("Community Prevention Centers es requerido.")
            if errs:
                st.error("• " + "\n• ".join(errs))
            else:
                maps_url = f"https://www.google.com/maps?q={lat_val},{lng_val}"
                row = {
                    "id": str(uuid.uuid4()),
                    "Beneficiaries": int(beneficiaries),
                    "Canton": f"{prov} / {canton}",
                    "Community Prevention Centers": cpc_name.strip(),
                    "maps_link": maps_url,
                    "date": datetime.now(TZ).strftime("%d-%m-%Y"),
                }
                append_row_generic(P2_TITLE, P2_HEADERS, row)
                st.success("✅ Registro guardado (Página 2).")
                st.cache_data.clear()
                st.rerun()

    st.divider()
    st.markdown("## 📋 Datos registrados (Página 2)")
    df2 = read_df_generic(P2_TITLE, P2_HEADERS)
    hide_df_index(df2[[c for c in P2_HEADERS if c in df2.columns]].tail(300))

    st.download_button(
        "⬇️ Descargar CSV (Página 2)",
        data=df2[[c for c in P2_HEADERS if c in df2.columns]].to_csv(index=False).encode("utf-8"),
        file_name=f"{P2_TITLE}.csv",
        mime="text/csv",
        key="dl_p2"
    )

    st.divider()
    crud_block(
        ws_name=P2_TITLE,
        headers=P2_HEADERS,
        df=df2,
        label="Página 2 (CPC)",
        preview_cols=["id","Canton","Community Prevention Centers","Beneficiaries","maps_link","date"]
    )

# ==========================================================
# PÁGINA 3 — EMPLEABILIDAD
# ==========================================================
with tabs[2]:
    st.subheader(f"{P3_TITLE} — Hoja: {P3_TITLE}")

    left, right = st.columns([0.58, 0.42], gap="large")

    with left:
        st.markdown("### Selecciona un punto en el mapa")
        lat_val, lng_val = render_pick_map("map_p3", "style_p3", "clicked_p3")

    with right:
        st.markdown("### Formulario (Empleabilidad)")

        # ✅ FUERA del form
        prov, canton = ui_select_prov_canton("p3")

        with st.form("form_p3", clear_on_submit=True):
            st.caption(f"Seleccionado: **{prov} / {canton}**")
            cursos = st.text_area("Cursos Brindados *", height=90)
            matric = st.number_input("Cantidad de personas matriculadas", min_value=0, step=1)
            egres = st.number_input("Cantidad de personas egresadas", min_value=0, step=1)
            sexo = st.text_input("sexo por personas egresadas (ej: H: 36 / M: 59)")
            submit = st.form_submit_button("Guardar en Google Sheets")

        if submit:
            errs = []
            if lat_val is None or lng_val is None:
                errs.append("Selecciona un **punto en el mapa**.")
            if prov == "(Seleccione)":
                errs.append("Provincia es requerida.")
            if canton == "(Seleccione)":
                errs.append("Cantón es requerido.")
            if not cursos.strip():
                errs.append("Cursos Brindados es requerido.")
            if errs:
                st.error("• " + "\n• ".join(errs))
            else:
                maps_url = f"https://www.google.com/maps?q={lat_val},{lng_val}"
                row = {
                    "id": str(uuid.uuid4()),
                    "Canton": f"{prov} / {canton}",
                    "Cursos Brindados": cursos.strip(),
                    "Cantidad de personas matriculadas": int(matric),
                    "Cantidad de personas egresadas": int(egres),
                    "sexo por personas egresadas": (sexo or "").strip(),
                    "maps_link": maps_url,
                    "date": datetime.now(TZ).strftime("%d-%m-%Y"),
                }
                append_row_generic(P3_TITLE, P3_HEADERS, row)
                st.success("✅ Registro guardado (Página 3).")
                st.cache_data.clear()
                st.rerun()

    st.divider()
    st.markdown("## 📋 Datos registrados (Página 3)")
    df3 = read_df_generic(P3_TITLE, P3_HEADERS)
    hide_df_index(df3[[c for c in P3_HEADERS if c in df3.columns]].tail(300))

    st.download_button(
        "⬇️ Descargar CSV (Página 3)",
        data=df3[[c for c in P3_HEADERS if c in df3.columns]].to_csv(index=False).encode("utf-8"),
        file_name=f"{P3_TITLE}.csv",
        mime="text/csv",
        key="dl_p3"
    )

    st.divider()
    crud_block(
        ws_name=P3_TITLE,
        headers=P3_HEADERS,
        df=df3,
        label="Página 3 (Empleabilidad)",
        preview_cols=["id","Canton","Cursos Brindados","Cantidad de personas matriculadas","Cantidad de personas egresadas","sexo por personas egresadas","maps_link","date"]
    )

# ==========================================================
# PÁGINA 4 — BANDAS MUNICIPALES
# ==========================================================
with tabs[3]:
    st.subheader(f"{P4_TITLE} — Hoja: {P4_TITLE}")

    left, right = st.columns([0.58, 0.42], gap="large")

    with left:
        st.markdown("### Selecciona un punto en el mapa")
        lat_val, lng_val = render_pick_map("map_p4", "style_p4", "clicked_p4")

    with right:
        st.markdown("### Formulario (Bandas municipales)")

        # ✅ FUERA del form
        prov, canton = ui_select_prov_canton("p4")

        with st.form("form_p4", clear_on_submit=True):
            st.caption(f"Seleccionado: **{prov} / {canton}**")
            nombre = st.text_input("Nombre de club o banda *")
            beneficiarios = st.number_input("Beneficiarios", min_value=0, step=1)
            submit = st.form_submit_button("Guardar en Google Sheets")

        if submit:
            errs = []
            if lat_val is None or lng_val is None:
                errs.append("Selecciona un **punto en el mapa**.")
            if prov == "(Seleccione)":
                errs.append("Provincia es requerida.")
            if canton == "(Seleccione)":
                errs.append("Cantón es requerido.")
            if not nombre.strip():
                errs.append("Nombre de club o banda es requerido.")
            if errs:
                st.error("• " + "\n• ".join(errs))
            else:
                maps_url = f"https://www.google.com/maps?q={lat_val},{lng_val}"
                row = {
                    "id": str(uuid.uuid4()),
                    "provincia": prov,
                    "Canton": canton,
                    "Nombre de club o banda": nombre.strip(),
                    "Beneficiarios": int(beneficiarios),
                    "maps_link": maps_url,
                    "date": datetime.now(TZ).strftime("%d-%m-%Y"),
                }
                append_row_generic(P4_TITLE, P4_HEADERS, row)
                st.success("✅ Registro guardado (Página 4).")
                st.cache_data.clear()
                st.rerun()

    st.divider()
    st.markdown("## 📋 Datos registrados (Página 4)")
    df4 = read_df_generic(P4_TITLE, P4_HEADERS)
    hide_df_index(df4[[c for c in P4_HEADERS if c in df4.columns]].tail(300))

    st.download_button(
        "⬇️ Descargar CSV (Página 4)",
        data=df4[[c for c in P4_HEADERS if c in df4.columns]].to_csv(index=False).encode("utf-8"),
        file_name=f"{P4_TITLE}.csv",
        mime="text/csv",
        key="dl_p4"
    )

    st.divider()
    crud_block(
        ws_name=P4_TITLE,
        headers=P4_HEADERS,
        df=df4,
        label="Página 4 (Bandas municipales)",
        preview_cols=["id","provincia","Canton","Nombre de club o banda","Beneficiarios","maps_link","date"]
    )

# ==========================================================
# PÁGINA 5 — FACTORES
# ==========================================================
with tabs[4]:
    st.subheader(f"{P5_TITLE} — Hoja: {FORM_SHEETS[P5_TITLE]}")

    left, right = st.columns([0.58, 0.42], gap="large")

    with left:
        st.markdown("### Selecciona un punto en el mapa")
        lat_val, lng_val = render_pick_map("map_p5", "style_p5", "clicked_p5")

    with right:
        st.markdown("### Formulario (Factores)")

        # ✅ FUERA del form
        prov, canton = ui_select_prov_canton("p5")

        with st.form("form_p5", clear_on_submit=True):
            st.caption(f"Seleccionado: **{prov} / {canton}**")
            distrito = st.text_input("Distrito (opcional)")
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
            if prov == "(Seleccione)":
                errs.append("Provincia es requerida.")
            if canton == "(Seleccione)":
                errs.append("Cantón es requerido.")
            if not factores_sel:
                errs.append("Selecciona al menos **un factor de riesgo**.")
            if errs:
                st.error("• " + "\n• ".join(errs))
            else:
                maps_url = f"https://www.google.com/maps?q={lat_val},{lng_val}"
                row = {
                    "id": str(uuid.uuid4()),
                    "provincia": prov,
                    "canton": canton,
                    "distrito": (distrito or "").strip(),
                    "factores": " | ".join([x.strip() for x in factores_sel]),
                    "delitos_relacionados": (delitos or "").strip(),
                    "ligado_estructura": (ligado or "").strip(),
                    "nombre_estructura": (nombre_estructura or "").strip(),
                    "observaciones": (observ or "").strip(),
                    "maps_link": maps_url,
                    "date": datetime.now(TZ).strftime("%d-%m-%Y"),
                }
                append_row_generic(FORM_SHEETS[P5_TITLE], P5_HEADERS, row)
                st.success("✅ Registro guardado (Página 5).")
                st.cache_data.clear()
                st.rerun()

    st.divider()
    st.markdown("## 📋 Datos registrados (Página 5)")
    df5 = read_df_generic(FORM_SHEETS[P5_TITLE], P5_HEADERS)
    hide_df_index(df5[[c for c in P5_HEADERS if c in df5.columns]].tail(300))

    st.download_button(
        "⬇️ Descargar CSV (Página 5)",
        data=df5[[c for c in P5_HEADERS if c in df5.columns]].to_csv(index=False).encode("utf-8"),
        file_name=f"{FORM_SHEETS[P5_TITLE]}.csv",
        mime="text/csv",
        key="dl_p5"
    )

    st.divider()
    crud_block(
        ws_name=FORM_SHEETS[P5_TITLE],
        headers=P5_HEADERS,
        df=df5,
        label="Página 5 (Factores)",
        preview_cols=["id","provincia","canton","distrito","factores","maps_link","date"]
    )

# ==========================================================
# VISOR (capas) — pines por provincia
# ==========================================================
with tabs[-2]:
    st.subheader("🗺️ Visor (capas) — Ver datos por página o todo junto")

    visor_style = st.selectbox("Estilo de mapa (Visor)", MAP_STYLE_OPTIONS, index=0, key="visor_style")

    df_all = load_all_data()
    if df_all.empty:
        st.info("Aún no hay registros.")
    else:
        c1, c2, c3 = st.columns([0.45, 0.25, 0.30])
        with c1:
            layer = st.selectbox("Capa a visualizar", options=["(Todas)","Página 1","Página 2","Página 3","Página 4","Página 5"], index=0)
        with c2:
            show_heat = st.checkbox("Mostrar HeatMap", value=True)
        with c3:
            show_clusters = st.checkbox("Mostrar clusters", value=True)

        dfv = df_all.copy()
        if layer != "(Todas)":
            dfv = dfv[dfv["page"] == layer]

        m = folium.Map(location=CR_CENTER, zoom_start=CR_ZOOM, control_scale=True, tiles=None)
        _add_panes(m)
        _add_tile_by_name(m, "Esri Satélite")
        if visor_style != "Esri Satélite":
            _add_tile_by_name(m, visor_style)
        LocateControl(auto_start=False).add_to(m)

        group = (MarkerCluster(name="Marcadores", overlay=True, control=True, pane="markers")
                 if show_clusters else folium.FeatureGroup(name="Marcadores", overlay=True, control=True))
        group.add_to(m)

        heat_points, idx, omitidos = [], 0, 0

        for _, r in dfv.iterrows():
            lat, lng = r.get("lat"), r.get("lng")
            if pd.isna(lat) or pd.isna(lng):
                omitidos += 1
                continue

            page = r.get("page","")

            prov = str(r.get("provincia","")).strip()

            # P2/P3 guardan "Canton" como "Provincia / Cantón"
            if not prov and "Canton" in r and isinstance(r.get("Canton"), str):
                pp, cc = parse_prov_from_canton_field(r.get("Canton"))
                if pp in PROVINCIAS:
                    prov = pp

            pin_color = color_by_provincia(prov)

            popup = f"<b>{page}</b><br>"
            if page == "Página 1":
                popup += f"<b>Provincia:</b> {r.get('provincia','')}<br><b>Cantón:</b> {r.get('canton','')}<br><b>Distrito:</b> {r.get('distrito','')}<br>"
            elif page == "Página 2":
                popup += f"<b>Canton:</b> {r.get('Canton','')}<br><b>Centro:</b> {r.get('Community Prevention Centers','')}<br><b>Beneficiaries:</b> {r.get('Beneficiaries','')}<br>"
            elif page == "Página 3":
                popup += f"<b>Canton:</b> {r.get('Canton','')}<br><b>Matriculadas:</b> {r.get('Cantidad de personas matriculadas','')}<br><b>Egresadas:</b> {r.get('Cantidad de personas egresadas','')}<br>"
            elif page == "Página 4":
                popup += f"<b>Provincia:</b> {r.get('provincia','')}<br><b>Canton:</b> {r.get('Canton','')}<br><b>Banda:</b> {r.get('Nombre de club o banda','')}<br>"
            else:
                popup += f"<b>Provincia:</b> {r.get('provincia','')}<br><b>Cantón:</b> {r.get('canton','')}<br><b>Distrito:</b> {r.get('distrito','')}<br><b>Factor(es):</b> {r.get('factores','')}<br>"

            popup += f"<b>Fecha:</b> {r.get('date','')}<br>"
            popup += f"<b>Maps:</b> <a href='{r.get('maps_link','')}' target='_blank'>Abrir</a>"

            jlat = float(lat) + _jitter(idx)
            jlng = float(lng) + _jitter(idx + 101)

            folium.Marker(
                [jlat, jlng],
                icon=make_pin_icon(pin_color),
                popup=popup,
                pane="markers"
            ).add_to(group)

            heat_points.append([float(lat), float(lng), 1.0])
            idx += 1

        if show_heat and heat_points:
            HeatMap(
                heat_points,
                radius=18, blur=22, max_zoom=16, min_opacity=0.25
            ).add_to(
                folium.FeatureGroup(name="Mapa de calor", overlay=True, control=True, pane="heatmap").add_to(m)
            )

        folium.LayerControl(collapsed=False).add_to(m)
        st_folium(m, height=560, use_container_width=True, key="visor_map", returned_objects=[])

        if omitidos:
            st.caption(f"({omitidos} registro(s) omitidos por coordenadas inválidas)")

        st.divider()
        st.markdown("#### Tabla (según filtros)")
        show_cols = [c for c in dfv.columns if c not in ["lat","lng","form_label"]]
        hide_df_index(dfv[show_cols].head(500))

        st.download_button(
            "⬇️ Descargar CSV (visor)",
            data=dfv[show_cols].to_csv(index=False).encode("utf-8"),
            file_name="visor_paginas.csv",
            mime="text/csv",
            key="dl_visor"
        )

# ==========================================================
# GRÁFICAS — SOLO AQUÍ (pro por página: barras + donut + sunburst)
# ==========================================================
with tabs[-1]:
    st.subheader("📊 Gráficas — Resumen por página (solo aquí)")

    df_all = load_all_data()
    if df_all.empty:
        st.info("Aún no hay registros para graficar.")
    else:
        page_sel = st.selectbox(
            "¿De qué página querés ver gráficos?",
            options=["Página 1","Página 2","Página 3","Página 4","Página 5"],
            index=0,
            key="g_page"
        )

        dfg = df_all[df_all["page"] == page_sel].copy()
        st.markdown(f"## 📌 Gráficas — {page_sel}")

        if dfg.empty:
            st.warning("No hay datos en esa página.")
        else:
            top_n = st.slider("Top N", 5, 30, 10, key="g_top")

            # -----------------------------
            # Página 1 — Estructuras
            # -----------------------------
            if page_sel == "Página 1":
                rows = []
                for _, r in dfg.iterrows():
                    prov = str(r.get("provincia","")).strip()
                    cant = str(r.get("canton","")).strip()
                    dist = str(r.get("distrito","")).strip()
                    for i in range(1, 12):
                        v = str(r.get(f"estructura_{i}","")).strip()
                        if v and v.lower() != "nan":
                            rows.append({"provincia": prov, "canton": cant, "distrito": dist, "estructura": v})

                df_struct = pd.DataFrame(rows)
                if df_struct.empty:
                    st.info("No hay estructuras registradas aún.")
                else:
                    c1, c2 = st.columns([0.5, 0.5])
                    with c1:
                        provs = sorted([p for p in df_struct["provincia"].dropna().unique() if str(p).strip()])
                        f_prov = st.selectbox("Filtrar Provincia", options=["(Todas)"] + provs, index=0, key="p1_g_prov")
                    tmp = df_struct.copy()
                    if f_prov != "(Todas)":
                        tmp = tmp[tmp["provincia"] == f_prov]
                    with c2:
                        cants = sorted([c for c in tmp["canton"].dropna().unique() if str(c).strip()])
                        f_cant = st.selectbox("Filtrar Cantón", options=["(Todos)"] + cants, index=0, key="p1_g_cant")
                    if f_cant != "(Todos)":
                        tmp = tmp[tmp["canton"] == f_cant]

                    counts = tmp["estructura"].value_counts().head(top_n).reset_index()
                    counts.columns = ["estructura","conteo"]

                    st.markdown("### 🔝 Top estructuras (Barras)")
                    fig_bar = px.bar(
                        counts.sort_values("conteo", ascending=True),
                        x="conteo", y="estructura", orientation="h", text="conteo",
                        template="plotly_dark",
                        title="Top estructuras por frecuencia"
                    )
                    fig_bar.update_traces(textposition="outside", cliponaxis=False)
                    fig_bar.update_layout(height=560, margin=dict(l=10, r=10, t=60, b=10))
                    st.plotly_chart(fig_bar, use_container_width=True)

                    st.markdown("### 🍩 Distribución (Donut)")
                    fig_donut = px.pie(
                        counts, names="estructura", values="conteo", hole=0.6,
                        template="plotly_dark",
                        title="Distribución (Top)"
                    )
                    fig_donut.update_traces(textinfo="percent", textposition="inside")
                    fig_donut.update_layout(height=560, margin=dict(l=10, r=10, t=60, b=10))
                    st.plotly_chart(fig_donut, use_container_width=True)

                    st.markdown("### 🧊 Sunburst — Provincia → Cantón → Estructura")
                    grp = tmp.groupby(["provincia","canton","estructura"]).size().reset_index(name="conteo")
                    fig_sun = px.sunburst(
                        grp, path=["provincia","canton","estructura"], values="conteo",
                        template="plotly_dark",
                        title="Provincia → Cantón → Estructura"
                    )
                    fig_sun.update_layout(height=650, margin=dict(l=10, r=10, t=60, b=10))
                    st.plotly_chart(fig_sun, use_container_width=True)

            # -----------------------------
            # Página 2 — CPC
            # -----------------------------
            elif page_sel == "Página 2":
                # Top centros por conteo
                counts = safe_series(dfg, "Community Prevention Centers").fillna("").replace("", pd.NA).dropna().value_counts().head(top_n).reset_index()
                counts.columns = ["centro","conteo"]

                st.markdown("### 🔝 Top Centros (Barras)")
                fig_bar = px.bar(
                    counts.sort_values("conteo", ascending=True),
                    x="conteo", y="centro", orientation="h", text="conteo",
                    template="plotly_dark",
                    title="Top Community Prevention Centers (por frecuencia)"
                )
                fig_bar.update_traces(textposition="outside", cliponaxis=False)
                fig_bar.update_layout(height=650, margin=dict(l=10, r=10, t=60, b=10))
                st.plotly_chart(fig_bar, use_container_width=True)

                st.markdown("### 🍩 Distribución (Donut)")
                fig_donut = px.pie(
                    counts, names="centro", values="conteo", hole=0.6,
                    template="plotly_dark",
                    title="Distribución de Centros (Top)"
                )
                fig_donut.update_traces(textinfo="percent", textposition="inside")
                fig_donut.update_layout(height=560, margin=dict(l=10, r=10, t=60, b=10))
                st.plotly_chart(fig_donut, use_container_width=True)

                st.markdown("### 🧊 Sunburst — Canton → Centro")
                grp = dfg.copy()
                grp["Canton"] = grp["Canton"].fillna("").astype(str)
                grp["centro"] = grp["Community Prevention Centers"].fillna("").astype(str)
                grp = grp[(grp["Canton"].str.strip() != "") & (grp["centro"].str.strip() != "")]
                grp = grp.groupby(["Canton","centro"]).size().reset_index(name="conteo")
                fig_sun = px.sunburst(
                    grp, path=["Canton","centro"], values="conteo",
                    template="plotly_dark",
                    title="Canton → Centro"
                )
                fig_sun.update_layout(height=650, margin=dict(l=10, r=10, t=60, b=10))
                st.plotly_chart(fig_sun, use_container_width=True)

            # -----------------------------
            # Página 3 — Empleabilidad
            # -----------------------------
            elif page_sel == "Página 3":
                g = dfg.copy()
                g["Canton"] = g["Canton"].fillna("").astype(str)
                for col in ["Cantidad de personas matriculadas","Cantidad de personas egresadas"]:
                    if col in g.columns:
                        g[col] = pd.to_numeric(g[col], errors="coerce").fillna(0)

                grp = g.groupby("Canton")[["Cantidad de personas matriculadas","Cantidad de personas egresadas"]].sum().reset_index()
                grp = grp.sort_values("Cantidad de personas matriculadas", ascending=False).head(top_n)

                melt = grp.melt(id_vars=["Canton"], var_name="tipo", value_name="cantidad")

                st.markdown("### 📊 Matriculadas vs Egresadas (Barras)")
                fig_bar = px.bar(
                    melt,
                    x="cantidad", y="Canton", color="tipo",
                    orientation="h",
                    template="plotly_dark",
                    title="Suma por Cantón (Top)"
                )
                fig_bar.update_layout(height=650, margin=dict(l=10, r=10, t=60, b=10))
                st.plotly_chart(fig_bar, use_container_width=True)

                st.markdown("### 🍩 Proporción total (Donut)")
                tot_m = float(g["Cantidad de personas matriculadas"].sum()) if "Cantidad de personas matriculadas" in g.columns else 0.0
                tot_e = float(g["Cantidad de personas egresadas"].sum()) if "Cantidad de personas egresadas" in g.columns else 0.0
                donut_df = pd.DataFrame({"categoria":["Matriculadas","Egresadas"], "cantidad":[tot_m, tot_e]})
                fig_donut = px.pie(
                    donut_df, names="categoria", values="cantidad", hole=0.6,
                    template="plotly_dark",
                    title="Total Matriculadas vs Egresadas"
                )
                fig_donut.update_traces(textinfo="percent", textposition="inside")
                fig_donut.update_layout(height=520, margin=dict(l=10, r=10, t=60, b=10))
                st.plotly_chart(fig_donut, use_container_width=True)

                st.markdown("### 🧊 Sunburst — Canton → Tipo")
                sun = melt.copy()
                sun["tipo"] = sun["tipo"].str.replace("Cantidad de personas ", "", regex=False)
                fig_sun = px.sunburst(
                    sun, path=["Canton","tipo"], values="cantidad",
                    template="plotly_dark",
                    title="Canton → Tipo (Matriculadas/Egresadas)"
                )
                fig_sun.update_layout(height=650, margin=dict(l=10, r=10, t=60, b=10))
                st.plotly_chart(fig_sun, use_container_width=True)

            # -----------------------------
            # Página 4 — Bandas municipales
            # -----------------------------
            elif page_sel == "Página 4":
                g = dfg.copy()
                g["provincia"] = g["provincia"].fillna("").astype(str)
                g["Canton"] = g["Canton"].fillna("").astype(str)
                g["Nombre de club o banda"] = g["Nombre de club o banda"].fillna("").astype(str)
                if "Beneficiarios" in g.columns:
                    g["Beneficiarios"] = pd.to_numeric(g["Beneficiarios"], errors="coerce").fillna(0)

                grp_prov = g.groupby("provincia")["Beneficiarios"].sum().reset_index().sort_values("Beneficiarios", ascending=False)
                st.markdown("### 🟦 Beneficiarios por provincia (Barras)")
                fig_bar = px.bar(
                    grp_prov.sort_values("Beneficiarios", ascending=True),
                    x="Beneficiarios", y="provincia", orientation="h", text="Beneficiarios",
                    template="plotly_dark",
                    title="Suma de Beneficiarios por provincia"
                )
                fig_bar.update_traces(textposition="outside", cliponaxis=False)
                fig_bar.update_layout(height=520, margin=dict(l=10, r=10, t=60, b=10))
                st.plotly_chart(fig_bar, use_container_width=True)

                top_bandas = g.groupby("Nombre de club o banda")["Beneficiarios"].sum().reset_index().sort_values("Beneficiarios", ascending=False).head(top_n)
                st.markdown("### 🍩 Top Bandas por beneficiarios (Donut)")
                fig_donut = px.pie(
                    top_bandas, names="Nombre de club o banda", values="Beneficiarios", hole=0.6,
                    template="plotly_dark",
                    title="Top Bandas (suma Beneficiarios)"
                )
                fig_donut.update_traces(textinfo="percent", textposition="inside")
                fig_donut.update_layout(height=620, margin=dict(l=10, r=10, t=60, b=10))
                st.plotly_chart(fig_donut, use_container_width=True)

                st.markdown("### 🧊 Sunburst — Provincia → Cantón → Banda")
                sun = g[(g["provincia"].str.strip() != "") & (g["Canton"].str.strip() != "") & (g["Nombre de club o banda"].str.strip() != "")]
                sun = sun.groupby(["provincia","Canton","Nombre de club o banda"])["Beneficiarios"].sum().reset_index()
                fig_sun = px.sunburst(
                    sun, path=["provincia","Canton","Nombre de club o banda"], values="Beneficiarios",
                    template="plotly_dark",
                    title="Provincia → Cantón → Banda (Beneficiarios)"
                )
                fig_sun.update_layout(height=700, margin=dict(l=10, r=10, t=60, b=10))
                st.plotly_chart(fig_sun, use_container_width=True)

            # -----------------------------
            # Página 5 — Factores
            # -----------------------------
            else:
                # Expandimos factores separados por |
                rows = []
                for _, r in dfg.iterrows():
                    prov = str(r.get("provincia","")).strip()
                    cant = str(r.get("canton","")).strip()
                    dist = str(r.get("distrito","")).strip()
                    parts = split_pipe_values(str(r.get("factores","") or ""))
                    for f in parts:
                        rows.append({"provincia": prov, "canton": cant, "distrito": dist, "factor": f})

                fx = pd.DataFrame(rows)
                if fx.empty:
                    st.info("No hay factores registrados aún.")
                else:
                    counts = fx["factor"].value_counts().head(top_n).reset_index()
                    counts.columns = ["factor","conteo"]

                    st.markdown("### 🔝 Top factores (Barras)")
                    fig_bar = px.bar(
                        counts.sort_values("conteo", ascending=True),
                        x="conteo", y="factor", orientation="h", text="conteo",
                        template="plotly_dark",
                        title="Top factores por frecuencia"
                    )
                    fig_bar.update_traces(textposition="outside", cliponaxis=False)
                    fig_bar.update_layout(height=720, margin=dict(l=10, r=10, t=60, b=10))
                    st.plotly_chart(fig_bar, use_container_width=True)

                    st.markdown("### 🍩 Distribución (Donut)")
                    fig_donut = px.pie(
                        counts, names="factor", values="conteo", hole=0.6,
                        template="plotly_dark",
                        title="Distribución de factores (Top)"
                    )
                    fig_donut.update_traces(textinfo="percent", textposition="inside")
                    fig_donut.update_layout(height=650, margin=dict(l=10, r=10, t=60, b=10))
                    st.plotly_chart(fig_donut, use_container_width=True)

                    st.markdown("### 🧊 Sunburst — Provincia → Cantón → Factor")
                    grp = fx.groupby(["provincia","canton","factor"]).size().reset_index(name="conteo")
                    fig_sun = px.sunburst(
                        grp, path=["provincia","canton","factor"], values="conteo",
                        template="plotly_dark",
                        title="Provincia → Cantón → Factor"
                    )
                    fig_sun.update_layout(height=760, margin=dict(l=10, r=10, t=60, b=10))
                    st.plotly_chart(fig_sun, use_container_width=True)

        st.divider()
        st.markdown("#### Datos base (según página)")
        hide_df_index(dfg.head(500))

