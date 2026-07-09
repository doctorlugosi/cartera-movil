NEGRO = "#0B0E11"
GRIS_TARJETA = "#1E2329"
GRIS_TARJETA_ACTIVA = "#2B3139"
AMARILLO = "#F0B90B"
AMARILLO_CLARO = "#FFD54A"
BLANCO = "#FFFFFF"
GRIS_TEXTO = "#848E9C"
GRIS_DESACTIVADO = "#5C6470"
VERDE = "#0ECB81"
ROJO = "#F6465D"
PALETA_PILARES = [AMARILLO_CLARO, AMARILLO, "#E0A030", "#C98A1F", "#A86A14", "#8C5A0E", "#6E4506", GRIS_DESACTIVADO]

CSS_GLOBAL = """
<style>
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        background-color: #0B0E11 !important;
    }
    [data-testid="stHeader"] {
        background-color: #0B0E11 !important;
        height: 0 !important;
        min-height: 0 !important;
    }
    .block-container {
        padding-top: 0.5rem !important;
        max-width: 480px;
    }
    .stButton > button {
        background-color: #1E2329 !important;
        color: #848E9C !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
    }
    .stButton > button:hover {
        background-color: #2B3139 !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    .stButton > button[kind="primary"] {
        background-color: #0B0E11 !important;
        color: #F0B90B !important;
        border: 1px solid #F0B90B !important;
    }
    .stButton > button:disabled {
        background-color: #1E2329 !important;
        color: #5C6470 !important;
        opacity: 0.5 !important;
    }
    [data-testid="stMetricValue"] { color: #F0B90B !important; }
    [data-testid="stMetricLabel"] { color: #848E9C !important; }
    hr { border-color: #2B3139 !important; }
    .texto-gris { color: #848E9C !important; font-size: 11px; }

    /* Navegacion superior por pestañas: forzar fila unica (Streamlit
       colapsa st.columns a una columna en viewports estrechos) y
       envolverla en una unica "pildora" oscura, con icono + texto. */
    div[class*="st-key-nav_pestanas"] [data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 4px !important;
        background-color: #1E2329;
        border-radius: 10px;
        padding: 4px;
    }
    div[class*="st-key-nav_pestanas"] [data-testid="stColumn"] {
        width: auto !important;
        flex: 1 1 0 !important;
        min-width: 0 !important;
    }
    div[class*="st-key-nav_pestanas"] [data-testid="stColumn"]:last-child {
        flex: 0 0 40px !important;
    }
    div[class*="st-key-nav_pestanas"] .stButton button {
        background-color: transparent !important;
        border: 1px solid transparent !important;
        padding: 8px 4px !important;
        font-size: 12px !important;
        gap: 4px !important;
    }
    div[class*="st-key-nav_pestanas"] .stButton button[kind="primary"] {
        background-color: #0B0E11 !important;
        border: 1px solid #F0B90B !important;
    }
    div[class*="st-key-nav_pestanas"] .stButton button p {
        font-size: 12px !important;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    div[class*="st-key-nav_pestanas"] .stButton button span[data-testid="stIconMaterial"] {
        color: #848E9C !important;
    }
    div[class*="st-key-nav_pestanas"] .stButton button[kind="primary"] span[data-testid="stIconMaterial"] {
        color: #F0B90B !important;
    }

    /* Separador debajo de la navegacion: menos espacio que el hr por defecto */
    hr.separador-nav {
        margin: 6px 0 10px !important;
    }

    /* Tarjetas de plataforma (Patrimonio): forzar grid de 3 columnas
       reales en vez de que Streamlit las colapse a 1 columna en movil. */
    div[class*="st-key-tarjetas_plataforma"] [data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: wrap !important;
        gap: 6px !important;
    }
    div[class*="st-key-tarjetas_plataforma"] [data-testid="stColumn"] {
        flex: 1 1 22% !important;
        width: auto !important;
        min-width: 0 !important;
    }

    /* Distribucion: donut + barras siempre lado a lado, tambien en movil. */
    div[class*="st-key-fila_donut_barras"] [data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 8px !important;
    }
    div[class*="st-key-fila_donut_barras"] [data-testid="stColumn"] {
        min-width: 0 !important;
    }

    /* Tarjeta de detalle de pilar (Distribucion): contenedor real que
       envuelve titulo + cabecera + filas, con padding consistente. */
    div[class*="st-key-panel_detalle"] {
        background: #1E2329 !important;
        border-radius: 8px !important;
        padding: 12px 14px !important;
    }

    /* Cabecera de tabla tipo hoja de calculo (Cartera Dividendos/Crecimiento):
       cada columna es un boton, pero debe verse como texto de cabecera, no
       como un boton normal - fondo transparente, sin borde, compacto. */
    div[class*="st-key-rv_tabla_header"] [data-testid="stHorizontalBlock"] {
        gap: 2px !important;
    }
    div[class*="st-key-rv_tabla_header"] [data-testid="stColumn"] {
        min-width: 0 !important;
    }
    div[class*="st-key-rv_tabla_header"] .stButton > button {
        background-color: transparent !important;
        color: #848E9C !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 0 2px !important;
        height: auto !important;
        min-height: 0 !important;
        width: 100% !important;
        text-align: left !important;
        justify-content: flex-start !important;
    }
    div[class*="st-key-rv_tabla_header"] .stButton > button p {
        font-size: 10px !important;
        font-weight: 700 !important;
        white-space: nowrap !important;
    }
    div[class*="st-key-rv_tabla_header"] .stButton > button:hover {
        background-color: transparent !important;
        color: #F0B90B !important;
    }

    /* Boton "volver" de navegacion interna (Renta Variable, Patrimonio):
       icono solo, fuera de la tarjeta, compacto y pegado a la izquierda. */
    div[class*="st-key-rv_boton_volver"], div[class*="st-key-plataforma_boton_volver"] {
        margin-bottom: -12px;
    }
    div[class*="st-key-rv_boton_volver"] .stButton > button,
    div[class*="st-key-plataforma_boton_volver"] .stButton > button {
        padding: 6px 10px !important;
        min-height: 0 !important;
    }

    /* Radio horizontal (rango patrimonio) */
    div[data-testid="stRadio"] > label { display: none !important; }
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 6px !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label {
        background: transparent !important;
        border-radius: 4px !important;
        padding: 2px 6px !important;
        border: none !important;
        cursor: pointer !important;
        display: flex !important;
        flex: 1 !important;
        min-width: 0 !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
        background: #F0B90B !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:last-child {
        display: block !important;
        text-align: center !important;
        width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label div[data-testid="stMarkdownContainer"] {
        display: inline-block !important;
        margin: 0 !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stRadio"] > div[role="radiogroup"] > label div[data-testid="stMarkdownContainer"] p * {
        font-size: 13px !important;
        font-weight: 600 !important;
        color: #848E9C !important;
        margin: 0 !important;
        line-height: 1.1 !important;
        white-space: nowrap !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) div[data-testid="stMarkdownContainer"] p * {
        color: #0B0E11 !important;
    }

    /* Radio de distribucion: ocultar el que tiene opcion __ninguno__ */
    div[data-testid="stRadio"]:has(input[value="__ninguno__"]) {
        display: none !important;
    }

    /* Filas clicables: bloque HTML con un boton de Streamlit invisible
       superpuesto encima, para capturar el click sin recargar la pagina
       (evita el "flash" de <a href>) y sin mostrar el boton. */
    div[class*="st-key-clic_"] {
        position: relative;
    }
    div[class*="st-key-clic_"] div[class*="st-key-btn_"] {
        position: absolute !important;
        inset: 0 !important;
        width: 100% !important;
        height: 100% !important;
        margin: 0 !important;
    }
    div[class*="st-key-clic_"] div[class*="st-key-btn_"] div[data-testid="stButton"],
    div[class*="st-key-clic_"] div[class*="st-key-btn_"] button {
        width: 100% !important;
        height: 100% !important;
    }
    div[class*="st-key-clic_"] div[class*="st-key-btn_"] button {
        min-height: 0 !important;
        opacity: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        border: none !important;
        background: transparent !important;
        cursor: pointer !important;
    }

    /* Inputs de texto y selectbox (filtro/orden de tablas) */
    [data-testid="stTextInput"] input,
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        background-color: #1E2329 !important;
        color: #EAECEF !important;
        border: 1px solid #2B3139 !important;
        border-radius: 6px !important;
    }
    [data-testid="stTextInput"] input::placeholder {
        color: #5C6470 !important;
    }
    [data-testid="stSelectbox"] svg {
        fill: #848E9C !important;
    }
    div[data-baseweb="popover"] ul[role="listbox"] {
        background-color: #1E2329 !important;
    }
    div[data-baseweb="popover"] li[role="option"] {
        background-color: #1E2329 !important;
        color: #EAECEF !important;
    }
    div[data-baseweb="popover"] li[role="option"]:hover,
    div[data-baseweb="popover"] li[aria-selected="true"] {
        background-color: #2B3139 !important;
    }

    /* Modo privado: difumina cualquier importe envuelto por formato_eur() */
    .valor-privado {
        filter: blur(12px);
        user-select: none;
    }

    /* Bloques de codigo (ej. log de Sistema) en tema oscuro */
    [data-testid="stCode"] pre, [data-testid="stCode"] code {
        background-color: #0B0E11 !important;
        color: #848E9C !important;
    }
    [data-testid="stCodeBlock"] {
        background-color: #0B0E11 !important;
    }
    div[data-testid="stExpander"] {
        background-color: #1E2329 !important;
        border: none !important;
        border-radius: 8px !important;
    }
    div[data-testid="stExpander"] summary {
        color: #EAECEF !important;
    }
</style>
"""

CSS_MODO_PRIVADO = """
<style>
    /* Modo privado: difumina tambien los graficos (ejes con importes,
       tooltips) ya que Plotly no permite envolver esos textos en un span. */
    [data-testid="stPlotlyChart"] {
        filter: blur(14px);
    }
</style>
"""


def aplicar_estilo(st, modo_privado=False):
    st.markdown(CSS_GLOBAL, unsafe_allow_html=True)
    if modo_privado:
        st.markdown(CSS_MODO_PRIVADO, unsafe_allow_html=True)