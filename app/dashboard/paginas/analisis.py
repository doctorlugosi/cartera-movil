"""
PESTANA ANALISIS
================
Informe comparativo entre la distribucion OBJETIVO (imports/clasificacion/
objetivo_distribucion.csv + objetivo_sectores.csv) y la distribucion REAL de la
cartera. Dos vistas:
  A) Semaforo   -> desviacion en puntos porcentuales por pilar (verde/ambar/rojo).
  B) Rebalanceo -> cuanto sobra/falta en euros para cuadrar cada pilar.
Al pulsar un pilar se despliega su detalle (nivel 2/3). Los sectores de la cartera
de dividendos se comparan contra el escenario macro seleccionado.
"""
import streamlit as st
import sys
import os

RUTA_DASHBOARD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RUTA_DASHBOARD not in sys.path:
    sys.path.insert(0, RUTA_DASHBOARD)

from datos import objetivo
from utilidades import formato_eur
from componentes import fila_clicable

# Colores/nombres por pilar (locales, para no depender de distribucion.py y que la
# pestana cargue tambien en la web movil).
COLORES = {
    'RENTA_VARIABLE': '#FFD54A', 'LIQUIDEZ': '#848E9C', 'MATERIAS_PRIMAS': '#F0B90B',
    'CRIPTOACTIVOS': '#D4921A', 'INVERSIONES_ALTERNATIVAS': '#B8860B',
    'RENTA_FIJA': '#8B6914', 'INMOBILIARIO': '#A67C52', 'NEGOCIOS': '#6E4506',
}
NOMBRES_COMPLETOS = {
    'RENTA_VARIABLE': 'Renta Variable', 'LIQUIDEZ': 'Liquidez',
    'MATERIAS_PRIMAS': 'Materias Primas', 'CRIPTOACTIVOS': 'Criptoactivos',
    'INVERSIONES_ALTERNATIVAS': 'Inversiones Alternativas', 'RENTA_FIJA': 'Renta Fija',
    'INMOBILIARIO': 'Inmobiliario', 'NEGOCIOS': 'Negocios',
}

VERDE, AMBAR, ROJO, GRIS = '#0ECB81', '#F0B90B', '#F6465D', '#848E9C'


def _pct(v):
    return f"{v:.1f}".replace('.', ',') + '%'


def _pp(v):
    return f"{v:+.1f}".replace('.', ',')


def _sem_color(desv):
    """Verde <1pp, ambar 1-3pp, rojo >3pp (en valor absoluto)."""
    if desv is None:
        return GRIS
    a = abs(desv)
    return VERDE if a < 1 else (AMBAR if a <= 3 else ROJO)


def _euros_con_signo(v):
    signo = '+' if v >= 0 else '−'
    return f"{signo}{formato_eur(abs(v))} &#8364;"


def _fila_semaforo(fila, escala, seleccionado):
    color_pilar = COLORES.get(fila['clave'], GRIS)
    sem = _sem_color(fila['desv'])
    bg = '#1E2329' if seleccionado else 'transparent'
    ancho_act = max(fila['act_pct'] / escala * 100, 0.5)
    pos_obj = min(fila['obj'] / escala * 100, 100)
    desv_txt = _pp(fila['desv']) if fila['desv'] is not None else '&mdash;'
    return (
        f"<div style='background:{bg};border-radius:6px;padding:6px 8px;display:flex;"
        f"align-items:center;gap:8px;margin-bottom:2px;'>"
        f"<span style='color:{sem};font-size:10px;width:10px;flex-shrink:0;'>&#9679;</span>"
        f"<span style='color:#EAECEF;font-size:13px;font-weight:600;width:118px;"
        f"flex-shrink:0;'>{fila['etiqueta']}</span>"
        f"<div style='flex:1;position:relative;background:#2B3139;border-radius:3px;height:8px;'>"
        f"<div style='width:{ancho_act}%;background:{color_pilar};border-radius:3px;height:8px;'></div>"
        f"<div style='position:absolute;left:{pos_obj}%;top:-2px;height:12px;width:2px;"
        f"background:#EAECEF;'></div></div>"
        f"<span style='color:#848E9C;font-size:12px;width:42px;text-align:right;'>"
        f"{fila['obj']:.0f}%</span>"
        f"<span style='color:#EAECEF;font-size:12px;width:48px;text-align:right;'>"
        f"{_pct(fila['act_pct'])}</span>"
        f"<span style='color:{sem};font-size:12px;width:52px;text-align:right;'>{desv_txt}</span>"
        f"</div>"
    )


