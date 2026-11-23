"""
PLAN · CAMINO A LA IF
======================
La pestaña del plan de independencia financiera (23-11-2026): lo que se mira cada mes para
saber cómo va el año frente a los objetivos del PLAN, el libro plan.xlsx. Diseño: el boceto 2,
opción A (barras), elegido por Jose el 23-11-2026. Pensada para el móvil.

NO CALCULA NINGÚN OBJETIVO. Lo previsto y lo real de cada mes, la fecha de salida, el
patrimonio objetivo y el margen del semáforo los escribe plan/generar_plan.py en
exports/plan_panel.json, con el libro ya calculado. Lo único de aquí son las sumas del año,
los semáforos y los textos.

EN EL MÓVIL (la web estática de stlite) no hay carpeta exports: construir_web_movil.py mete
ese JSON DENTRO de la base de datos cifrada, en la tabla plan_panel, y aquí se lee de ahí.
Nunca va en claro a GitHub Pages.

LOS SEMÁFOROS, con medio euro de tolerancia para que un céntimo de redondeo no pinte nada:
  · Ahorro, gasto e ingresos: verde si cumplen su objetivo; ámbar si fallan por menos de
    SEMAFORO_MARGEN (PARAMETROS del plan) sobre ese objetivo; rojo si fallan por más.
  · Patrimonio: la regla del PANEL del plan. Verde si va en objetivo; ámbar si va por detrás
    pero el ahorro del mes cumple (lo que falta es mercado); rojo si va por detrás y el ahorro
    tampoco llega.

La cartera y lo fiscal llegan en los pasos siguientes.
"""
import json
import os
import sqlite3
import sys
from datetime import date

import streamlit as st

RUTA_DASHBOARD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RUTA_DASHBOARD not in sys.path:
    sys.path.insert(0, RUTA_DASHBOARD)

from datos import consultas
from estilo import AMARILLO, VERDE, ROJO, GRIS_DESACTIVADO
from utilidades import formato_eur

JSON_PANEL = os.path.join(os.path.dirname(RUTA_DASHBOARD), 'exports', 'plan_panel.json')
TOLERANCIA = 0.5          # euros que se dan por iguales (redondeos de céntimos)

MES_C = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
MES_L = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']

# (clave en el JSON, nombre, más es mejor)
ASPECTOS = (('ahorro', 'Ahorro', True), ('gasto', 'Gastos', False),
            ('ingresos', 'Ingresos', True))
# lo que mueve el ahorro del mes: ahorro = nómina + rentas − gasto − impuestos
MOTIVOS = (('rentas', 'Rentas cobradas', True), ('nomina', 'Nómina y paga variable', True),
           ('gasto', 'Gasto', False), ('impuestos', 'Impuestos', False))

