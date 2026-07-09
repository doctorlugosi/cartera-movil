import streamlit as st


def mostrar():
    st.markdown(
        "<p style='color:#848E9C;font-size:13px;text-align:center;margin:24px 0;'>"
        "La pestana Sistema (logs de actualizacion) no esta disponible en la "
        "version movil, ya que depende de archivos locales del PC.</p>",
        unsafe_allow_html=True,
    )
