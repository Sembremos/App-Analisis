# -*- coding: utf-8 -*-
# Streamlit — Páginas + Visor (capas) + Gráficas — Google Sheets como DB
# ✅ CRUD (editar/eliminar) por pestaña
# ✅ Gráficas SOLO en pestaña 📊 Gráficas
# ✅ Página 1: barrio -> distrito
# ✅ Pines por provincia (color distinto)
# ✅ Provincia/Cantón precargados (cantón condicionado por provincia)
# ✅ Página 2/3/4 con columnas EXACTAS según imágenes (se agregan id/date solo para CRUD)
# ✅ Tablas sin índice (sin contar filas)

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import random, re
import uuid

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

# Colores por provincia para pines
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

# ==========================================================
# PÁGINAS / HOJAS (Google Sheets)
# ==========================================================
P1_TITLE = "Pandillas de trafico transnacional Costa Rica 2025"  # Página 1

# OJO: Reordenado EXACTO como pediste
P2_TITLE = "Community Prevention Centers"  # Página 2 (imagen 1)
P3_TITLE = "Programa de empleabilidad"     # Página 3 (imagen 2)
P4_TITLE = "Bandas municipales"            # Página 4 (imagen 3)

P5_TITLE = "Formulario 5"                  # Página 5 opcional (factores con mapa)

FORM_SHEETS = {
    P1_TITLE: P1_TITLE,
    P2_TITLE: P2_TITLE,
    P3_TITLE: P3_TITLE,
    P4_TITLE: P4_TITLE,
    P5_TITLE: "Prueba_5",
}

# ==========================================================
# SCHEMAS (con ID para CRUD)
# ==========================================================
# Página 1 (pandillas/estructuras)
P1_HEADERS = [
    "id",
    "provincia",
    "canton",
    "distrito",   # antes "barrio"
    "estructura_1","estructura_2","estructura_3","estructura_4","estructura_5","estructura_6",
    "estructura_7","estructura_8","estructura_9","estructura_10","estructura_11",
    "maps_link",
    "date",
]

# Página 2 (CPC) — EXACTO como imagen 1 (se agrega id/date para CRUD)
P2_HEADERS = [
    "id",
    "Beneficiaries",
    "Canton",
    "Community Prevention Centers",
    "date",
]

# Página 3 (Empleabilidad) — EXACTO como imagen 2 (se agrega id/date para CRUD)
P3_HEADERS = [
    "id",
    "Canton",
    "Cursos Brindados",
    "Cantidad de personas matriculadas",
    "Cantidad de personas egresadas",
    "sexo por personas egresadas",
    "date",
]

# Página 4 (Bandas municipales) — EXACTO como imagen 3 (se agrega id/date para CRUD)
P4_HEADERS = [
    "id",
    "provincia",
    "Canton",
    "Nombre de club o banda",
    "Beneficiarios",
    "date",
]

# Página 5 (factores con mapa)
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

    # compatibilidad: si una hoja vieja tenía "barrio" y ahora usamos "distrito"
    if "distrito" in headers and "barrio" in df.columns:
        df["distrito"] = df.get("distrito", "").fillna("").astype(str)
        df["barrio"] = df["barrio"].fillna("").astype(str)
        df.loc[df["distrito"].str.strip() == "", "distrito"] = df["barrio"]

    # lat/lng solo si existe maps_link
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
        raise ValueError("No se encontró el ID a editar en la hoja.")
    cols = _headers(ws)
    values = [updated.get(c, "") for c in cols]
    ws.update(f"A{row_num}:{gspread.utils.rowcol_to_a1(row_num, len(cols))}", [values])

def delete_row_by_id(ws_name: str, headers: list, record_id: str):
    ws = _get_or_create_ws(ws_name, headers)
    row_num = _find_row_by_id(ws, record_id)
    if not row_num:
        raise ValueError("No se encontró el ID a eliminar en la hoja.")
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

def color_by_provincia(prov: str) -> str:
    prov = (prov or "").strip()
    return PROV_COLORS.get(prov, DEFAULT_PROV_COLOR)