CSS = """<style>
.pl-tit{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin:2px 0 12px}
.pl-h1{font-size:21px;font-weight:700;color:#EAECEF;line-height:1.2}
.pl-fecha{text-align:right;font-size:11px;color:#848E9C;line-height:1.25;white-space:nowrap}
.pl-fecha b{display:block;color:#C7CBD1;font-size:13px}
.pl-grandes{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 0 6px}
.pl-grande{background:linear-gradient(160deg,rgba(240,185,11,.16),rgba(240,185,11,.03) 60%),#1E2329;
  border:1px solid #F0B90B;border-radius:14px;padding:12px;min-width:0}
.pl-et{font-size:11px;font-weight:700;color:#F0B90B;text-transform:uppercase;letter-spacing:.04em}
.pl-gv{font-size:22px;font-weight:800;color:#EAECEF;line-height:1.1;margin:6px 0 5px;white-space:nowrap}
.pl-s{font-size:11px;color:#C7CBD1;line-height:1.3}
.pl-prog{height:6px;background:#2B3139;border-radius:3px;overflow:hidden;margin:3px 0 6px}
.pl-prog b{display:block;height:6px;background:#F0B90B}
.pl-ley{display:flex;gap:12px;flex-wrap:wrap;font-size:11px;color:#848E9C;margin:2px 0 4px}
.pl-ley span{display:inline-flex;align-items:center;gap:5px}
.pl-p{display:inline-block;width:10px;height:10px;border-radius:50%;flex:none}
.pl-h2{font-size:15px;font-weight:700;color:#EAECEF;margin:14px 0 8px}
.pl-h2 small{font-weight:400;color:#848E9C;font-size:12px;margin-left:6px}
.pl-caja{background:#1E2329;border-radius:12px;padding:12px;margin-bottom:10px}
.pl-cab{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.pl-cab b{font-size:14px;color:#EAECEF}
.pl-cab span{display:flex;gap:6px;font-size:11px;color:#848E9C;align-items:center}
.pl-cab span .pl-p{margin-left:6px}
.pl-lin{display:grid;grid-template-columns:40px 1fr;gap:4px 8px;align-items:center;margin:6px 0 8px}
.pl-q{font-size:11px;color:#848E9C}
.pl-pista{position:relative;height:10px;background:#2B3139;border-radius:5px}
.pl-pista b{position:absolute;top:0;bottom:0;border-radius:5px}
.pl-pista em{position:absolute;top:-4px;width:2px;height:18px;margin-left:-1px;background:#EAECEF}
.pl-pista i{position:absolute;top:-2px;width:1px;height:14px;background:#848E9C}
.pl-nums{grid-column:2;display:flex;justify-content:space-between;gap:8px;font-size:11px;color:#C7CBD1}
.pl-gris{color:#848E9C}
.pl-nota{font-size:11px;color:#848E9C;margin:-2px 0 10px;line-height:1.4}
.pl-t{font-size:13px;font-weight:700;color:#EAECEF;margin-bottom:6px}
.pl-mot{display:grid;grid-template-columns:12px 1fr;gap:8px;align-items:start;font-size:12px;
  color:#C7CBD1;padding:4px 0;line-height:1.35}
.pl-mot .pl-p{margin-top:3px}
.pl-res{border-top:1px solid #2B3139;margin-top:6px;padding-top:8px;font-size:13px;font-weight:700}
.pl-fila{display:flex;justify-content:space-between;align-items:center;gap:8px}
.pl-qq{font-size:11px;color:#848E9C;font-weight:600}
.pl-v{font-size:20px;font-weight:700;color:#F0B90B;line-height:1.2}
.pl-o{font-size:12px;color:#C7CBD1}
.pl-der{text-align:right;font-size:13px;font-weight:700;max-width:52%}
.pl-der small{display:block;font-size:11px;font-weight:400;color:#848E9C;margin-top:2px}
.pl-pie{display:flex;justify-content:space-between;font-size:12px;color:#C7CBD1}
.pl-aviso{background:#1E2329;border-radius:12px;padding:14px;font-size:13px;color:#C7CBD1;line-height:1.45}
div[class*="st-key-plan_meses"] div[role="radiogroup"]{display:grid !important;width:100% !important;
  grid-template-columns:repeat(6,minmax(0,1fr));gap:6px !important}
div[class*="st-key-plan_meses"] div[role="radiogroup"] > label{margin:0 !important;min-width:0 !important}
</style>"""


# ── los datos ─────────────────────────────────────────────────────────────────────────────────
def cargar_panel():
    """El panel del plan: del JSON si está (en el PC) o, si no, de la base de datos (en el
    móvil, donde viaja cifrado). None si todavía no hay ninguno."""
    if os.path.exists(JSON_PANEL):
        try:
            with open(JSON_PANEL, encoding='utf-8') as f:
                return json.load(f)
        except (OSError, ValueError):
            return None
    try:
        con = consultas.conectar()
        try:
            fila = con.execute("SELECT json FROM plan_panel LIMIT 1").fetchone()
        finally:
            con.close()
        return json.loads(fila[0]) if fila else None
    except (sqlite3.Error, ValueError, TypeError):
        return None


# ── formatos ──────────────────────────────────────────────────────────────────────────────────
def _eur(x):
    """Importe con su signo («−1.234 €»), difuminado en modo privado."""
    if x is None:
        return '—'
    return ('−' if round(x) < 0 else '') + formato_eur(abs(x)) + ' €'


def _pct(x, dec=0):
    return f"{x * 100:.{dec}f}".replace('.', ',') + ' %'


def _fecha(iso):
    return date.fromisoformat(iso[:10])


def _punto(color):
    return f"<span class='pl-p' style='background:{color}'></span>"