def _fila_detalle(fila):
    sem = _sem_color(fila['desv'])
    obj_txt = f"{fila['obj']:.0f}%" if fila['obj'] is not None else '&mdash;'
    act_txt = _pct(fila['act_pct']) if fila['act_pct'] is not None else '&mdash;'
    desv_txt = _pp(fila['desv']) if fila['desv'] is not None else '&mdash;'
    nota = fila.get('nota') or ''
    nota_html = (f"<span style='color:#5C6470;font-size:10px;margin-left:6px;'>{nota}</span>"
                 if nota else '')
    return (
        f"<div style='display:flex;align-items:center;gap:8px;padding:3px 0 3px 18px;"
        f"border-bottom:1px solid #1E2329;'>"
        f"<span style='color:{sem};font-size:8px;width:8px;flex-shrink:0;'>&#9679;</span>"
        f"<span style='color:#C7CBD1;font-size:12px;flex:1;'>{fila['etiqueta']}{nota_html}</span>"
        f"<span style='color:#848E9C;font-size:11px;width:42px;text-align:right;'>{obj_txt}</span>"
        f"<span style='color:#EAECEF;font-size:11px;width:48px;text-align:right;'>{act_txt}</span>"
        f"<span style='color:{sem};font-size:11px;width:52px;text-align:right;'>{desv_txt}</span>"
        f"</div>"
    )


def _fila_rebalanceo(fila, max_abs):
    color_pilar = COLORES.get(fila['clave'], GRIS)
    aj = fila['ajuste_eur']
    ancho = min(abs(aj) / max_abs * 50, 50) if max_abs else 0
    color = VERDE if aj >= 0 else ROJO
    if aj >= 0:
        barra = (f"<div style='position:absolute;left:50%;top:0;height:10px;width:{ancho}%;"
                 f"background:{color};border-radius:0 3px 3px 0;'></div>")
    else:
        barra = (f"<div style='position:absolute;right:50%;top:0;height:10px;width:{ancho}%;"
                 f"background:{color};border-radius:3px 0 0 3px;'></div>")
    return (
        f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:3px;'>"
        f"<span style='color:{color_pilar};font-size:9px;width:9px;flex-shrink:0;'>&#9679;</span>"
        f"<span style='color:#EAECEF;font-size:12px;width:118px;flex-shrink:0;'>"
        f"{fila['etiqueta']}</span>"
        f"<div style='flex:1;position:relative;background:#2B3139;border-radius:3px;height:10px;'>"
        f"<div style='position:absolute;left:50%;top:-2px;height:14px;width:1px;background:#4A525C;'></div>"
        f"{barra}</div>"
        f"<span style='color:{color};font-size:12px;width:96px;text-align:right;'>"
        f"{_euros_con_signo(aj)}</span></div>"
    )


