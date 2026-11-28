"""
PESTANA ANALISIS
================
Informe comparativo entre la distribucion OBJETIVO y la distribucion REAL de la cartera.
El objetivo de cada pilar lo manda el plan (exports/objetivo_vigente.json) y el de sus
partes, imports/Objetivos/objetivo_distribucion.csv y objetivo_sectores.csv (datos/objetivo.py).
Dos vistas:
  A) Cumplimiento -> que parte de su objetivo tiene cada pilar, en un anillo (100 % es justo
     lo que toca; lo que pasa de 100 % se pinta en rojo). Al tocar un pilar salen sus partes,
     cada una con una barra cuyo final es su objetivo: el dorado la llena segun lo que tiene,
     y lo que pasa de su objetivo sobresale en rojo, sin borde. Es la opcion C que eligio Jose
     el 25-11-2026, en vez del semaforo en puntos porcentuales que habia hasta entonces.
  B) Rebalanceo -> cuanto sobra/falta en euros para cuadrar cada pilar.
Los sectores de la cartera de dividendos se comparan contra la columna «estable» de
objetivo_sectores.csv. Hasta el 25-11-2026 habia un selector de escenario macro (crecimiento /
estable / recesion); lo quito Jose porque ya no tenia sentido.
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

VERDE, ROJO, GRIS = '#0ECB81', '#F6465D', '#848E9C'
DORADO = '#F0B90B'
TOPE_BARRA = 2.0     # en las partes, lo que pasa del doble del objetivo ya no se alarga mas
# el rotulo del primer bloque de objetivo.subcomparativa() -> como se dice en el titulo
POR_PARTES = {'Por capítulo': 'por capítulos', 'Por bloque': 'por bloques',
              'Por moneda': 'por monedas', 'Por composición': 'por composición'}

CSS = """<style>
.an-tit{color:#EAECEF;font-size:15px;font-weight:700;margin:0 0 8px}
div[class*="st-key-an_anillos"] [data-testid="stHorizontalBlock"]{flex-direction:row !important;
  flex-wrap:nowrap !important;gap:8px !important}
div[class*="st-key-an_anillos"] [data-testid="stColumn"]{flex:1 1 0 !important;width:auto !important;
  min-width:0 !important}
.an-ani{background:#1E2329;border-radius:12px;padding:10px;display:flex;gap:10px;align-items:center;
  min-width:0;border:1px solid transparent;margin-bottom:8px}
.an-ani.sel{border-color:#F0B90B}
.an-ani svg{flex:none}
.an-ani .t{min-width:0}
.an-ani .n{font-size:12.5px;font-weight:700;color:#EAECEF;line-height:1.2}
.an-ani .x{font-size:11px;color:#848E9C;white-space:nowrap;line-height:1.35}
.an-ani .x b,.an-cn small b{font-weight:600}
.an-re{color:#F0B90B}
.an-ob{color:#EAECEF}
.an-caja{background:#1E2329;border-radius:12px;padding:12px;margin-top:2px}
.an-h{font-size:13px;font-weight:700;color:#EAECEF;margin-bottom:2px}
.an-bt{font-size:11px;font-weight:700;color:#848E9C;margin:12px 0 0}
.an-cum{display:grid;grid-template-columns:1fr auto;gap:5px 8px;align-items:center;padding:8px 0;
  border-top:1px solid #2B3139}
.an-bt + .an-cum,.an-h + .an-cum{border-top:0}
.an-cn{font-size:12.5px;font-weight:600;color:#EAECEF;min-width:0}
.an-cn small{display:block;font-weight:400;color:#848E9C;font-size:11px}
.an-cp{font-size:13px;font-weight:700;color:#EAECEF;text-align:right}
.an-pista{grid-column:1 / 3;position:relative;height:12px}
.an-marco{position:absolute;left:0;top:0;height:12px;border:2px solid #EAECEF;border-radius:7px;
  overflow:hidden}
.an-marco b{display:block;height:100%;background:#F0B90B}
.an-sobra{position:absolute;top:2px;height:8px;background:#F6465D;border-radius:0 4px 4px 0}
.an-nota{font-size:12px;color:#5C6470;margin-top:6px}
</style>"""


def _pct(v, dec=1):
    return f"{v:.{dec}f}".replace('.', ',') + ' %'


def _pct_obj(v):
    """El objetivo tal como esta en el CSV: sin decimales si los no tiene."""
    return _pct(v, 0 if abs(v - round(v)) < 0.05 else 1)


def _euros_con_signo(v):
    signo = '+' if v >= 0 else '−'
    return f"{signo}{formato_eur(abs(v))} &#8364;"


def _anillo(ratio):
    """Anillo de 56 px: el dorado llena lo que tiene el pilar de su objetivo; lo que pasa de
    100 % se pinta en rojo encima (hasta un segundo anillo entero). None = sin objetivo."""
    r = 21
    c = 2 * 3.14159265 * r
    s = (f"<svg width='56' height='56' viewBox='0 0 56 56'><circle cx='28' cy='28' r='{r}' "
         f"fill='none' stroke='#2B3139' stroke-width='6'/>")
    if ratio is not None:
        base, extra = min(ratio, 1.0), min(max(ratio - 1.0, 0.0), 1.0)
        s += (f"<circle cx='28' cy='28' r='{r}' fill='none' stroke='{DORADO}' stroke-width='6' "
              f"stroke-dasharray='{base * c:.1f} {c:.1f}' transform='rotate(-90 28 28)'/>")
        if extra > 0:
            s += (f"<circle cx='28' cy='28' r='{r}' fill='none' stroke='{ROJO}' stroke-width='6' "
                  f"stroke-dasharray='{extra * c:.1f} {c:.1f}' transform='rotate(-90 28 28)'/>")
    txt = '—' if ratio is None else f"{ratio * 100:.0f}%"
    return (s + f"<text x='28' y='32' text-anchor='middle' font-size='12' font-weight='700' "
                f"fill='#EAECEF'>{txt}</text></svg>")


def _tarjeta(fila, seleccionado):
    """Un pilar: su anillo de cumplimiento, el real y el objetivo (en dos lineas, para que no
    parezca un porcentaje de otro porcentaje)."""
    obj, act = fila['obj'], fila['act_pct']
    ratio = act / obj if obj else None
    return (f"<div class='an-ani{' sel' if seleccionado else ''}'>{_anillo(ratio)}"
            f"<div class='t'><div class='n'>{fila['etiqueta']}</div>"
            f"<div class='x'>Real <b class='an-re'>{_pct(act)}</b></div>"
            f"<div class='x'>Objetivo <b class='an-ob'>{_pct(obj) if obj else '—'}</b></div>"
            f"</div></div>")


def _escala(filas):
    """Hasta donde llega la barra mas larga de un bloque, en veces su objetivo (1 si nadie se
    pasa, y nunca mas de TOPE_BARRA): el final de la barra de cada parte es su 100 %."""
    r = [f['act_pct'] / f['obj'] for f in filas if f.get('obj')]
    return min(max(r + [1.0]), TOPE_BARRA)


def _parte(f, escala):
    """Una parte de un pilar. La barra con borde blanco es su objetivo entero: el dorado la
    llena segun lo que tiene, y lo que pasa de su objetivo sobresale en rojo, sin borde."""
    obj, act = f.get('obj'), f['act_pct']
    if not obj:
        return (f"<div class='an-cum'><div class='an-cn'>{f['etiqueta']}"
                f"<small>Real <b class='an-re'>{_pct(act)}</b> · Sin objetivo</small></div>"
                f"<div class='an-cp' style='color:{GRIS}'>—</div></div>")
    ratio = act / obj
    marco = 100.0 / escala                              # el 100 % de su objetivo
    lleno = min(ratio, 1.0) * 100.0                     # dentro del marco
    sobra = (min(ratio, escala) - 1.0) / escala * 100.0 if ratio > 1 else 0.0
    return (f"<div class='an-cum'><div class='an-cn'>{f['etiqueta']}"
            f"<small>Real <b class='an-re'>{_pct(act)}</b> · Objetivo "
            f"<b class='an-ob'>{_pct_obj(obj)}</b></small></div>"
            f"<div class='an-cp'>{ratio * 100:.0f} %</div>"
            f"<div class='an-pista'><div class='an-marco' style='width:{marco:.2f}%'>"
            f"<b style='width:{lleno:.2f}%'></b></div>"
            + (f"<i class='an-sobra' style='left:{marco:.2f}%;width:{sobra:.2f}%'></i>"
               if sobra > 0 else '')
            + "</div></div>")


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
    st.markdown(CSS + "<p class='an-tit'>Objetivo frente a real</p>", unsafe_allow_html=True)

    if 'analisis_pilar_sel' not in st.session_state:
        st.session_state.analisis_pilar_sel = None

    filas, total = objetivo.comparativa_pilares()

    # --- A) CUMPLIMIENTO: un anillo por pilar, de dos en dos ---
    visibles = [f for f in filas if f['obj'] > 0 or f['act_pct'] > 0.05]
    with st.container(key="an_anillos"):
        for i in range(0, len(visibles), 2):
            for col, fila in zip(st.columns(2), visibles[i:i + 2]):
                with col:
                    sel = st.session_state.analisis_pilar_sel == fila['clave']
                    if fila_clicable(_tarjeta(fila, sel), key=f"an_{fila['clave']}"):
                        st.session_state.analisis_pilar_sel = None if sel else fila['clave']
                        st.rerun()

    # --- El pilar tocado, por partes ---
    sel = st.session_state.analisis_pilar_sel
    if sel:
        bloques = objetivo.subcomparativa(sel, 'estable')
        # El primer bloque es el reparto del pilar en sus partes («Por capítulo», «Por bloque»...):
        # su rótulo pasa al título («Renta variable, por capítulos», 25-11-2026) y no se repite.
        nombre = NOMBRES_COMPLETOS.get(sel, sel).capitalize()
        reparto = 'por partes'
        if bloques and bloques[0][0] in POR_PARTES:
            reparto = POR_PARTES[bloques[0][0]]
            bloques = [('', bloques[0][1])] + bloques[1:]
        h = f"<div class='an-caja'><div class='an-h'>{nombre}, {reparto}</div>"
        if not bloques:
            h += "<div class='an-nota'>Este pilar no tiene subdivisión definida en el objetivo.</div>"
        for titulo, filas_det in bloques:
            esc = _escala(filas_det)
            h += ((f"<div class='an-bt'>{titulo}</div>" if titulo else '')
                  + "".join(_parte(f, esc) for f in filas_det))
        st.markdown(h + "</div>", unsafe_allow_html=True)

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