def _sem(o, r, mas, margen):
    """Color de una cifra frente a su objetivo. `mas`: más es mejor (ahorro, ingresos)."""
    if o is None or r is None:
        return GRIS_DESACTIVADO
    if (r >= o - TOLERANCIA) if mas else (r <= o + TOLERANCIA):
        return VERDE
    fallo = (o - r) if mas else (r - o)
    return AMARILLO if fallo <= margen * max(abs(o), 1.0) else ROJO


def _diferencia(o, r, mas):
    if o is None or r is None:
        return 'pendiente'
    d = r - o
    if abs(d) < TOLERANCIA:
        return 'en el objetivo'
    if mas:
        return ('+' if d > 0 else '−') + formato_eur(abs(d)) + (' € por encima' if d > 0
                                                                 else ' € por debajo')
    return formato_eur(abs(d)) + (' € de más' if d > 0 else ' € de menos')


def _cuenta_atras(salida, hoy):
    if hoy >= salida:
        return 'Ya ha llegado'
    meses = ((salida.year - hoy.year) * 12 + salida.month - hoy.month
             - (1 if salida.day < hoy.day else 0))
    a, m = divmod(meses, 12)
    partes = ([f"{a} año" + ('s' if a != 1 else '')] if a else []) + \
             ([f"{m} mes" + ('es' if m != 1 else '')] if m else [])
    if not partes:
        return 'Falta menos de un mes'
    verbo = 'Falta' if meses == 1 or meses == 12 else 'Faltan'
    return verbo + ' ' + ' y '.join(partes)


# ── las piezas ────────────────────────────────────────────────────────────────────────────────
def _cabecera(d, pat_hoy):
    salida = _fecha(d['salida']['fecha'])
    obj = d['salida']['patrimonio_objetivo']
    h = (f"<div class='pl-tit'><div class='pl-h1'>Plan · Camino a la IF</div>"
         f"<div class='pl-fecha'>datos del<b>{_fecha(d['fecha_datos']):%d-%m-%Y}</b></div></div>"
         f"<div class='pl-grandes'>"
         f"<div class='pl-grande'><div class='pl-et'>Salida</div>"
         f"<div class='pl-gv'>{salida:%d-%m-%Y}</div>"
         f"<div class='pl-s'>{_cuenta_atras(salida, date.today())}</div></div>"
         f"<div class='pl-grande'><div class='pl-et'>Patrimonio</div>"
         f"<div class='pl-gv'>{_eur(obj)}</div>")
    if pat_hoy is not None and obj:
        av = pat_hoy / obj
        h += (f"<div class='pl-prog'><b style='width:{min(av, 1) * 100:.1f}%'></b></div>"
              f"<div class='pl-s'>Hoy {_eur(pat_hoy)} · el {_pct(av)}</div>")
    return h + "</div></div>"


def _barra(o, r, color):
    """Lo real es la barra y el objetivo la raya blanca. Admite negativos (un mes con el pago
    del IRPF tiene el ahorro previsto en negativo): la barra sale entonces a la izquierda del
    cero, que se marca con una raya gris."""
    lo = min(0.0, o or 0.0, r or 0.0)
    hi = max(0.0, o or 0.0, r or 0.0)
    ancho = (hi - lo) * 1.15 or 1.0

    def x(v):
        return (v - lo) / ancho * 100

    h = "<div class='pl-pista'>"
    if r is not None:
        a, b = sorted((x(0), x(r)))
        h += f"<b style='left:{a:.2f}%;width:{max(b - a, 0.8):.2f}%;background:{color}'></b>"
    if lo < 0:
        h += f"<i style='left:{x(0):.2f}%'></i>"
    if o is not None:
        h += f"<em style='left:{x(o):.2f}%'></em>"
    return h + "</div>"


