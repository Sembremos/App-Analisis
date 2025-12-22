import streamlit as st

st.title("🔍 Ver correo del Service Account")

st.write("Service Account email:")
st.code(st.secrets["gcp_service_account"]["client_email"])
