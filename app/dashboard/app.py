"""
APP.PY - Punto de entrada del dashboard de cartera
=====================================================
Ejecutar con: streamlit run dashboard\\app.py
"""
import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(__file__))
from estilo import aplicar_estilo

st.set_page_config(
    page_title="Mi Cartera",
    page_icon="💰",
    layout="centered",
    initial_sidebar_state="collapsed",
)

if 'modo_privado' not in st.session_state:
    st.session_state.modo_privado = False

aplicar_estilo(st, st.session_state.modo_privado)

# --- Navegacion por pestañas ---
PESTANAS = ["Patrimonio", "Distribución", "Sistema"]
ICONOS_PESTANA = {
    "Patrimonio":   ":material/account_balance_wallet:",
    "Distribución": ":material/donut_small:",
    "Sistema":      ":material/settings:",
}

if 'pestana_activa' not in st.session_state:
    st.session_state.pestana_activa = "Patrimonio"

with st.container(key="nav_pestanas"):
    cols = st.columns(len(PESTANAS) + 1)
    for i, nombre in enumerate(PESTANAS):
        with cols[i]:
            if st.button(
                nombre,
                icon=ICONOS_PESTANA[nombre],
                key=f"btn_{nombre}",
                use_container_width=True,
                type="primary" if st.session_state.pestana_activa == nombre else "secondary",
            ):
                st.session_state.pestana_activa = nombre
                st.rerun()
    with cols[len(PESTANAS)]:
        icono_ojo = ":material/visibility_off:" if st.session_state.modo_privado else ":material/visibility:"
        if st.button(
            "",
            icon=icono_ojo,
            key="btn_privacidad",
            use_container_width=True,
            type="primary" if st.session_state.modo_privado else "secondary",
            help="Ocultar/mostrar importes",
        ):
            st.session_state.modo_privado = not st.session_state.modo_privado
            st.rerun()

st.markdown("<hr class='separador-nav'>", unsafe_allow_html=True)

# Leer tab desde URL params
url_tab = st.query_params.get("tab", "")
if url_tab in PESTANAS:
    st.session_state.pestana_activa = url_tab

# --- Cargar la pagina correspondiente ---
if st.session_state.pestana_activa == "Patrimonio":
    from paginas import patrimonio
    patrimonio.mostrar()
elif st.session_state.pestana_activa == "Distribución":
    from paginas import distribucion
    distribucion.mostrar()
elif st.session_state.pestana_activa == "Sistema":
    from paginas import sistema
    sistema.mostrar()