# ==========================================================
# HELPERS UI: select Provincia/Cantón condicionados
# ==========================================================
def ui_select_prov_canton(key_prefix: str, default_prov: str = "", default_canton: str = ""):
    c1, c2 = st.columns(2)
    with c1:
        prov = st.selectbox(
            "Provincia *",
            options=["(Seleccione)"] + PROVINCIAS,
            index=(PROVINCIAS.index(default_prov) + 1) if default_prov in PROVINCIAS else 0,
            key=f"{key_prefix}_prov"
        )
    cantones = PROV_CANTONES.get(prov, []) if prov != "(Seleccione)" else []
    with c2:
        canton = st.selectbox(
            "Cantón *",
            options=["(Seleccione)"] + cantones,
            index=(cantones.index(default_canton) + 1) if default_canton in cantones else 0,
            key=f"{key_prefix}_canton"
        )
    return prov, canton

def hide_df_index(df: pd.DataFrame):
    st.dataframe(df, use_container_width=True, hide_index=True)

# ==========================================================
# LOAD ALL (para visor y gráficas globales)
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
# CRUD reusable
# ==========================================================
def crud_block(ws_name: str, headers: list, df: pd.DataFrame, label: str, preview_cols: list):
    st.markdown(f"### 🛠️ CRUD — {label}")
    if df.empty:
        st.info("Aún no hay registros para editar/eliminar.")
        return

    if "id" not in df.columns:
        st.warning("No existe columna 'id' en la hoja. Revisá headers.")
        return

    show_cols = [c for c in preview_cols if c in df.columns]
    view_df = df[show_cols].copy()

    def _label_row(r):
        parts = []
        for c in ["provincia","canton","distrito","Canton","date","Nombre de club o banda","Cursos Brindados","Community Prevention Centers"]:
            if c in r and str(r.get(c,"")).strip():
                parts.append(str(r.get(c)))
        return " | ".join(parts)[:140] if parts else "registro"

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
            st.markdown("**Editar campos** (se actualiza Google Sheets)")
            updated = dict(row)

            for h in headers:
                if h == "id":
                    continue
                if h in ["maps_link"]:
                    updated[h] = st.text_input(h, value=str(row.get(h,"")), disabled=True)
                elif h == "date":
                    updated[h] = st.text_input(h, value=str(row.get(h,"")), disabled=True)
                elif h in ["Beneficiaries","Beneficiarios","Cantidad de personas matriculadas","Cantidad de personas egresadas"]:
                    updated[h] = st.number_input(h, value=float(row.get(h) or 0), step=1.0)
                    if float(updated[h]).is_integer():
                        updated[h] = int(updated[h])
                else:
                    updated[h] = st.text_input(h, value=str(row.get(h,"")))

            do_update = st.form_submit_button("💾 Guardar cambios")

        if do_update:
            try:
                updated["id"] = record_id
                if "date" in headers and not str(updated.get("date","")).strip():
                    updated["date"] = datetime.now(TZ).strftime("%d-%m-%Y")
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
# UI
# ==========================================================
st.title("📍 Costa Rica — Páginas + Visor + Gráficas")
st.caption("CRUD incluido (editar/eliminar). Gráficas SOLO en pestaña 📊 Gráficas.")

tab_labels = [P1_TITLE, P2_TITLE, P3_TITLE, P4_TITLE, P5_TITLE, "Visor (capas)", "📊 Gráficas"]
tabs = st.tabs(tab_labels)

# ==========================================================
# PÁGINA 1 — Pandillas/Estructuras (mapa + CRUD, sin gráficas aquí)
# ==========================================================
with tabs[0]:
    st.subheader(f"{P1_TITLE} — Guardando en hoja: {P1_TITLE}")

    style = st.selectbox("Estilo de mapa", MAP_STYLE_OPTIONS, index=0, key="style_p1")
    left, right = st.columns([0.58, 0.42], gap="large")

    with left:
        st.markdown("### Selecciona un punto en el mapa")
        key_clicked = "clicked_p1"
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
        map_ret = st_folium(m, height=520, use_container_width=True, key="map_p1")

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
        if cols[2].button("Limpiar selección", key="clear_p1"):
            st.session_state.pop(key_clicked, None)
            st.rerun()

    with right:
        st.markdown("### Formulario (Provincia / Cantón / Distrito + estructuras)")

        with st.form("form_p1", clear_on_submit=True):
            prov, canton = ui_select_prov_canton("p1")
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
                rid = str(uuid.uuid4())
                row = {
                    "id": rid,
                    "provincia": prov,
                    "canton": canton,
                    "distrito": (distrito or "").strip(),
                    **{f"estructura_{i}": (e[i-1] or "").strip() for i in range(1, 12)},
                    "maps_link": maps_url,
                    "date": datetime.now(TZ).strftime("%d-%m-%Y"),
                }
                try:
                    append_row_generic(P1_TITLE, P1_HEADERS, row)
                    st.success("✅ Registro guardado (Página 1).")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as ex:
                    st.error(f"❌ No se pudo guardar.\n\n{ex}")

    st.divider()
    st.markdown("## 📋 Datos registrados (Página 1)")
    df1 = read_df_generic(P1_TITLE, P1_HEADERS)
    cols_show = [c for c in P1_HEADERS if c in df1.columns]
    hide_df_index(df1[cols_show].tail(300))

    st.download_button(
        "⬇️ Descargar CSV (Página 1)",
        data=df1[cols_show].to_csv(index=False).encode("utf-8"),
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
        preview_cols=["id","provincia","canton","distrito","date"] + [f"estructura_{i}" for i in range(1,12)]
    )