def _aspecto(nombre, mas, etq_mes, mes, ano, margen):
    """Una tarjeta: el mes y lo que va de año, cada uno frente a su objetivo."""
    c_mes, c_ano = _sem(mes[0], mes[1], mas, margen), _sem(ano[0], ano[1], mas, margen)

    def linea(etq, par, color):
        o, r = par
        return (f"<div class='pl-lin'><span class='pl-q'>{etq}</span>{_barra(o, r, color)}"
                f"<div class='pl-nums'><span>{_eur(r)} "
                f"<span class='pl-gris'>· objetivo {_eur(o)}</span></span>"
                f"<span style='color:{color};font-weight:700'>{_diferencia(o, r, mas)}"
                f"</span></div></div>")

    return (f"<div class='pl-caja'><div class='pl-cab'><b>{nombre}</b>"
            f"<span>{_punto(c_mes)}mes{_punto(c_ano)}año</span></div>"
            + linea(etq_mes, mes, c_mes) + linea('Año', ano, c_ano) + "</div>")


def _que_ha_pasado(m, margen):
    """Lo que ha movido el ahorro del mes frente a lo previsto, de peor a mejor."""
    mes_l = MES_L[int(m['mes'][5:7]) - 1]
    h = f"<div class='pl-caja'><div class='pl-t'>Qué ha pasado en {mes_l}</div>"
    if not m['cerrado']:
        return h + ("<div class='pl-mot'><span></span><span>El mes aún no está cerrado: saldrá "
                    "cuando el extracto del banco lo cubra entero.</span></div></div>")
    motivos = []
    for clave, nombre, mas in MOTIVOS:
        o, r = m[clave]
        if o is not None and r is not None:
            motivos.append(((r - o) if mas else (o - r), nombre, o, r, mas))
    for impacto, nombre, o, r, mas in sorted(motivos, key=lambda t: t[0]):
        if abs(impacto) < 1:
            color, txt = VERDE, f"{nombre}: lo previsto ({_eur(r)})."
        else:
            color = VERDE if impacto > 0 else _sem(o, r, mas, margen)
            txt = (f"{nombre}: {_eur(r)} frente a {_eur(o)} previstos. "
                   + ('Suma ' if impacto > 0 else 'Resta ') + formato_eur(abs(impacto))
                   + " € al ahorro.")
        h += f"<div class='pl-mot'>{_punto(color)}<span>{txt}</span></div>"
    o, r = m['ahorro']
    if o is not None and r is not None:
        dif = r - o
        txt = ('Resultado: ahorras lo previsto.' if abs(dif) < TOLERANCIA else
               'Resultado: ahorras ' + formato_eur(abs(dif))
               + (' € más' if dif > 0 else ' € menos') + ' de lo previsto.')
        h += (f"<div class='pl-res' style='color:{_sem(o, r, True, margen)}'>{txt}</div>")
    return h + "</div>"


def _patrimonio(m, obj_fin, inicio_ref):
    """El patrimonio del mes frente a su objetivo y, aparte, el camino hacia el objetivo de
    fin de año. El semáforo es el del PANEL del plan (ver arriba)."""
    mes_l = MES_L[int(m['mes'][5:7]) - 1]
    o, r = m['patrimonio']
    h = "<div class='pl-h2'>Patrimonio invertido</div><div class='pl-caja'>"
    if r is None:
        return h + f"<div class='pl-o'>Sin dato de patrimonio en {mes_l}.</div></div>"
    if o is None:
        der = ''
        sub = ('Sin objetivo: la senda de referencia empieza en '
               + (f"{MES_L[int(inicio_ref[5:7]) - 1]} de {inicio_ref[:4]}" if inicio_ref
                  else 'un mes posterior'))
    else:
        ao, ar = m['ahorro']
        if r >= o - TOLERANCIA:
            color, lectura = VERDE, ''          # la diferencia ya lo dice todo
        elif ao is not None and ar is not None and ar >= ao - TOLERANCIA:
            color, lectura = AMARILLO, 'detrás por mercado: tu ahorro cumple'
        elif ar is None:
            color, lectura = GRIS_DESACTIVADO, 'detrás; el ahorro del mes aún no está cerrado'
        else:
            color, lectura = ROJO, 'detrás, y el ahorro tampoco llega'
        sub = f"Objetivo {_eur(o)}"
        der = (f"<div class='pl-der' style='color:{color}'>{_punto(color)}"
               f"<div>{_diferencia(o, r, True)}</div>"
               + (f"<small>{lectura}</small>" if lectura else '') + "</div>")
    h += (f"<div class='pl-fila'><div><div class='pl-qq'>En {mes_l}</div>"
          f"<div class='pl-v'>{_eur(r)}</div><div class='pl-o'>{sub}</div></div>{der}</div>")
    if obj_fin:
        av = r / obj_fin
        pie = ("<span style='color:#0ECB81'>objetivo del año conseguido</span>"
               if r >= obj_fin - TOLERANCIA else f"<span>faltan {_eur(obj_fin - r)}</span>")
        h += (f"<div style='margin-top:12px'><div class='pl-qq'>Hacia el objetivo de fin de año "
              f"({_eur(obj_fin)} a 31-12)</div>"
              f"<div class='pl-prog' style='margin:6px 0'><b style='width:"
              f"{min(av, 1) * 100:.1f}%'></b></div>"
              f"<div class='pl-pie'><span>{_pct(av, 1)} conseguido</span>{pie}</div></div>")
    return h + "</div>"