def mostrar():
    st.markdown("<p style='color:#EAECEF;font-size:15px;font-weight:700;margin:0 0 2px;'>"
                "Distribución objetivo vs actual</p>", unsafe_allow_html=True)

    if 'escenario_sector' not in st.session_state:
        st.session_state.escenario_sector = 'estable'
    if 'analisis_pilar_sel' not in st.session_state:
        st.session_state.analisis_pilar_sel = None

    filas, total = objetivo.comparativa_pilares()
    escala = max(max(f['obj'], f['act_pct']) for f in filas) or 1.0

    # --- A) SEMAFORO ---
    st.markdown(
        "<div style='display:flex;align-items:center;gap:8px;color:#848E9C;font-size:10px;"
        "font-weight:700;padding:2px 8px 4px;'>"
        "<span style='width:10px;flex-shrink:0;'></span>"
        "<span style='width:118px;flex-shrink:0;'>PILAR</span>"
        "<span style='flex:1;'>ACTUAL vs OBJETIVO</span>"
        "<span style='width:42px;text-align:right;'>OBJ.</span>"
        "<span style='width:48px;text-align:right;'>ACT.</span>"
        "<span style='width:52px;text-align:right;'>DESV.</span></div>",
        unsafe_allow_html=True)

    for fila in filas:
        sel = st.session_state.analisis_pilar_sel == fila['clave']
        html = _fila_semaforo(fila, escala, sel)
        if fila_clicable(html, key=f"an_{fila['clave']}"):
            st.session_state.analisis_pilar_sel = None if sel else fila['clave']
            st.rerun()

    st.markdown(
        f"<div style='display:flex;gap:14px;color:#5C6470;font-size:10px;margin:6px 0 2px 8px;'>"
        f"<span><span style='color:{VERDE};'>&#9679;</span> &lt;1pp</span>"
        f"<span><span style='color:{AMBAR};'>&#9679;</span> 1&ndash;3pp</span>"
        f"<span><span style='color:{ROJO};'>&#9679;</span> &gt;3pp</span>"
        f"<span style='margin-left:auto;'>| marca blanca = objetivo</span></div>",
        unsafe_allow_html=True)

    # --- Detalle del pilar seleccionado (drill-down) ---
    sel = st.session_state.analisis_pilar_sel
    if sel:
        st.markdown("<div style='border-top:1px solid #2B3139;margin:8px 0 6px;'></div>",
                    unsafe_allow_html=True)
        color_sel = COLORES.get(sel, AMBAR)
        st.markdown(
            f"<p style='color:{color_sel};font-size:13px;font-weight:700;margin:0 0 4px;'>"
            f"{NOMBRES_COMPLETOS.get(sel, sel)} &mdash; detalle</p>", unsafe_allow_html=True)

        if sel == 'RENTA_VARIABLE':
            opciones = {lbl: cod for cod, lbl in objetivo.ESCENARIOS}
            actual_lbl = next(lbl for cod, lbl in objetivo.ESCENARIOS
                              if cod == st.session_state.escenario_sector)
            elegido = st.radio("Escenario macro (sectores de dividendos)",
                               list(opciones.keys()),
                               index=list(opciones.keys()).index(actual_lbl),
                               horizontal=True, key="radio_escenario")
            if opciones[elegido] != st.session_state.escenario_sector:
                st.session_state.escenario_sector = opciones[elegido]
                st.rerun()

        bloques = objetivo.subcomparativa(sel, st.session_state.escenario_sector)
        if not bloques:
            st.markdown("<p style='color:#5C6470;font-size:12px;'>"
                        "Este pilar no tiene subdivisión definida en el objetivo.</p>",
                        unsafe_allow_html=True)
        for titulo, filas_det in bloques:
            st.markdown(
                f"<p style='color:#848E9C;font-size:11px;font-weight:700;margin:8px 0 2px;'>"
                f"{titulo}</p>", unsafe_allow_html=True)
            for f in filas_det:
                st.markdown(_fila_detalle(f), unsafe_allow_html=True)

    # --- B) REBALANCEO EN EUROS ---
    st.markdown("<div style='border-top:1px solid #2B3139;margin:10px 0 6px;'></div>",
                unsafe_allow_html=True)
    st.markdown("<p style='color:#EAECEF;font-size:13px;font-weight:700;margin:0 0 6px;'>"
                "Rebalanceo &mdash; cuánto mover para cuadrar</p>", unsafe_allow_html=True)

    reb = sorted(filas, key=lambda f: -abs(f['ajuste_eur']))
    max_abs = max((abs(f['ajuste_eur']) for f in reb), default=1.0) or 1.0
    for fila in reb:
        st.markdown(_fila_rebalanceo(fila, max_abs), unsafe_allow_html=True)
    st.markdown(
        f"<div style='display:flex;gap:16px;color:#5C6470;font-size:10px;margin-top:6px;'>"
        f"<span><span style='color:{VERDE};'>&#9679;</span> falta (comprar)</span>"
        f"<span><span style='color:{ROJO};'>&#9679;</span> sobra (vender)</span></div>",
        unsafe_allow_html=True)