# ==========================================================
# PÁGINA 2 — CPC (imagen 1) + CRUD
# Columns: Beneficiaries | Canton | Community Prevention Centers
# ==========================================================
with tabs[1]:
    st.subheader(f"{P2_TITLE} — Guardando en hoja: {P2_TITLE}")

    with st.form("form_p2", clear_on_submit=True):
        # Para que "Canton" quede como en tus excel, lo guardo como "Provincia / Cantón"
        prov, canton = ui_select_prov_canton("p2")
        beneficiaries = st.number_input("Beneficiaries", min_value=0, step=1)
        cpc_name = st.text_input("Community Prevention Centers *")
        submit = st.form_submit_button("Guardar en Google Sheets")

    if submit:
        errs = []
        if prov == "(Seleccione)":
            errs.append("Provincia es requerida.")
        if canton == "(Seleccione)":
            errs.append("Cantón es requerido.")
        if not cpc_name.strip():
            errs.append("Community Prevention Centers es requerido.")
        if errs:
            st.error("• " + "\n• ".join(errs))
        else:
            row = {
                "id": str(uuid.uuid4()),
                "Beneficiaries": int(beneficiaries),
                "Canton": f"{prov} / {canton}",
                "Community Prevention Centers": cpc_name.strip(),
                "date": datetime.now(TZ).strftime("%d-%m-%Y"),
            }
            try:
                append_row_generic(P2_TITLE, P2_HEADERS, row)
                st.success("✅ Registro guardado (Página 2).")
                st.cache_data.clear()
                st.rerun()
            except Exception as ex:
                st.error(f"❌ No se pudo guardar.\n\n{ex}")

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
        preview_cols=["id","Canton","Community Prevention Centers","Beneficiaries","date"]
    )

# ==========================================================
# PÁGINA 3 — Empleabilidad (imagen 2) + CRUD
# Columns: Cantón | Cursos Brindados | Cantidad ... matriculadas | ... egresadas | sexo...
# ==========================================================
with tabs[2]:
    st.subheader(f"{P3_TITLE} — Guardando en hoja: {P3_TITLE}")

    with st.form("form_p3", clear_on_submit=True):
        # igual: guardo Canton como "Provincia / Cantón" para mantener formato consistente
        prov, canton = ui_select_prov_canton("p3")
        cursos = st.text_area("Cursos Brindados *", height=90)
        matric = st.number_input("Cantidad de personas matriculadas", min_value=0, step=1)
        egres = st.number_input("Cantidad de personas egresadas", min_value=0, step=1)
        sexo = st.text_input("sexo por personas egresadas (ej: H: 36 / M: 59)")
        submit = st.form_submit_button("Guardar en Google Sheets")

    if submit:
        errs = []
        if prov == "(Seleccione)":
            errs.append("Provincia es requerida.")
        if canton == "(Seleccione)":
            errs.append("Cantón es requerido.")
        if not cursos.strip():
            errs.append("Cursos Brindados es requerido.")
        if errs:
            st.error("• " + "\n• ".join(errs))
        else:
            row = {
                "id": str(uuid.uuid4()),
                "Canton": f"{prov} / {canton}",
                "Cursos Brindados": cursos.strip(),
                "Cantidad de personas matriculadas": int(matric),
                "Cantidad de personas egresadas": int(egres),
                "sexo por personas egresadas": (sexo or "").strip(),
                "date": datetime.now(TZ).strftime("%d-%m-%Y"),
            }
            try:
                append_row_generic(P3_TITLE, P3_HEADERS, row)
                st.success("✅ Registro guardado (Página 3).")
                st.cache_data.clear()
                st.rerun()
            except Exception as ex:
                st.error(f"❌ No se pudo guardar.\n\n{ex}")

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
        preview_cols=["id","Canton","Cursos Brindados","Cantidad de personas matriculadas","Cantidad de personas egresadas","sexo por personas egresadas","date"]
    )

