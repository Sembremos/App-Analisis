# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ==========================================================
# CONFIG (TU HOJA)
# ==========================================================
# LINK: https://docs.google.com/spreadsheets/d/1pCUXSJ_hvQzpzBTaJ-h0ntcdhYwMTyWomxXMjmi7lyg/edit?usp=sharing
SHEET_ID = "1pCUXSJ_hvQzpzBTaJ-h0ntcdhYwMTyWomxXMjmi7lyg"
WORKSHEET_NAME = "Hoja 1"  # o cambia al nombre real de la pestaña

# Encabezados recomendados (puedes cambiarlos luego)
HEADERS = [
    "date", "barrio", "factores", "delitos_relacionados",
    "ligado_estructura", "nombre_estructura", "observaciones", "maps_link"
]

# ==========================================================
# GSPREAD: CONEXIÓN ÚNICA + HOJA LISTA
# ==========================================================
@st.cache_resource(show_spinner=False)
def get_ws():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)

    # Abrir o crear worksheet
    try:
        ws = sh.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=WORKSHEET_NAME, rows=2000, cols=len(HEADERS) + 10)

    # Asegurar encabezados en fila 1
    current = [h.strip() for h in ws.row_values(1)]
    if not current:
        ws.append_row(HEADERS, value_input_option="USER_ENTERED")
    else:
        # si faltan columnas, las agregamos al final
        missing = [h for h in HEADERS if h not in current]
        if missing:
            ws.update_cell(1, len(current) + 1, missing[0])
            # si hay más de una, las ponemos seguidas
            if len(missing) > 1:
                ws.update(
                    gspread.utils.rowcol_to_a1(1, len(current) + 1) + ":" +
                    gspread.utils.rowcol_to_a1(1, len(current) + len(missing)),
                    [missing]
                )

    return ws

def get_headers(ws):
    return [h.strip() for h in ws.row_values(1)]

@st.cache_data(ttl=20, show_spinner=False)
def read_df() -> pd.DataFrame:
    ws = get_ws()
    records = ws.get_all_records()  # usa fila 1 como headers
    return pd.DataFrame(records) if records else pd.DataFrame(columns=get_headers(ws))

def append_row(data: dict):
    """
    Inserta 1 fila en la hoja respetando el orden de columnas del Sheet.
    `data` debe traer claves como los headers.
    """
    ws = get_ws()
    headers = get_headers(ws)
    row = [data.get(h, "") for h in headers]
    ws.append_row(row, value_input_option="USER_ENTERED")

# ==========================================================
# PRUEBA RÁPIDA DE CONEXIÓN (UI)
# ==========================================================
st.title("✅ Prueba de conexión Google Sheets (DB)")

ws = get_ws()
st.success(f"Conectado a: {SHEET_ID} | Pestaña: {WORKSHEET_NAME}")

if st.button("Insertar fila de prueba"):
    append_row({
        "date": "22-12-2025",
        "barrio": "Prueba",
        "factores": "Factor X",
        "delitos_relacionados": "N/A",
        "ligado_estructura": "No",
        "nombre_estructura": "",
        "observaciones": "Fila insertada desde Streamlit",
        "maps_link": "https://www.google.com/maps?q=9.8814,-85.5233"
    })
    st.cache_data.clear()
    st.success("Fila insertada ✅")

df = read_df()
st.write("Vista de datos:")
st.dataframe(df, use_container_width=True)