# ── la pestaña ────────────────────────────────────────────────────────────────────────────────
def mostrar():
    d = cargar_panel()
    if not d:
        st.markdown(CSS + "<div class='pl-tit'><div class='pl-h1'>Plan · Camino a la IF</div>"
                    "</div><div class='pl-aviso'>Todavía no hay datos del plan. Se generan con "
                    "el plan en el PC: <b>python plan\\generar_plan.py</b>, que deja "
                    "exports/plan_panel.json y vuelve a publicar el móvil.</div>",
                    unsafe_allow_html=True)
        return

    meses = d['meses']
    margen = d['semaforo_margen']
    con_dato = [m for m in meses if m['cerrado'] or m['patrimonio'][1] is not None]
    pat = [m['patrimonio'][1] for m in con_dato if m['patrimonio'][1] is not None]
    st.markdown(CSS + _cabecera(d, pat[-1] if pat else None), unsafe_allow_html=True)
    if not con_dato:
        st.markdown("<div class='pl-aviso'>El plan todavía no tiene ningún mes con datos "
                    "reales.</div>", unsafe_allow_html=True)
        return

    # el año que se mira: el de los datos o, si aún no tiene ningún mes, el último que tenga
    ano = d['fecha_datos'][:4]
    if not any(m['mes'].startswith(ano) for m in con_dato):
        ano = con_dato[-1]['mes'][:4]
    opciones = [m['mes'] for m in con_dato if m['mes'].startswith(ano)]
    with st.container(key="plan_meses"):
        sel = st.radio("Mes", opciones, index=len(opciones) - 1, horizontal=True,
                       format_func=lambda k: MES_C[int(k[5:7]) - 1],
                       label_visibility="collapsed", key=f"plan_mes_{ano}")
    m = next(x for x in meses if x['mes'] == sel)
    # lo que va de año: los meses CERRADOS del año hasta el elegido, como el PANEL
    hasta = [x for x in meses if x['mes'].startswith(ano) and x['mes'] <= sel and x['cerrado']]

    def suma(clave, i):
        return round(sum(x[clave][i] for x in hasta if x[clave][i] is not None), 2) if hasta \
            else None

    etq_mes = MES_C[int(sel[5:7]) - 1].capitalize()
    h = (f"<div class='pl-ley'><span>{_punto(VERDE)}cumple</span>"
         f"<span>{_punto(AMARILLO)}no cumple por menos del {_pct(margen)}</span>"
         f"<span>{_punto(ROJO)}no cumple</span></div>"
         f"<div class='pl-h2'>Ahorro, gastos e ingresos"
         f"<small>{MES_L[int(sel[5:7]) - 1]} y lo que va de año</small></div>")
    for clave, nombre, mas in ASPECTOS:
        h += _aspecto(nombre, mas, etq_mes, m[clave], [suma(clave, 0), suma(clave, 1)], margen)
    h += "<div class='pl-nota'>Barra: lo real. Raya blanca: el objetivo.</div>"
    h += _que_ha_pasado(m, margen)
    obj_fin = next((x['patrimonio'][0] for x in meses if x['mes'] == f"{ano}-12"), None)
    inicio_ref = next((x['mes'] for x in meses if x['patrimonio'][0] is not None), None)
    h += _patrimonio(m, obj_fin, inicio_ref)
    st.markdown(h, unsafe_allow_html=True)