# ==========================================================
# PÁGINA 4 — Bandas municipales (imagen 3) + CRUD
# Columns: provincia | Canton | Nombre de club o banda | Beneficiarios
# ==========================================================
with tabs[3]:
    st.subheader(f"{P4_TITLE} — Guardando en hoja: {P4_TITLE}")

    with st.form("form_p4", clear_on_submit=True):
        prov, canton = ui_select_prov_canton("p4")
        nombre = st.text_input("Nombre de club o banda *")
        beneficiarios = st.number_input("Beneficiarios", min_value=0, step=1)
        submit = st.form_submit_button("Guardar en Google Sheets")

    if submit:
        errs = []
        if prov == "(Seleccione)":
            errs.append("Provincia es requerida.")
        if canton == "(Seleccione)":
            errs.append("Cantón es requerido.")
        if not nombre.strip():
            errs.append("Nombre de club o banda es requerido.")
        if errs:
            st.error("• " + "\n• ".join(errs))
        else:
            row = {
                "id": str(uuid.uuid4()),
                "provincia": prov,
                "Canton": canton,
                "Nombre de club o banda": nombre.strip(),
                "Beneficiarios": int(beneficiarios),
                "date": datetime.now(TZ).strftime("%d-%m-%Y"),
            }
            try:
                append_row_generic(P4_TITLE, P4_HEADERS, row)
                st.success("✅ Registro guardado (Página 4).")
                st.cache_data.clear()
                st.rerun()
            except Exception as ex:
                st.error(f"❌ No se pudo guardar.\n\n{ex}")

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
        preview_cols=["id","provincia","Canton","Nombre de club o banda","Beneficiarios","date"]
    )

# ==========================================================
# PÁGINA 5 — Factores (opcional) con mapa + CRUD
# ==========================================================
with tabs[4]:
    st.subheader(f"{P5_TITLE} — Guardando en hoja: {FORM_SHEETS[P5_TITLE]}")

    style = st.selectbox("Estilo de mapa", MAP_STYLE_OPTIONS, index=0, key="style_p5")

    left, right = st.columns([0.58, 0.42], gap="large")
    with left:
        st.markdown("### Selecciona un punto en el mapa")
        key_clicked = "clicked_p5"
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
        map_ret = st_folium(m, height=520, use_container_width=True, key="map_p5")

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
        if cols[2].button("Limpiar selección", key="clear_p5"):
            st.session_state.pop(key_clicked, None)
            st.rerun()

    with right:
        st.markdown("### Formulario (factores)")
        with st.form("form_p5", clear_on_submit=True):
            prov, canton = ui_select_prov_canton("p5")
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
                try:
                    append_row_generic(FORM_SHEETS[P5_TITLE], P5_HEADERS, row)
                    st.success("✅ Registro guardado (Página 5).")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as ex:
                    st.error(f"❌ No se pudo guardar.\n\n{ex}")

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
        preview_cols=["id","provincia","canton","distrito","factores","date"]
    )

