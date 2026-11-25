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
  Se pintan con ICONOS, no con círculos, y sin leyenda (los eligió Jose el 25-11-2026): un ✓ en
  un círculo verde, un triángulo de aviso ámbar, una ✗ en un círculo rojo y un reloj gris si está
  pendiente.

LO FISCAL va al final, en una pestaña que se despliega (decisión suya, 23-11-2026): el IRPF del
ahorro que toca pagar y qué pérdidas latentes se pueden realizar para bajarlo, por pilar. Los
datos son los de la hoja FISCAL del plan (que salen de la cadena de KUBER); lo único de aquí es
la simulación al marcar o quitar un pilar, con la MISMA escala de la hoja, y la pestaña avisa si
la escala no da la cuota de la hoja.

La cartera llega en un paso siguiente.
"""
import json
import os
import sqlite3
import sys
from datetime import date
from html import escape

import streamlit as st

RUTA_DASHBOARD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RUTA_DASHBOARD not in sys.path:
    sys.path.insert(0, RUTA_DASHBOARD)

from datos import consultas
from estilo import AMARILLO, VERDE, ROJO, GRIS_DESACTIVADO
from utilidades import formato_eur
from componentes import fila_clicable

JSON_PANEL = os.path.join(os.path.dirname(RUTA_DASHBOARD), 'exports', 'plan_panel.json')
TOLERANCIA = 0.5          # euros que se dan por iguales (redondeos de céntimos)

MES_C = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
MES_L = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']

# (clave en el JSON, nombre, más es mejor)
ASPECTOS = (('ahorro', 'Ahorro', True), ('gasto', 'Gastos', False),
            ('ingresos', 'Ingresos', True))

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
.pl-p{display:inline-block;width:10px;height:10px;border-radius:50%;flex:none}
.pl-h2{font-size:15px;font-weight:700;color:#EAECEF;margin:14px 0 8px}
.pl-h2 small{font-weight:400;color:#848E9C;font-size:12px;margin-left:6px}
.pl-caja{background:#1E2329;border-radius:12px;padding:12px;margin-bottom:10px}
.pl-cab{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.pl-cab b{font-size:14px;color:#EAECEF}
.pl-cab span{display:flex;gap:12px;font-size:11px;color:#848E9C;align-items:center}
.pl-cab span span{gap:4px}
.pl-ic{display:inline-block;flex:none;vertical-align:-3px}
.pl-lin{display:grid;grid-template-columns:40px 1fr;gap:4px 8px;align-items:center;margin:6px 0 8px}
.pl-q{font-size:11px;color:#848E9C}
.pl-pista{position:relative;height:10px;background:#2B3139;border-radius:5px}
.pl-pista b{position:absolute;top:0;bottom:0;border-radius:5px}
.pl-pista em{position:absolute;top:-4px;width:2px;height:18px;margin-left:-1px;background:#EAECEF}
.pl-pista i{position:absolute;top:-2px;width:1px;height:14px;background:#848E9C}
.pl-nums{grid-column:2;display:flex;justify-content:space-between;gap:8px;font-size:11px;color:#C7CBD1}
.pl-gris{color:#848E9C}
.pl-nota{font-size:11px;color:#848E9C;margin:-2px 0 10px;line-height:1.4}
.pl-o{font-size:12px;color:#C7CBD1}
.pl-pt{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.pl-pl{font-size:13px;color:#848E9C;font-weight:600}
.pl-pl .pl-ic{margin-left:6px}
.pl-pv{font-size:22px;font-weight:700;color:#F0B90B;line-height:1.2;margin:3px 0;white-space:nowrap}
.pl-po{font-size:12px;color:#C7CBD1}
.pl-barra{height:16px;border:2px solid #EAECEF;border-radius:8px;overflow:hidden;margin:14px 0 6px}
.pl-barra b{display:block;height:100%;background:#F0B90B}
.pl-pie2{display:flex;justify-content:space-between;font-size:13px;color:#EAECEF}
.pl-aviso{background:#1E2329;border-radius:12px;padding:14px;font-size:13px;color:#C7CBD1;line-height:1.45}
div[class*="st-key-plan_meses"] div[role="radiogroup"]{display:grid !important;width:100% !important;
  grid-template-columns:repeat(6,minmax(0,1fr));gap:6px !important}
div[class*="st-key-plan_meses"] div[role="radiogroup"] > label{margin:0 !important;min-width:0 !important}
div[class*="st-key-plan_fiscal"] [data-testid="stVerticalBlock"]{gap:6px !important}
div[data-testid="stExpander"] summary,div[data-testid="stExpander"] summary:hover,
div[data-testid="stExpander"] summary:focus,div[data-testid="stExpander"] summary:focus-visible{
  background:#1E2329 !important;color:#EAECEF !important}
div[data-testid="stExpander"] summary p{font-size:15px !important;font-weight:700 !important}
.pl-fc{background:#0B0E11;border-radius:10px;padding:12px;margin-bottom:8px}
.pl-fl{font-size:11px;color:#848E9C;font-weight:600}
.pl-fv{font-size:24px;font-weight:700;color:#EAECEF;margin:4px 0 2px;line-height:1.15}
.pl-fs{font-size:11px;color:#C7CBD1;line-height:1.35}
.pl-ft{font-size:12px;color:#848E9C;margin:6px 0 0}
.pl-fp{display:grid;grid-template-columns:36px 1fr auto;gap:6px 10px;align-items:center;
  background:#0B0E11;border-radius:10px;padding:10px 12px}
.pl-sw{position:relative;display:inline-block;width:36px;height:20px;border-radius:10px;background:#2B3139}
.pl-sw::after{content:"";position:absolute;top:3px;left:3px;width:14px;height:14px;border-radius:50%;
  background:#848E9C}
.pl-sw.on{background:#0ECB81}
.pl-sw.on::after{left:19px;background:#0B0E11}
.pl-sw.no{opacity:.35}
.pl-fn{display:flex;flex-direction:column;font-size:13px;font-weight:600;color:#EAECEF;min-width:0}
.pl-fa{display:flex;flex-direction:column;text-align:right;font-size:13px;font-weight:700;color:#EAECEF}
.pl-fn small,.pl-fa small{font-size:11px;font-weight:400;color:#848E9C;margin-top:2px}
.pl-fb{grid-column:2 / 4;height:6px;background:#2B3139;border-radius:3px;overflow:hidden}
.pl-fb b{display:block;height:6px}
.pl-det{margin:0 0 4px 12px;font-size:12px;color:#C7CBD1}
.pl-det summary{cursor:pointer;color:#848E9C;padding:2px 0 4px;list-style:none}
.pl-det summary::-webkit-details-marker{display:none}
.pl-det summary::before{content:"▸ "}
.pl-det[open] summary::before{content:"▾ "}
.pl-pos{display:flex;justify-content:space-between;gap:10px;padding:4px 0;border-top:1px solid #2B3139}
.pl-pos em{font-style:normal;font-size:10px;color:#F0B90B;border:1px solid #F0B90B;border-radius:4px;
  padding:0 4px;margin-left:6px;white-space:nowrap}
.pl-tot{display:flex;justify-content:space-between;gap:10px;font-size:13px;font-weight:700;color:#EAECEF;
  border-top:1px solid #2B3139;margin-top:4px;padding-top:8px}
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


# el semáforo como icono: (color del trazo, dibujo) según el color que da _sem()
_ICONOS = {
    VERDE: (VERDE, "<circle cx='12' cy='12' r='9'/><path d='M8 12.4l2.7 2.7L16.2 9.6'/>"),
    AMARILLO: (AMARILLO, "<path d='M12 3.6L21.4 19.8H2.6z'/><path d='M12 9.6v4.6'/>"
                         "<circle cx='12' cy='17' r='1.1' fill='#F0B90B' stroke='none'/>"),
    ROJO: (ROJO, "<circle cx='12' cy='12' r='9'/><path d='M9 9l6 6M15 9l-6 6'/>"),
    GRIS_DESACTIVADO: ('#848E9C', "<circle cx='12' cy='12' r='9'/><path d='M12 7.5V12l3 2'/>"),
}


def _icono(color):
    """✓ si cumple, triángulo si falla por poco, ✗ si no cumple y un reloj si está pendiente."""
    trazo, dibujo = _ICONOS.get(color, _ICONOS[GRIS_DESACTIVADO])
    return (f"<svg class='pl-ic' viewBox='0 0 24 24' width='16' height='16' fill='none' "
            f"stroke='{trazo}' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'>"
            f"{dibujo}</svg>")


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
            f"<span><span>mes{_icono(c_mes)}</span><span>año{_icono(c_ano)}</span></span></div>"
            + linea(etq_mes, mes, c_mes) + linea('Año', ano, c_ano) + "</div>")


def _patrimonio(m, obj_fin):
    """Patrimonio invertido, como lo pidió Jose (25-11-2026): a la izquierda el mes, con su
    patrimonio en grande y amarillo y el objetivo debajo; al lado el año, con el mismo formato
    (el patrimonio que se lleva y el objetivo del 31-12). Debajo, solo del año, una barra de
    borde blanco y grueso que el dorado llena según lo conseguido, el porcentaje y lo que falta.
    El punto junto al mes es el semáforo del PANEL del plan (ver arriba)."""
    mes_l = MES_L[int(m['mes'][5:7]) - 1]
    o, r = m['patrimonio']
    h = "<div class='pl-h2'>Patrimonio invertido</div><div class='pl-caja'>"
    if r is None:
        return h + f"<div class='pl-o'>Sin dato de patrimonio en {mes_l}.</div></div>"
    punto = ''
    if o is not None:
        ao, ar = m['ahorro']
        if r >= o - TOLERANCIA:
            punto = _icono(VERDE)
        elif ao is not None and ar is not None and ar >= ao - TOLERANCIA:
            punto = _icono(AMARILLO)            # detrás, pero por mercado: el ahorro cumple
        elif ar is None:
            punto = _icono(GRIS_DESACTIVADO)    # detrás, con el mes aún sin cerrar
        else:
            punto = _icono(ROJO)                # detrás, y el ahorro tampoco llega
    h += (f"<div class='pl-pt'><div><div class='pl-pl'>{mes_l.capitalize()}{punto}</div>"
          f"<div class='pl-pv'>{_eur(r)}</div>"
          f"<div class='pl-po'>{'Objetivo ' + _eur(o) if o is not None else 'Sin objetivo'}</div></div>"
          f"<div><div class='pl-pl'>Anual</div><div class='pl-pv'>{_eur(r)}</div>"
          f"<div class='pl-po'>{'Objetivo ' + _eur(obj_fin) if obj_fin else 'Sin objetivo'}</div>"
          f"</div></div>")
    if obj_fin:
        av = r / obj_fin
        h += (f"<div class='pl-barra'><b style='width:{min(av, 1) * 100:.1f}%'></b></div>"
              f"<div class='pl-pie2'><span>{_pct(av, 1)}</span>"
              f"<span>Falta <b>{_eur(max(0.0, obj_fin - r))}</b></span></div>")
    return h + "</div>"


# ── lo fiscal ─────────────────────────────────────────────────────────────────────────────────
PILAR_COLOR = {'Renta variable': '#FFD54A', 'Ligados a inflación': '#E0A030',
               'Renta fija nominal': '#8B6914', 'Oro y plata': '#F0B90B', 'Liquidez': '#848E9C',
               'Cripto': '#D4921A', 'Préstamos / alternativos': '#B8860B'}


def _cuota(base, tramos):
    """La cuota de la escala del ahorro: la misma cuenta, tramo a tramo, que la hoja FISCAL."""
    return sum(max(0.0, min(base, base if hasta is None else hasta) - desde) * tipo
               for desde, hasta, tipo in tramos)


def _marginal(base, tramos):
    """El tipo del tramo en el que cae el euro siguiente: lo que ahorra un euro de pérdida."""
    for desde, hasta, tipo in tramos:
        if hasta is None or base < hasta:
            return tipo
    return tramos[-1][2]


def _seccion_fiscal(f):
    """La pestaña «Fiscal» del final: se despliega al tocarla. Cada pilar con pérdidas
    compensables se marca o se quita tocándolo, y las dos tarjetas de arriba lo recalculan.
    Las marcas son de esta sesión (no tocan las del PANEL del Excel)."""
    with st.expander(f"Fiscal {f['ano']}" if f else "Fiscal"), st.container(key="plan_fiscal"):
        if not f:
            st.markdown("<div class='pl-fs'>Sin datos fiscales: hace falta fiscal_&lt;año&gt;.json, "
                        "que deja la cadena de KUBER, y volver a generar el plan.</div>",
                        unsafe_allow_html=True)
            return
        grupos = {}
        for p in f['posiciones']:
            grupos.setdefault(p['pilar'], []).append(p)
        comp = {k: sum(-p['latente'] for p in v if not p['recompra_2m'] and p['latente'])
                for k, v in grupos.items()}
        orden = sorted(grupos, key=lambda k: (-comp[k], k))
        marcas = st.session_state.setdefault('plan_fis_marcas', {})
        for k in orden:                    # de entrada, marcado todo lo que se puede realizar
            marcas.setdefault(k, comp[k] > TOLERANCIA)
        tramos, base, marginal = f['tramos'], f['base'], _marginal(f['base'], f['tramos'])
        realizas = sum(comp[k] for k in orden if marcas[k] and comp[k] > TOLERANCIA)
        ahorras = f['cuota'] - _cuota(max(0.0, base - realizas), tramos)
        datos = f" Datos de KUBER del {_fecha(f['datos_del']):%d-%m-%Y}." if f.get('datos_del') else ''
        h = (f"<div class='pl-fc'><div class='pl-fl'>IRPF del ahorro {f['ano']} · a pagar en junio "
             f"de {f['ano'] + 1}</div><div class='pl-fv'>{_eur(f['a_pagar'])}</div>"
             f"<div class='pl-fs'>Cuota de {_eur(f['cuota'])} menos {_eur(f['retenido'])} ya "
             f"retenidos · base del ahorro {_eur(base)}</div></div>"
             f"<div class='pl-fc'><div class='pl-fl'>Si realizas las pérdidas marcadas</div>"
             f"<div class='pl-fv' style='color:{VERDE if realizas > TOLERANCIA else '#EAECEF'}'>"
             f"{_eur(f['a_pagar'] - ahorras)}</div><div class='pl-fs'>")
        h += (f"Pagas {formato_eur(ahorras)} € menos · realizas {formato_eur(realizas)} € de "
              f"pérdidas · cada euro de pérdida ahorra un {_pct(marginal)}"
              if realizas > TOLERANCIA else "No hay ninguna pérdida marcada.")
        h += ("</div></div><div class='pl-ft'>Pérdidas que puedes realizar, por pilar. Toca un "
              "pilar para marcarlo o quitarlo.</div>")
        if abs(_cuota(base, tramos) - f['cuota']) >= 1:
            h += ("<div class='pl-fs' style='color:#F6465D'>Aviso: la escala no da la cuota de la "
                  "hoja FISCAL; la simulación no es fiable. Revisa el plan.</div>")
        st.markdown(h, unsafe_allow_html=True)

        tope = max([c for c in comp.values() if c > TOLERANCIA] or [1.0])
        for i, k in enumerate(orden):
            v, activo = grupos[k], comp[k] > TOLERANCIA
            on = activo and marcas[k]
            susp = sum(1 for p in v if p['recompra_2m'])
            cuenta = len(v) - susp
            pie = f"{cuenta} {'posición' if cuenta == 1 else 'posiciones'}" + \
                (f" · {susp} en suspenso" if susp else '')
            fila = (f"<div class='pl-fp'><span class='pl-sw{' on' if on else ''}"
                    f"{'' if activo else ' no'}'></span>"
                    f"<div class='pl-fn'><span>{_punto(PILAR_COLOR.get(k, '#848E9C'))} "
                    f"{escape(k)}</span><small>{pie}</small></div>"
                    f"<div class='pl-fa'>{_eur(comp[k])}<small>"
                    + (f"≈ {formato_eur(comp[k] * marginal)} € de impuesto" if activo else '—')
                    + f"</small></div><div class='pl-fb'><b style='width:{comp[k] / tope * 100:.1f}%;"
                    f"background:{VERDE if on else GRIS_DESACTIVADO}'></b></div></div>")
            if activo:
                if fila_clicable(fila, key=f"plan_fis_{i}"):
                    marcas[k] = not marcas[k]
                    st.rerun()
            else:
                st.markdown(fila, unsafe_allow_html=True)
            n = len(v)
            det = (f"<details class='pl-det'><summary>Ver "
                   f"{'la posición' if n == 1 else f'las {n} posiciones'}</summary>")
            for p in sorted(v, key=lambda p: p['latente'] or 0):
                nombre = p['nombre'].split(' - ', 1)[-1]
                tk = p['valor'] if p['valor'] not in ('', '—') else ''
                det += (f"<div class='pl-pos'><span>{escape((tk + ' · ' if tk else '') + nombre)}"
                        + ("<em>recompra reciente: no cuenta</em>" if p['recompra_2m'] else '')
                        + f"</span><span style='color:{GRIS_DESACTIVADO if p['recompra_2m'] else ROJO};"
                        f"white-space:nowrap'>{_eur(p['latente'])}</span></div>")
            st.markdown(det + "</details>", unsafe_allow_html=True)

        st.markdown(
            f"<div class='pl-tot'><span>Total marcado</span><span>{_eur(realizas)}</span></div>"
            f"<div class='pl-fs' style='margin-top:8px'>Realizar una pérdida aplaza el impuesto, no "
            f"lo gana: compras más barato y pagarás más cuando vendas. En acciones, fondos y bonos "
            f"la pérdida no cuenta si compras el mismo valor en los dos meses antes o después de "
            f"venderlo, o en el año si no cotiza en un mercado de la UE. Cada posición va en su "
            f"pilar por su tipo y su nombre.{datos} No soy asesor fiscal: confírmalo antes de "
            f"vender.</div>", unsafe_allow_html=True)


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
    h = (f"<div class='pl-h2'>Ahorro, gastos e ingresos"
         f"<small>{MES_L[int(sel[5:7]) - 1]} y lo que va de año</small></div>")
    for clave, nombre, mas in ASPECTOS:
        h += _aspecto(nombre, mas, etq_mes, m[clave], [suma(clave, 0), suma(clave, 1)], margen)
    h += "<div class='pl-nota'>Barra: lo real. Raya blanca: el objetivo.</div>"
    obj_fin = next((x['patrimonio'][0] for x in meses if x['mes'] == f"{ano}-12"), None)
    h += _patrimonio(m, obj_fin)
    st.markdown(h, unsafe_allow_html=True)
    _seccion_fiscal(d.get('fiscal'))
