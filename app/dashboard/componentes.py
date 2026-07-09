"""
COMPONENTES
============
Elementos de UI reutilizables entre paginas del dashboard.
"""
import streamlit as st


def fila_clicable(contenido_html, key):
    """Renderiza contenido_html dentro de un contenedor con un boton
    invisible superpuesto. Devuelve True si se ha pulsado en este render,
    sin provocar una recarga de pagina (a diferencia de <a href>).
    El CSS que hace esto funcionar esta en estilo.py, con selectores
    'st-key-clic_*' y 'st-key-btn_*'."""
    with st.container(key=f"clic_{key}"):
        st.markdown(contenido_html, unsafe_allow_html=True)
        return st.button("", key=f"btn_{key}")