# ==========================================================
# VISOR (capas) — Pines por provincia
# (Solo aparecerán páginas que tengan maps_link con coordenadas válidas: Página 1 y 5)
# ==========================================================
with tabs[-2]:
    st.subheader("🗺️ Visor (capas) — Ver datos por página (solo mapas)")

    visor_style = st.selectbox("Estilo de mapa (Visor)", MAP_STYLE_OPTIONS, index=0, key="visor_style")

    df_all = load_all_data()
    if df_all.empty:
        st.info("Aún no hay registros.")
    else:
        # Solo páginas con coordenadas (P1 y P5)
        df_map = df_all[df_all["page"].isin(["Página 1", "Página 5"])].copy()

        c1, c2, c3 = st.columns([0.45, 0.25, 0.30])
        with c1:
            layer = st.selectbox("Capa a visualizar", options=["(Todas)","Página 1","Página 5"], index=0)
        with c2:
            show_heat = st.checkbox("Mostrar HeatMap", value=True)
        with c3:
            show_clusters = st.checkbox("Mostrar clusters", value=True)

        dfv = df_map.copy()
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

        heat_points = []
        idx = 0
        omitidos = 0

        for _, r in dfv.iterrows():
            lat, lng = r.get("lat"), r.get("lng")
            if pd.isna(lat) or pd.isna(lng):
                omitidos += 1
                continue

            prov = str(r.get("provincia","")).strip()
            pin_color = color_by_provincia(prov)

            page = r.get("page","")
            if page == "Página 1":
                estructuras = []
                for i in range(1, 12):
                    v = str(r.get(f"estructura_{i}", "")).strip()
                    if v and v.lower() != "nan":
                        estructuras.append(v)
                estructuras_txt = "<br>".join([f"• {x}" for x in estructuras]) if estructuras else "(sin estructuras)"
                popup = (
                    f"<b>Página:</b> 1 (Pandillas)<br>"
                    f"<b>Provincia:</b> {prov}<br>"
                    f"<b>Cantón:</b> {r.get('canton','')}<br>"
                    f"<b>Distrito:</b> {r.get('distrito','')}<br>"
                    f"<b>Estructuras:</b><br>{estructuras_txt}<br>"
                    f"<b>Fecha:</b> {r.get('date','')}<br>"
                    f"<b>Maps:</b> <a href='{r.get('maps_link','')}' target='_blank'>Abrir</a>"
                )
            else:
                popup = (
                    f"<b>Página:</b> 5 (Factores)<br>"
                    f"<b>Provincia:</b> {prov}<br>"
                    f"<b>Cantón:</b> {r.get('canton','')}<br>"
                    f"<b>Distrito:</b> {r.get('distrito','')}<br>"
                    f"<b>Fecha:</b> {r.get('date','')}<br>"
                    f"<b>Factor(es):</b> {r.get('factores','')}<br>"
                    f"<b>Delitos:</b> {r.get('delitos_relacionados','')}<br>"
                    f"<b>Maps:</b> <a href='{r.get('maps_link','')}' target='_blank'>Abrir</a>"
                )

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
        base_cols = ["page","provincia","canton","distrito","date","maps_link"]
        show_cols = [c for c in base_cols if c in dfv.columns]
        hide_df_index(dfv[show_cols].copy())

# ==========================================================
# GRÁFICAS — SOLO AQUÍ (bien titulado por página)
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
            # Página 1: top estructuras
            if page_sel == "Página 1":
                rows = []
                for _, r in dfg.iterrows():
                    for i in range(1, 12):
                        v = str(r.get(f"estructura_{i}", "")).strip()
                        if v and v.lower() != "nan":
                            rows.append({
                                "provincia": r.get("provincia",""),
                                "canton": r.get("canton",""),
                                "estructura": v
                            })
                df_struct = pd.DataFrame(rows)

                if df_struct.empty:
                    st.info("Aún no hay estructuras registradas para graficar.")
                else:
                    c1, c2, c3 = st.columns([0.34, 0.33, 0.33])
                    with c1:
                        provs = sorted([p for p in df_struct["provincia"].dropna().unique() if str(p).strip()])
                        f_prov = st.selectbox("Provincia", options=["(Todas)"] + provs, index=0, key="g1_prov")
                    tmp = df_struct.copy()
                    if f_prov != "(Todas)":
                        tmp = tmp[tmp["provincia"] == f_prov]
                    with c2:
                        cants = sorted([c for c in tmp["canton"].dropna().unique() if str(c).strip()])
                        f_cant = st.selectbox("Cantón", options=["(Todos)"] + cants, index=0, key="g1_cant")
                    if f_cant != "(Todos)":
                        tmp = tmp[tmp["canton"] == f_cant]
                    with c3:
                        top_n = st.slider("Top N", 5, 30, 10, key="g1_top")

                    counts = tmp["estructura"].value_counts().head(top_n).reset_index()
                    counts.columns = ["estructura","conteo"]

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
                    fig_donut.update_traces(textinfo="percent", textposition="inside")
                    fig_donut.update_layout(height=520, margin=dict(l=10, r=10, t=60, b=10))
                    st.plotly_chart(fig_donut, use_container_width=True)

            # Página 2: CPC (conteo por centro / cantón)
            elif page_sel == "Página 2":
                st.markdown("### 📌 Top Community Prevention Centers")
                s = dfg["Community Prevention Centers"].fillna("").replace("", pd.NA).dropna().value_counts().head(15).reset_index()
                s.columns = ["Community Prevention Centers", "conteo"]
                fig = px.bar(
                    s.sort_values("conteo", ascending=True),
                    x="conteo", y="Community Prevention Centers", orientation="h", text="conteo",
                    template="plotly_dark",
                    title="Top Community Prevention Centers (por frecuencia)"
                )
                fig.update_traces(textposition="outside", cliponaxis=False)
                fig.update_layout(height=620, margin=dict(l=10, r=10, t=60, b=10))
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("### 📌 Suma de Beneficiaries por Cantón")
                g = dfg.groupby("Canton", dropna=True)["Beneficiaries"].sum().sort_values(ascending=False).head(15).reset_index()
                fig2 = px.bar(
                    g.sort_values("Beneficiaries", ascending=True),
                    x="Beneficiaries", y="Canton", orientation="h", text="Beneficiaries",
                    template="plotly_dark",
                    title="Beneficiaries (suma) por Cantón"
                )
                fig2.update_traces(textposition="outside", cliponaxis=False)
                fig2.update_layout(height=620, margin=dict(l=10, r=10, t=60, b=10))
                st.plotly_chart(fig2, use_container_width=True)

            # Página 3: empleabilidad
            elif page_sel == "Página 3":
                st.markdown("### 📌 Suma matriculadas vs egresadas (Top 15 cantones)")
                g = dfg.groupby("Canton", dropna=True)[
                    ["Cantidad de personas matriculadas", "Cantidad de personas egresadas"]
                ].sum().sort_values("Cantidad de personas matriculadas", ascending=False).head(15).reset_index()

                g_m = g.melt(id_vars=["Canton"], var_name="tipo", value_name="cantidad")

                fig = px.bar(
                    g_m,
                    x="cantidad",
                    y="Canton",
                    color="tipo",
                    orientation="h",
                    template="plotly_dark",
                    title="Matriculadas vs Egresadas (suma) por Cantón — Top 15"
                )
                fig.update_layout(height=700, margin=dict(l=10, r=10, t=60, b=10))
                st.plotly_chart(fig, use_container_width=True)

            # Página 4: bandas
            elif page_sel == "Página 4":
                st.markdown("### 📌 Beneficiarios por provincia (suma)")
                g = dfg.groupby("provincia", dropna=True)["Beneficiarios"].sum().sort_values(ascending=False).reset_index()
                fig = px.bar(
                    g.sort_values("Beneficiarios", ascending=True),
                    x="Beneficiarios", y="provincia", orientation="h", text="Beneficiarios",
                    template="plotly_dark",
                    title="Beneficiarios (suma) por provincia"
                )
                fig.update_traces(textposition="outside", cliponaxis=False)
                fig.update_layout(height=520, margin=dict(l=10, r=10, t=60, b=10))
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("### 📌 Top clubes/bandas por beneficiarios")
                g2 = dfg.groupby("Nombre de club o banda", dropna=True)["Beneficiarios"].sum().sort_values(ascending=False).head(15).reset_index()
                fig2 = px.bar(
                    g2.sort_values("Beneficiarios", ascending=True),
                    x="Beneficiarios", y="Nombre de club o banda", orientation="h", text="Beneficiarios",
                    template="plotly_dark",
                    title="Top 15 clubes/bandas por beneficiarios (suma)"
                )
                fig2.update_traces(textposition="outside", cliponaxis=False)
                fig2.update_layout(height=700, margin=dict(l=10, r=10, t=60, b=10))
                st.plotly_chart(fig2, use_container_width=True)

            # Página 5: factores
            else:
                st.markdown("### 📌 Frecuencia de factores (Top 15)")
                expl = []
                for _, r in dfg.iterrows():
                    txt = str(r.get("factores","") or "")
                    parts = [p.strip() for p in txt.split("|") if p.strip()]
                    expl.extend(parts)

                if not expl:
                    st.info("No hay factores aún.")
                else:
                    s = pd.Series(expl).value_counts().head(15).reset_index()
                    s.columns = ["factor","conteo"]
                    fig = px.bar(
                        s.sort_values("conteo", ascending=True),
                        x="conteo", y="factor", orientation="h", text="conteo",
                        template="plotly_dark",
                        title="Top factores"
                    )
                    fig.update_traces(textposition="outside", cliponaxis=False)
                    fig.update_layout(height=700, margin=dict(l=10, r=10, t=60, b=10))
                    st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.markdown("#### Datos base (según página)")
        hide_df_index(dfg.head(500))




