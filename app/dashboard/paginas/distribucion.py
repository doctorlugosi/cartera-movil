import streamlit as st
import plotly.graph_objects as go
import sys
import os

RUTA_DASHBOARD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RUTA_DASHBOARD not in sys.path:
    sys.path.insert(0, RUTA_DASHBOARD)

try:
    RUTA_SCRIPTS = os.path.join(RUTA_DASHBOARD, '..', 'scripts')
    if RUTA_SCRIPTS not in sys.path:
        sys.path.insert(0, RUTA_SCRIPTS)
    import red_navegador   # HTTP con huella TLS de navegador (pasa el filtro de red)
except Exception:          # en la web movil no hay scripts/: el navegador ya pasa el TLS
    import requests as red_navegador

from datos import consultas
from utilidades import formato_eur, rango_y_grafico
from componentes import fila_clicable


ETIQUETAS = {
    'RENTA_VARIABLE':           'R. var.',
    'LIQUIDEZ':                 'Liquidez',
    'MATERIAS_PRIMAS':          'M. prim.',
    'CRIPTOACTIVOS':            'Cripto',
    'INVERSIONES_ALTERNATIVAS': 'Inv. alt.',
    'RENTA_FIJA':               'R. fija',
    'INMOBILIARIO':             'Inmobil.',
    'NEGOCIOS':                 'Negocios',
}

COLORES = {
    'RENTA_VARIABLE':           '#FFD54A',
    'LIQUIDEZ':                 '#848E9C',
    'MATERIAS_PRIMAS':          '#F0B90B',
    'CRIPTOACTIVOS':            '#D4921A',
    'INVERSIONES_ALTERNATIVAS': '#B8860B',
    'RENTA_FIJA':               '#8B6914',
    'INMOBILIARIO':             '#A67C52',
    'NEGOCIOS':                 '#6E4506',
}

ORDEN = ['RENTA_VARIABLE', 'LIQUIDEZ', 'MATERIAS_PRIMAS', 'CRIPTOACTIVOS',
         'INVERSIONES_ALTERNATIVAS', 'RENTA_FIJA', 'INMOBILIARIO', 'NEGOCIOS']

ICONOS_PILAR = {
    'RENTA_VARIABLE':           'candlestick_chart',
    'LIQUIDEZ':                 'payments',
    'MATERIAS_PRIMAS':          'diamond',
    'CRIPTOACTIVOS':            'currency_bitcoin',
    'INVERSIONES_ALTERNATIVAS': 'business_center',
    'RENTA_FIJA':               'account_balance',
    'INMOBILIARIO':             'home_work',
    'NEGOCIOS':                 'storefront',
}

NOMBRES_COMPLETOS = {
    'RENTA_VARIABLE':           'Renta Variable',
    'LIQUIDEZ':                 'Liquidez',
    'MATERIAS_PRIMAS':          'Materias Primas',
    'CRIPTOACTIVOS':            'Criptoactivos',
    'INVERSIONES_ALTERNATIVAS': 'Inversiones Alternativas',
    'RENTA_FIJA':               'Renta Fija',
    'INMOBILIARIO':             'Inmobiliario',
    'NEGOCIOS':                 'Negocios',
}

TITULO_AMARILLO = '#F0B90B'

MESES_ES_CORTO = {
    1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr',
    5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Ago',
    9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'
}


def _etiqueta_mes_corto(fecha_iso):
    anio, mes = int(fecha_iso[:4]), int(fecha_iso[5:7])
    return f"{MESES_ES_CORTO[mes]} {anio % 100:02d}"


def encabezado_columnas(columnas):
    """columnas: lista de (texto, flex_o_ancho_css, alineacion)."""
    celdas = ''.join(
        f"<span style='color:#848E9C;font-size:12px;{ancho}text-align:{align};'>{texto}</span>"
        for texto, ancho, align in columnas
    )
    return (
        f"<div style='display:flex;justify-content:space-between;padding:0 0 6px;'>"
        f"{celdas}</div>"
    )


def historico_cripto_api(cripto_id, dias=180):
    """Precio (USD) de los ultimos `dias` dias hasta HOY. Con dias>90 CoinGecko
    devuelve granularidad diaria; se usan todos los puntos para una linea suave."""
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{cripto_id}/market_chart"
        r = red_navegador.get(url, params={'vs_currency': 'usd', 'days': dias}, timeout=10)
        data = r.json()['prices']
        fechas = [p[0] for p in data]
        valores = [p[1] for p in data]
        return fechas, valores
    except Exception:
        return [], []


def historico_metal_api(metal, meses=6):
    """Precio (USD/onza) de los ultimos `meses` meses via Yahoo Finance (yfinance),
    en lugar de Metals.Dev, cuyo plan solo da 30 dias. Oro = GC=F, Plata = SI=F.
    Devuelve (fechas_ms, valores) para dibujar igual que los graficos de cripto."""
    TICKER = {'oro': 'GC=F', 'plata': 'SI=F'}
    try:
        import yfinance as yf
        cierres = yf.Ticker(TICKER[metal]).history(
            period=f'{meses}mo', interval='1d')['Close'].dropna()
        fechas = [int(ts.timestamp() * 1000) for ts in cierres.index]
        valores = [float(v) for v in cierres.values]
        return fechas, valores
    except Exception:
        return [], []


_MESES_ES = {1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
             7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'}


def grafico_mini_precio(col, label, fechas_ms, valores, unidad='USD'):
    """Mini-grafico de evolucion de precio (6 meses): linea amarilla con relleno,
    eje Y ajustado al recorrido real de la serie (no al maximo) y un tick por mes
    en espanol. Compartido por los graficos de cripto y de metales."""
    from datetime import datetime
    with col:
        if not (fechas_ms and valores):
            st.markdown(f"<p style='color:#333;font-size:12px;'>{label}: sin datos</p>",
                        unsafe_allow_html=True)
            return
        dts = [datetime.fromtimestamp(f / 1000) for f in fechas_ms]
        tickvals, ticktext, visto = [], [], set()
        for dt in dts:
            clave = (dt.year, dt.month)
            if clave not in visto:
                visto.add(clave)
                tickvals.append(dt)
                ticktext.append(_MESES_ES[dt.month])
        lo, hi = min(valores), max(valores)
        pad = (hi - lo) * 0.12 or hi * 0.02
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dts, y=valores,
            line=dict(color='#F0B90B', width=1.8, shape='spline', smoothing=0.5),
            fill='tozeroy', fillcolor='rgba(240,185,11,0.10)',
            mode='lines', showlegend=False,
            hovertemplate='%{x|%d %b}: %{y:,.0f} ' + unidad + '<extra></extra>',
        ))
        fig.update_layout(
            title=dict(text=label, font=dict(color='#848E9C', size=11)),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=24, b=0), height=120,
            xaxis=dict(showgrid=False, color='#848E9C', tickfont=dict(size=9),
                       tickvals=tickvals, ticktext=ticktext, fixedrange=True),
            yaxis=dict(showgrid=True, gridcolor='#1E2329', color='#848E9C',
                       tickfont=dict(size=9), range=[lo - pad, hi + pad], fixedrange=True),
        )
        st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})


def panel_liquidez(detalle):
    # Cada cuenta se muestra en su divisa nativa (eToro en USD); el patrimonio total y
    # los % ya usan el valor convertido a EUR por detras.
    SIMBOLO = {'EUR': '&#8364;', 'USD': '$', 'GBP': '&#163;', 'GBX': '&#163;', 'CHF': 'CHF'}
    st.markdown(encabezado_columnas([
        ('Plataforma', 'flex:1;', 'left'),
        ('Divisa', 'width:70px;', 'center'),
        ('Valor', 'width:110px;', 'right'),
    ]), unsafe_allow_html=True)
    for broker, divisa, valor_nativo, _valor_eur in consultas.liquidez_cuentas():
        sym = SIMBOLO.get(divisa, divisa or '')
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;"
            f"padding:5px 0;border-bottom:1px solid #1E2329;'>"
            f"<span style='color:#EAECEF;font-size:14px;flex:1;'>{broker}</span>"
            f"<span style='color:#848E9C;font-size:14px;width:70px;text-align:center;'>{divisa}</span>"
            f"<span style='color:#EAECEF;font-size:14px;font-weight:600;width:110px;"
            f"text-align:right;'>{formato_eur(valor_nativo)} {sym}</span></div>",
            unsafe_allow_html=True
        )


def panel_materias_primas(detalle):
    st.markdown(encabezado_columnas([
        ('Activo', 'flex:1;', 'left'),
        ('Peso (kg)', 'width:80px;', 'center'),
        ('Valor', 'width:90px;', 'right'),
    ]), unsafe_allow_html=True)
    simbolos_metal = {'Oro': 'Au', 'Plata': 'Ag'}
    for row in detalle:
        nombre, broker, *_, activo_id, valor, cantidad = row
        nombre_corto = nombre.replace(f"{broker} - ", "")
        simbolo = simbolos_metal.get(nombre_corto, '')
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;"
            f"padding:5px 0;border-bottom:1px solid #1E2329;'>"
            f"<span style='display:flex;align-items:center;gap:6px;flex:1;'>"
            f"<span style='display:inline-flex;align-items:center;justify-content:center;"
            f"width:20px;height:20px;border-radius:5px;background:#2B3139;"
            f"color:#F0B90B;font-size:10px;font-weight:700;flex-shrink:0;'>{simbolo}</span>"
            f"<span style='color:#EAECEF;font-size:14px;'>{nombre_corto}</span></span>"
            f"<span style='color:#848E9C;font-size:14px;width:80px;text-align:center;'>"
            f"{cantidad:.3f} kg</span>"
            f"<span style='color:#EAECEF;font-size:14px;font-weight:600;width:90px;"
            f"text-align:right;'>{formato_eur(valor)} &#8364;</span></div>",
            unsafe_allow_html=True
        )
        for camara, cant_camara, valor_camara in consultas.materias_primas_por_camara(activo_id):
            valor_txt = f"{formato_eur(valor_camara)} &#8364;" if valor_camara is not None else "&mdash;"
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;padding:3px 0 3px 14px;'>"
                f"<span style='color:#5C6470;font-size:12px;flex:1;'>{camara}</span>"
                f"<span style='color:#5C6470;font-size:12px;width:80px;text-align:center;'>"
                f"{cant_camara:.3f} kg</span>"
                f"<span style='color:#848E9C;font-size:12px;width:90px;text-align:right;'>"
                f"{valor_txt}</span></div>",
                unsafe_allow_html=True
            )
    st.markdown("<p style='color:#848E9C;font-size:11px;margin:10px 0 4px;'>"
                "Evolucion precio USD/onza (6 meses)</p>", unsafe_allow_html=True)
    col_oro, col_plata = st.columns(2)
    for col, metal, label in [(col_oro, 'oro', 'Oro'), (col_plata, 'plata', 'Plata')]:
        fechas, valores = historico_metal_api(metal, meses=6)
        grafico_mini_precio(col, label, fechas, valores, unidad='USD')


NOMBRE_MONEDA = {'BTC': 'Bitcoin', 'ETH': 'Ethereum', 'USDC': 'USDC'}


def _num_color(pct, sufijo=''):
    if pct is None:
        return "<span style='color:#5C6470;font-size:11px;'>&mdash;</span>"
    col = '#0ECB81' if pct >= 0 else '#F6465D'
    return f"<span style='color:{col};font-size:11px;'>{pct:+.1f}%{sufijo}</span>"


def _vista_rentabilidad_cripto(arbol):
    """Segunda tarjeta: rentabilidades. Por posicion: carne (capital, valor
    actualizado, rent. real neta desde inicio) y leche (earnings, rendimiento
    ANUALIZADO sobre el valor inicial). Debajo, los graficos de BTC/ETH."""
    def _celda(valor_html, pct, sufijo='', ml=0):
        return (f"<span style='display:inline-flex;flex-direction:column;align-items:flex-end;"
                f"width:88px;margin-left:{ml}px;'>"
                f"<span style='color:#EAECEF;font-size:12px;line-height:1.25;'>{valor_html}</span>"
                f"<span style='line-height:1.1;'>{_num_color(pct, sufijo)}</span></span>")

    st.markdown(
        "<div style='display:flex;align-items:flex-end;padding:2px 0 4px;"
        "border-bottom:1px solid #2B3139;'>"
        "<span style='color:#848E9C;font-size:10px;font-weight:700;flex:1;'>POSICION</span>"
        "<span style='color:#848E9C;font-size:10px;font-weight:700;width:88px;text-align:right;'>"
        "CARNE</span>"
        "<span style='color:#848E9C;font-size:10px;font-weight:700;width:88px;text-align:right;"
        "margin-left:8px;'>LECHE</span></div>", unsafe_allow_html=True)

    for m in arbol['monedas']:
        visibles = [p for e in m['estrategias'] for p in e['posiciones']
                    if not (p.get('carne_rent') is None and (p.get('leche') or 0) <= 0.005)]
        if not visibles:
            continue
        st.markdown(
            f"<div style='color:#F0B90B;font-size:13px;font-weight:700;padding:8px 0 2px;'>"
            f"{NOMBRE_MONEDA.get(m['moneda'], m['moneda'])}</div>", unsafe_allow_html=True)
        for p in visibles:
            carne_cel = _celda(f"{formato_eur(p['carne'])} &#8364;", p.get('carne_rent'))
            leche_val = f"+{p['leche']:,.1f} &#8364;" if p.get('leche', 0) > 0.005 else "&mdash;"
            leche_cel = _celda(leche_val, p.get('leche_anual'), sufijo='/a', ml=8)
            st.markdown(
                f"<div style='display:flex;align-items:center;"
                f"padding:3px 0 3px 8px;border-bottom:1px solid #1A1D21;'>"
                f"<span style='color:#EAECEF;font-size:12px;flex:1;'>{p['nombre']}</span>"
                f"{carne_cel}{leche_cel}</div>", unsafe_allow_html=True)

    st.markdown("<p style='color:#5C6470;font-size:10px;margin:8px 0 10px;'>"
                "Carne = rentabilidad real neta del capital desde su inicio (valor actualizado). "
                "Leche = rendimiento anualizado de los earnings sobre el valor inicial.</p>",
                unsafe_allow_html=True)

    st.markdown("<p style='color:#848E9C;font-size:11px;margin:6px 0 4px;'>"
                "Evolucion precio USD (6 meses)</p>", unsafe_allow_html=True)
    col_btc, col_eth = st.columns(2)
    for col, cripto_id, label in [
            (col_btc, 'bitcoin', 'Bitcoin'), (col_eth, 'ethereum', 'Ethereum')]:
        fechas, valores = historico_cripto_api(cripto_id, dias=180)
        grafico_mini_precio(col, label, fechas, valores, unidad='USD')


def panel_criptoactivos(detalle):
    """Dos vistas: inventario (arbol Moneda->Estrategia->posiciones) y, al pulsar,
    rentabilidades (carne/leche con sus %). Los graficos van en la de rentabilidades."""
    arbol = consultas.arbol_cripto()
    if 'cripto_vista' not in st.session_state:
        st.session_state.cripto_vista = 'arbol'
    if st.session_state.cripto_vista == 'rentabilidad':
        _vista_rentabilidad_cripto(arbol)
        return

    # Inventario: todo el arbol es un unico bloque CLICABLE. Se conservan los % de
    # reparto (amarillos); se quitan solo las anotaciones verdes de leche.
    # Al pulsar en cualquier parte de la tarjeta -> vista de rentabilidades.
    filas = []
    for m in arbol['monedas']:
        filas.append(
            f"<div style='display:flex;justify-content:space-between;align-items:baseline;"
            f"padding:9px 0 5px;border-bottom:1px solid #2B3139;margin-top:6px;'>"
            f"<span style='color:#F0B90B;font-size:15px;font-weight:700;flex:1;'>"
            f"{NOMBRE_MONEDA.get(m['moneda'], m['moneda'])}</span>"
            f"<span style='color:#F0B90B;font-size:13px;font-weight:600;width:70px;"
            f"text-align:right;'>{m['pct']:.0f}%</span>"
            f"<span style='color:#EAECEF;font-size:14px;font-weight:700;width:100px;"
            f"text-align:right;'>{formato_eur(m['valor'])} &#8364;</span></div>")
        for e in m['estrategias']:
            colapsar = e['estrategia'] in ('HOLD', 'STAKING')
            nombre_estr = e['nombre']
            if colapsar:
                plataformas = ', '.join(dict.fromkeys(p['plataforma'] for p in e['posiciones']))
                nombre_estr += (f" <span style='color:#848E9C;font-weight:400;font-size:12px;'>"
                                f"({plataformas})</span>")
            filas.append(
                f"<div style='display:flex;justify-content:space-between;align-items:baseline;"
                f"padding:5px 0 2px 12px;'>"
                f"<span style='color:#EAECEF;font-size:13px;font-weight:600;flex:1;'>{nombre_estr}</span>"
                f"<span style='color:#F0B90B;font-size:12px;font-weight:600;width:70px;"
                f"text-align:right;'>{e['pct']:.0f}%</span>"
                f"<span style='color:#EAECEF;font-size:13px;font-weight:600;width:100px;"
                f"text-align:right;'>{formato_eur(e['valor'])} &#8364;</span></div>")
            if colapsar:
                continue
            for p in e['posiciones']:
                filas.append(
                    f"<div style='display:flex;justify-content:space-between;align-items:baseline;"
                    f"padding:3px 0 3px 26px;border-bottom:1px solid #1A1D21;'>"
                    f"<span style='color:#B7BDC6;font-size:12px;flex:1;'>{p['nombre']}</span>"
                    f"<span style='color:#F0B90B;font-size:11px;font-weight:600;width:70px;"
                    f"text-align:right;'>{p['pct']:.0f}%</span>"
                    f"<span style='color:#B7BDC6;font-size:12px;width:100px;text-align:right;'>"
                    f"{formato_eur(p['valor'])} &#8364;</span></div>")
    filas.append("<div style='height:8px;'></div>")   # respiro al final (ultima fila BTC)
    if fila_clicable("".join(filas), key='cripto_ver_rent'):
        st.session_state.cripto_vista = 'rentabilidad'
        st.rerun()


def panel_renta_fija(detalle):
    st.markdown(encabezado_columnas([
        ('Activo', 'flex:1;', 'left'),
        ('Sector', 'width:90px;', 'center'),
        ('Geografia', 'width:70px;', 'center'),
        ('Valor', 'width:90px;', 'right'),
    ]), unsafe_allow_html=True)
    for row in detalle:
        nombre, broker, divisa, composicion, sector, geografia, vehiculo, ticker, *_, valor, cantidad = row
        nombre_corto = nombre.replace(f"{broker} - ", "")
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;"
            f"padding:5px 0;border-bottom:1px solid #1E2329;'>"
            f"<span style='color:#EAECEF;font-size:14px;flex:1;'>{nombre_corto}</span>"
            f"<span style='color:#848E9C;font-size:14px;width:90px;text-align:center;'>"
            f"{sector or 'N/D'}</span>"
            f"<span style='color:#848E9C;font-size:14px;width:70px;text-align:center;'>"
            f"{geografia or 'N/D'}</span>"
            f"<span style='color:#EAECEF;font-size:14px;font-weight:600;width:90px;"
            f"text-align:right;'>{formato_eur(valor)} &#8364;</span></div>",
            unsafe_allow_html=True
        )


def _vista_inv_alternativa_individual(detalle):
    activo_id = st.session_state.inv_alt_activo_sel
    d = next((row for row in detalle if row[-3] == activo_id), None)
    nombre_activo = d[0].split(' - ')[-1] if d else 'Activo'

    st.markdown(
        f"<p style='color:#EAECEF;font-size:14px;font-weight:700;margin:0 0 4px;'>"
        f"{nombre_activo}</p>",
        unsafe_allow_html=True
    )

    historico_valor = consultas.historico_valoraciones_activo(activo_id, dias=730)
    if not historico_valor:
        st.markdown(
            "<p style='color:#5C6470;font-size:13px;margin:8px 0;'>"
            "Todavia no hay historico de valoraciones guardado para este activo. "
            "Se ira completando con cada actualizacion periodica.</p>",
            unsafe_allow_html=True
        )
        return

    valor_actual = historico_valor[-1][1]
    st.markdown(
        f"<p style='color:#EAECEF;font-size:28px;font-weight:600;margin:4px 0 10px;line-height:1.0;'>"
        f"{formato_eur(valor_actual)} &#8364;</p>",
        unsafe_allow_html=True
    )

    key_rango = f"inv_alt_rango_{activo_id}"
    if key_rango not in st.session_state:
        st.session_state[key_rango] = 'MAX'
    n_puntos = len(historico_valor)
    opciones_activas = [e for e, m in RANGOS_ACTIVO.items() if m is None or n_puntos >= m]
    if st.session_state[key_rango] not in opciones_activas:
        st.session_state[key_rango] = opciones_activas[-1]

    rango_sel = st.radio(
        "Rango", options=opciones_activas,
        index=opciones_activas.index(st.session_state[key_rango]),
        horizontal=True, key=f"radio_{key_rango}",
    )
    st.session_state[key_rango] = rango_sel

    meses_sel = RANGOS_ACTIVO[rango_sel]
    historico_filtrado = (
        historico_valor if meses_sel is None or n_puntos <= meses_sel else historico_valor[-meses_sel:]
    )
    fechas = [h[0] for h in historico_filtrado]
    valores = [h[1] for h in historico_filtrado]
    y_min, y_max = rango_y_grafico(valores)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=fechas, y=valores, fill='tozeroy', fillcolor='rgba(240,185,11,0.12)',
        line=dict(color='#F0B90B', width=2, shape='spline', smoothing=0.8), mode='lines',
        hovertemplate='%{x}: %{y:,.0f} &#8364;<extra></extra>',
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=8, b=0), height=180,
        xaxis=dict(showgrid=False, color='#848E9C', tickfont=dict(size=10), fixedrange=True),
        yaxis=dict(showgrid=True, gridcolor='#1E2329', color='#848E9C',
                   tickformat=',.0f', ticksuffix=' &#8364;', range=[y_min, y_max], fixedrange=True),
        hoverlabel=dict(bgcolor='#1E2329', font_color='#EAECEF'),
        showlegend=False,
    )
    st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})

    _seccion_rentabilidad_real_neta(activo_id)


def _tarjeta_rentabilidad(linea1, linea2, valor_pct):
    if valor_pct is None:
        valor_html = "<p style='font-size:18px;color:#5C6470;margin:6px 0 0;font-weight:700;line-height:1.1;'>N/A</p>"
    else:
        signo = '+' if valor_pct >= 0 else ''
        valor_html = (
            f"<p style='font-size:18px;color:#EAECEF;margin:6px 0 0;"
            f"font-weight:700;line-height:1.1;'>{signo}{valor_pct:.2f}%</p>"
        )
    return (
        "<div style='background-color:#000000;border-radius:7px;"
        "padding:8px 11px;margin-bottom:5px;'>"
        f"<p style='font-size:13px;color:#F0B90B;margin:0;"
        f"font-weight:600;line-height:1.3;'>{linea1}<br>{linea2}</p>"
        f"{valor_html}"
        "</div>"
    )


def _seccion_rentabilidad_real_neta(activo_id):
    """Tarjetas + grafico de rentabilidad 'real neta' (aportaciones/retiradas
    de capital actualizadas por IPC, ganancia gravada a la fiscalidad tipo si
    es positiva) de un activo, a partir del snapshot mensual guardado en
    historico_rentabilidad_activo. Compartido entre Inversiones Alternativas
    y Fondos/Carteras de Renta Variable."""
    historico_rent = consultas.historico_rentabilidad_mensual(activo_id)
    st.markdown(
        "<div style='border-top:1px solid #2B3139;margin:14px 0 10px;'></div>"
        "<p style='color:#848E9C;font-size:11px;margin:0 0 6px;'>"
        "Rentabilidad real neta (aportaciones/retiradas actualizadas por IPC, "
        "fiscalidad tipo aplicada)</p>",
        unsafe_allow_html=True
    )

    if not historico_rent:
        st.markdown(
            "<p style='color:#5C6470;font-size:13px;margin:8px 0;'>"
            "Todavia no hay suficiente historico de aportaciones/valor para calcular "
            "la rentabilidad de este activo.</p>",
            unsafe_allow_html=True
        )
        return

    _, acumulada_pct, doce_meses_pct = historico_rent[-1]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(_tarjeta_rentabilidad('Rentabilidad', 'acumulada', acumulada_pct), unsafe_allow_html=True)
    with col2:
        st.markdown(_tarjeta_rentabilidad('Rentabilidad 12m', 'm&oacute;vil', doce_meses_pct), unsafe_allow_html=True)

    if len(historico_rent) >= 2:
        fechas_rent = [_etiqueta_mes_corto(h[0]) for h in historico_rent]
        valores_rent = [h[1] for h in historico_rent]
        # Rango simetrico centrado en 0 (a diferencia de rango_y_grafico, pensado
        # para series de valor siempre positivas): la rentabilidad puede ser
        # negativa, asi que se deja un 30% de margen sobre el maximo absoluto
        # tanto por arriba como por abajo.
        _, y_max_r = rango_y_grafico([abs(v) for v in valores_rent], margen=0.3)

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=fechas_rent, y=valores_rent,
            line=dict(color='#F0B90B', width=2, shape='spline', smoothing=0.8),
            mode='lines+markers', marker=dict(size=5, color='#F0B90B'),
            hovertemplate='%{x}: %{y:.2f}%<extra></extra>',
        ))
        fig2.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=10, b=0), height=160,
            xaxis=dict(showgrid=False, color='#848E9C', tickfont=dict(size=10), fixedrange=True),
            yaxis=dict(showgrid=True, gridcolor='#1E2329', color='#848E9C',
                       ticksuffix=' %', range=[-y_max_r, y_max_r], fixedrange=True),
            hoverlabel=dict(bgcolor='#1E2329', font_color='#EAECEF'),
            showlegend=False,
        )
        st.plotly_chart(fig2, width='stretch', config={'displayModeBar': False})
    else:
        st.markdown(
            "<p style='color:#5C6470;font-size:11px;margin:6px 0 0;'>"
            "Solo hay 1 mes de rentabilidad guardado todavia; el grafico de evolucion "
            "se ira completando con cada actualizacion mensual.</p>",
            unsafe_allow_html=True
        )


def panel_inv_alternativas(detalle):
    if 'inv_alt_activo_sel' not in st.session_state:
        st.session_state.inv_alt_activo_sel = None

    if st.session_state.inv_alt_activo_sel is not None:
        _vista_inv_alternativa_individual(detalle)
        return

    st.markdown(encabezado_columnas([
        ('Activo', 'flex:1;', 'left'),
        ('Tipo', 'width:130px;', 'center'),
        ('Valor', 'width:90px;', 'right'),
    ]), unsafe_allow_html=True)
    # El % de cada activo sobre el total del pilar viene precalculado en metricas.
    met_alt = consultas.inv_alt_metricas()
    for row in detalle:
        nombre, broker, divisa, composicion, sector, geografia, vehiculo, ticker, *_, activo_id, valor, cantidad = row
        nombre_corto = nombre.replace(f"{broker} - ", "")
        tipo = (composicion or sector or 'N/D').capitalize()
        m = met_alt.get(activo_id)
        pct_txt = (f" <span style='color:#F0B90B;font-size:12px;font-weight:600;'>"
                   f"{m['pct']:.1f}%</span>"
                   if m and m['pct'] is not None else '')
        html = (
            f"<div style='display:flex;justify-content:space-between;"
            f"padding:5px 0;border-bottom:1px solid #1E2329;'>"
            f"<span style='color:#EAECEF;font-size:14px;flex:1;'>{nombre_corto}</span>"
            f"<span style='color:#848E9C;font-size:14px;width:130px;text-align:center;'>"
            f"{tipo}{pct_txt}</span>"
            f"<span style='color:#EAECEF;font-size:14px;font-weight:600;width:90px;"
            f"text-align:right;'>{formato_eur(valor)} &#8364;</span></div>"
        )
        if fila_clicable(html, key=f"inv_alt_{activo_id}"):
            st.session_state.inv_alt_activo_sel = activo_id
            st.rerun()


def panel_negocios(detalle):
    st.markdown(encabezado_columnas([
        ('Activo', 'flex:1;', 'left'),
        ('Sector', 'width:100px;', 'center'),
        ('Valor', 'width:90px;', 'right'),
    ]), unsafe_allow_html=True)
    for row in detalle:
        nombre, broker, divisa, composicion, sector, geografia, vehiculo, ticker, *_, valor, cantidad = row
        nombre_corto = nombre.replace(f"{broker} - ", "")
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;"
            f"padding:5px 0;border-bottom:1px solid #1E2329;'>"
            f"<span style='color:#EAECEF;font-size:14px;flex:1;'>{nombre_corto}</span>"
            f"<span style='color:#848E9C;font-size:14px;width:100px;text-align:center;'>"
            f"{sector or 'N/D'}</span>"
            f"<span style='color:#EAECEF;font-size:14px;font-weight:600;width:90px;"
            f"text-align:right;'>{formato_eur(valor)} &#8364;</span></div>",
            unsafe_allow_html=True
        )


def panel_inmobiliario(detalle):
    st.markdown(encabezado_columnas([
        ('Municipio', 'flex:1;', 'left'),
        ('Destino', 'width:110px;', 'center'),
        ('Valor', 'width:90px;', 'right'),
    ]), unsafe_allow_html=True)
    for row in detalle:
        (nombre, broker, divisa, composicion, sector, geografia, vehiculo, ticker,
         municipio, destino, porcentaje, activo_id, valor, cantidad) = row
        destino_txt = destino or 'N/D'
        if porcentaje and porcentaje < 100:
            destino_txt += f" &middot; {porcentaje:.0f}%"
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;"
            f"padding:5px 0;border-bottom:1px solid #1E2329;'>"
            f"<span style='color:#EAECEF;font-size:14px;flex:1;'>{municipio or 'N/D'}</span>"
            f"<span style='color:#848E9C;font-size:14px;width:110px;text-align:center;'>"
            f"{destino_txt}</span>"
            f"<span style='color:#EAECEF;font-size:14px;font-weight:600;width:90px;"
            f"text-align:right;'>{formato_eur(valor)} &#8364;</span></div>",
            unsafe_allow_html=True
        )


ESTRATEGIA_LABEL = {
    'DIVIDENDOS':     'Cartera Dividendos',
    'CRECIMIENTO':    'Cartera Crecimiento',
    'VALOR':          'Cartera Valor',
    'PRESERVACION':   'Cartera Preservacion',
    'SIN_ESTRATEGIA': 'Sin estrategia asignada',
}
ORDEN_ESTRATEGIAS = ['DIVIDENDOS', 'CRECIMIENTO', 'VALOR', 'PRESERVACION', 'SIN_ESTRATEGIA']


def _rv_tiles():
    rv_vehiculos, total_rv = consultas.distribucion_rv_por_vehiculo()
    etiq_vehiculo = {'ACCION': 'Acciones', 'ETF': 'ETFs', 'FONDOS': 'Fondos Value + Carteras'}
    colores_rv = {'ACCION': '#F0B90B', 'ETF': '#D4921A', 'FONDOS': '#B8860B'}
    iconos_rv = {'ACCION': 'trending_up', 'ETF': 'donut_small', 'FONDOS': 'account_balance'}

    for clave, label in etiq_vehiculo.items():
        valor, porc = rv_vehiculos.get(clave, (0, 0))
        color = colores_rv[clave]
        icono = iconos_rv[clave]
        html = (
            f"<div style='background:#1E2329;border-radius:6px;padding:10px 12px;"
            f"margin-bottom:4px;display:flex;align-items:center;justify-content:space-between;'>"
            f"<span style='display:flex;align-items:center;gap:8px;'>"
            f"<span style='font-family:&quot;Material Symbols Rounded&quot;;font-size:18px;"
            f"color:{color};'>{icono}</span>"
            f"<span style='color:#EAECEF;font-size:14px;font-weight:600;'>{label}</span>"
            f"</span>"
            f"<span style='color:{color};font-size:15px;font-weight:700;'>{porc:.1f}%</span>"
            f"</div>"
        )
        if fila_clicable(html, key=f"rv_tile_{clave}"):
            st.session_state.rv_vista = clave
            st.rerun()

    segmentos = ''.join(
        f"<div style='flex:{max(rv_vehiculos.get(clave, (0, 0))[1], 0.3)};"
        f"background:{colores_rv[clave]};height:6px;'></div>"
        for clave in etiq_vehiculo
    )
    st.markdown(
        f"<div style='display:flex;gap:2px;border-radius:3px;overflow:hidden;margin-top:6px;'>"
        f"{segmentos}</div>",
        unsafe_allow_html=True
    )


def _rv_acciones_carteras():
    datos = consultas.rv_acciones_por_estrategia()
    total_acc = sum(v[0] for v in datos.values())  # valor total de acciones (EUR)
    for clave in ORDEN_ESTRATEGIAS:
        if clave not in datos:
            continue
        valor, _carne_pct, sectores = datos[clave]
        pct_cartera = round(valor / total_acc * 100, 1) if total_acc else 0.0
        label = ESTRATEGIA_LABEL.get(clave, clave.title())
        barras = ''.join(
            f"<div style='display:flex;align-items:center;gap:6px;margin-bottom:3px;'>"
            f"<span style='color:#848E9C;font-size:11px;width:88px;flex-shrink:0;"
            f"overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'>{sec}</span>"
            f"<div style='flex:1;background:#2B3139;border-radius:3px;height:5px;'>"
            f"<div style='width:{max(pct,0.5)}%;background:#F0B90B;border-radius:3px;"
            f"height:5px;'></div></div>"
            f"<span style='color:#848E9C;font-size:11px;width:28px;text-align:right;'>"
            f"{pct:.0f}%</span></div>"
            for sec, val, pct in sectores[:10]
        )
        html = (
            f"<div style='background:#1E2329;border-radius:8px;padding:12px 14px;"
            f"margin-bottom:8px;'>"
            f"<div style='display:flex;justify-content:space-between;align-items:baseline;"
            f"margin-bottom:8px;'>"
            f"<span style='color:#EAECEF;font-size:14px;font-weight:700;'>{label}</span>"
            f"<span style='color:#EAECEF;font-size:15px;font-weight:700;'>"
            f"{pct_cartera:.1f}%</span></div>"
            f"{barras}</div>"
        )
        if fila_clicable(html, key=f"rv_cartera_{clave}"):
            st.session_state.rv_estrategia_sel = clave
            st.rerun()


def _rv_acciones_detalle_vista():
    estrategia = st.session_state.rv_estrategia_sel
    label = ESTRATEGIA_LABEL.get(estrategia, estrategia)

    datos = consultas.rv_acciones_detalle(estrategia)

    total_valor = sum(d['valor_eur'] for d in datos)
    # Cabecera: titulo de la cartera (izq) y posiciones + valor (der) en la MISMA fila
    st.markdown(
        f"<div style='display:flex;justify-content:space-between;align-items:baseline;"
        f"margin:0 0 8px;'>"
        f"<span style='color:#EAECEF;font-size:16px;font-weight:700;'>{label}</span>"
        f"<span style='color:#848E9C;font-size:12px;'>{len(datos)} posiciones &middot; "
        f"<span style='color:#EAECEF;font-size:15px;font-weight:700;'>"
        f"{formato_eur(total_valor)} &#8364;</span></span>"
        f"</div>",
        unsafe_allow_html=True
    )

    col_filtro, _ = st.columns([2, 3])
    with col_filtro:
        filtro = st.text_input(
            "Filtrar", key="rv_filtro_acciones", placeholder="Buscar...",
            label_visibility="collapsed"
        )

    if filtro:
        q = filtro.upper()

        def _coincide(d):
            textos = [
                d['ticker'], d['nombre'], d['fecha_adquisicion'] or '',
                f"{d['coste']:.2f}", f"{d['valor']:.2f}",
                f"{d['carne_pct']:.1f}", f"{d['leche_pct']:.1f}",
            ]
            return any(q in t.upper() for t in textos)

        datos = [d for d in datos if _coincide(d)]

    # Cabecera de tabla tipo hoja de calculo: cada columna es un boton, pulsar
    # ordena por esa columna (con una flecha indicando la columna/direccion
    # activa) y volver a pulsar la misma alterna ascendente/descendente.
    COLUMNAS_TABLA = [
        ('Ticker', 'ticker', 1.3, 'text'),
        ('Fecha', 'fecha_adquisicion', 0.9, 'text'),
        ('Coste', 'coste_eur', 1.0, 'num'),
        ('Valor', 'valor_eur', 1.0, 'num'),
        ('Carne', 'carne_pct', 0.8, 'num'),
        ('Leche', 'leche_pct', 0.8, 'num'),
    ]

    if 'rv_orden_campo' not in st.session_state:
        st.session_state.rv_orden_campo = 'valor_eur'
    if 'rv_orden_asc' not in st.session_state:
        st.session_state.rv_orden_asc = False

    with st.container(key="rv_tabla_header"):
        columnas = st.columns([w for _, _, w, _ in COLUMNAS_TABLA])
        for col, (etiqueta, campo_col, _, tipo) in zip(columnas, COLUMNAS_TABLA):
            with col:
                es_activa = st.session_state.rv_orden_campo == campo_col
                if es_activa:
                    flecha = ' ▲' if st.session_state.rv_orden_asc else ' ▼'
                else:
                    flecha = ''
                if st.button(f"{etiqueta}{flecha}", key=f"rv_orden_col_{campo_col}",
                             use_container_width=True):
                    if es_activa:
                        st.session_state.rv_orden_asc = not st.session_state.rv_orden_asc
                    else:
                        st.session_state.rv_orden_campo = campo_col
                        st.session_state.rv_orden_asc = (tipo == 'text')
                    st.rerun()

    campo = st.session_state.rv_orden_campo

    def _clave_orden(d):
        valor = d[campo]
        if valor is None:
            return '' if campo in ('ticker', 'fecha_adquisicion') else float('-inf')
        return valor

    datos.sort(key=_clave_orden, reverse=not st.session_state.rv_orden_asc)

    # Simbolo de divisa para mostrar coste/valor en divisa original (como el Excel).
    SIMBOLO = {'EUR': '&#8364;', 'USD': '$', 'GBP': '&#163;', 'GBX': '&#163;',
               'CHF': 'CHF', 'DKK': 'kr', 'NOK': 'kr', 'SEK': 'kr', 'PLN': 'z&#322;'}
    # Pesos identicos a los de la cabecera (COLUMNAS_TABLA) para que columnas y
    # encabezados queden alineados; todo centrado para mejor lectura.
    filas = ""
    for d in datos:
        color_carne = '#0ECB81' if d['carne_pct'] >= 0 else '#F6465D'
        fa = d['fecha_adquisicion']
        fecha = f"{fa[5:7]}/{fa[0:4]}" if fa else 'N/D'  # MM/YYYY
        sym = SIMBOLO.get(d['divisa'], d['divisa'] or '')
        filas += (
            "<div style='display:flex;padding:5px 0;border-bottom:1px solid #1E2329;'>"
            f"<span style='flex:1.3;text-align:center;color:#EAECEF;font-size:12px;"
            f"font-weight:600;'>{d['ticker']}</span>"
            f"<span style='flex:0.9;text-align:center;color:#848E9C;font-size:11px;'>{fecha}</span>"
            f"<span style='flex:1;text-align:center;color:#848E9C;font-size:11px;'>"
            f"{formato_eur(d['coste'])} {sym}</span>"
            f"<span style='flex:1;text-align:center;color:#EAECEF;font-size:11px;'>"
            f"{formato_eur(d['valor'])} {sym}</span>"
            f"<span style='flex:0.8;text-align:center;color:{color_carne};font-size:11px;"
            f"font-weight:600;'>{d['carne_pct']:+.1f}%</span>"
            f"<span style='flex:0.8;text-align:center;color:#F0B90B;font-size:11px;'>"
            f"{d['leche_pct']:.1f}%</span></div>"
        )
    st.markdown(filas, unsafe_allow_html=True)


RANGOS_ACTIVO = {'1M': 2, '3M': 3, '6M': 6, '1A': 12, 'MAX': None}


def _vista_activo_individual(vehiculo):
    activo_id = st.session_state.rv_activo_sel
    datos = consultas.rv_lista_vehiculo(vehiculo)
    d = next((x for x in datos if x['id'] == activo_id), None)
    nombre_activo = d['nombre'].split(' - ')[-1] if d else 'Activo'

    st.markdown(
        f"<p style='color:#EAECEF;font-size:14px;font-weight:700;margin:0 0 4px;'>"
        f"{nombre_activo}</p>",
        unsafe_allow_html=True
    )

    historico = consultas.historico_valoraciones_activo(activo_id, dias=730)
    if not historico:
        st.markdown(
            "<p style='color:#5C6470;font-size:13px;margin:8px 0;'>"
            "Todavia no hay historico de valoraciones guardado para este activo. "
            "Se ira completando con cada actualizacion periodica.</p>",
            unsafe_allow_html=True
        )
        return

    n_puntos = len(historico)
    valor_actual = historico[-1][1]

    margen_valor = '4px 0 10px' if vehiculo == 'FONDOS' else '4px 0 0'
    st.markdown(
        f"<p style='color:#EAECEF;font-size:28px;font-weight:600;margin:{margen_valor};line-height:1.0;'>"
        f"{formato_eur(valor_actual)} &#8364;</p>",
        unsafe_allow_html=True
    )

    key_rango = f"rv_rango_activo_{activo_id}"
    if key_rango not in st.session_state:
        st.session_state[key_rango] = 'MAX'
    opciones_activas = [e for e, m in RANGOS_ACTIVO.items() if m is None or n_puntos >= m]
    if st.session_state[key_rango] not in opciones_activas:
        st.session_state[key_rango] = opciones_activas[-1]

    rango_sel = st.radio(
        "Rango", options=opciones_activas,
        index=opciones_activas.index(st.session_state[key_rango]),
        horizontal=True, key=f"radio_{key_rango}",
    )
    st.session_state[key_rango] = rango_sel

    meses_sel = RANGOS_ACTIVO[rango_sel]
    historico_filtrado = (
        historico if meses_sel is None or n_puntos <= meses_sel else historico[-meses_sel:]
    )
    fechas = [h[0] for h in historico_filtrado]
    valores = [h[1] for h in historico_filtrado]

    # Para Fondos/Carteras no se muestra aqui: ahi la rentabilidad de
    # referencia es la "real neta" (IPC + fiscalidad tipo) de las tarjetas de
    # _seccion_rentabilidad_real_neta. Para ETFs se muestra en este mismo
    # sitio (sin tarjetas ni grafico aparte), pero con esa misma formula real
    # neta en vez de la variacion simple de precio sobre el rango del grafico
    # (que ya no depende de 1M/3M/6M/MAX: es la rentabilidad acumulada desde
    # la aportacion inicial).
    if vehiculo == 'FONDOS':
        pass
    elif vehiculo == 'ETF':
        historico_rent = consultas.historico_rentabilidad_mensual(activo_id)
        if historico_rent:
            _, rent_pct, _ = historico_rent[-1]
        else:
            rent_pct = None
        if rent_pct is not None:
            signo = '+' if rent_pct >= 0 else ''
            color_var = '#0ECB81' if rent_pct >= 0 else '#F6465D'
            flecha = '&#8599;' if rent_pct >= 0 else '&#8600;'
            st.markdown(
                f"<p style='color:{color_var};font-size:13px;margin:2px 0 10px;'>"
                f"{flecha} {signo}{rent_pct:.1f}% rentabilidad real neta</p>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                "<p style='color:#5C6470;font-size:11px;margin:2px 0 10px;'>"
                "Todavia no hay suficiente historico para calcular la rentabilidad.</p>",
                unsafe_allow_html=True
            )
    elif len(historico_filtrado) >= 2:
        valor_inicio_rango = historico_filtrado[0][1]
        variacion = ((valor_actual - valor_inicio_rango) / valor_inicio_rango * 100) if valor_inicio_rango else 0
        signo = '+' if variacion >= 0 else ''
        color_var = '#0ECB81' if variacion >= 0 else '#F6465D'
        flecha = '&#8599;' if variacion >= 0 else '&#8600;'
        st.markdown(
            f"<p style='color:{color_var};font-size:13px;margin:2px 0 10px;'>"
            f"{flecha} {signo}{variacion:.1f}% en {rango_sel}</p>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            "<p style='color:#5C6470;font-size:11px;margin:2px 0 10px;'>"
            "Solo hay 1 valoracion guardada todavia.</p>",
            unsafe_allow_html=True
        )

    y_min, y_max = rango_y_grafico(valores)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=fechas, y=valores, fill='tozeroy', fillcolor='rgba(240,185,11,0.12)',
        line=dict(color='#F0B90B', width=2, shape='spline', smoothing=0.8), mode='lines',
        hovertemplate='%{x}: %{y:,.0f} &#8364;<extra></extra>',
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=8, b=0), height=180,
        xaxis=dict(showgrid=False, color='#848E9C', tickfont=dict(size=10), fixedrange=True),
        yaxis=dict(showgrid=True, gridcolor='#1E2329', color='#848E9C',
                   tickformat=',.0f', ticksuffix=' &#8364;', range=[y_min, y_max], fixedrange=True),
        hoverlabel=dict(bgcolor='#1E2329', font_color='#EAECEF'),
        showlegend=False,
    )
    st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})

    if vehiculo == 'FONDOS':
        _seccion_rentabilidad_real_neta(activo_id)


def _rv_lista_vehiculo_vista(vehiculo):
    if st.session_state.rv_activo_sel is not None:
        _vista_activo_individual(vehiculo)
        return

    datos = consultas.rv_lista_vehiculo(vehiculo)
    if not datos:
        st.markdown(
            "<p style='color:#5C6470;font-size:13px;margin:4px 0;'>"
            "Todavia no hay activos registrados en este vehiculo.</p>",
            unsafe_allow_html=True
        )
        return

    SIMBOLO = {'EUR': '&#8364;', 'USD': '$', 'GBP': '&#163;', 'GBX': '&#163;',
               'CHF': 'CHF', 'DKK': 'kr', 'NOK': 'kr', 'SEK': 'kr', 'PLN': 'z&#322;'}
    ETIQ_EXP = {'Regiones': 'Regiones', 'Tematicas': 'Tem&aacute;ticas'}

    # Peso de cada uno sobre el total de la lista (en EUR, para poder comparar
    # instrumentos en distintas divisas).
    total_lista = sum((d['valor_eur'] or 0.0) for d in datos)

    # Agrupar por exposicion (Regiones / Tematicas). Lo que no la tiene (fondos,
    # carteras) va sin cabecera de grupo.
    grupos = {}
    for d in datos:
        grupos.setdefault(d.get('exposicion') or '', []).append(d)
    orden_grupos = [g for g in ('Regiones', 'Tematicas') if g in grupos]
    orden_grupos += [g for g in grupos if g not in ('Regiones', 'Tematicas')]

    for grupo in orden_grupos:
        if grupo:
            # % del grupo (Regiones / Tematicas) sobre el total de la lista
            val_grupo = sum((d['valor_eur'] or 0.0) for d in grupos[grupo])
            pct_grupo = (val_grupo / total_lista * 100) if total_lista else 0.0
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;align-items:baseline;"
                f"margin:10px 0 2px;'>"
                f"<span style='color:#F0B90B;font-size:11px;font-weight:700;"
                f"text-transform:uppercase;letter-spacing:0.6px;'>"
                f"{ETIQ_EXP.get(grupo, grupo)}</span>"
                f"<span style='color:#F0B90B;font-size:11px;font-weight:700;'>"
                f"{pct_grupo:.1f}%</span></div>",
                unsafe_allow_html=True
            )
        for d in grupos[grupo]:
            sym = SIMBOLO.get(d['divisa'], d['divisa'] or '')
            rent = d['carne_pct']
            if rent is None:
                color_carne, rent_txt = '#848E9C', '&mdash;'
            else:
                color_carne = '#0ECB81' if rent >= 0 else '#F6465D'
                rent_txt = f"{rent:+.1f}%"
            if d.get('exposicion_detalle'):
                sub = d['exposicion_detalle']
            else:
                composicion_cap = d['composicion'].capitalize() if d['composicion'] else None
                sub = ' &middot; '.join(x for x in [composicion_cap, d['geografia']] if x)
            html = (
                f"<div style='background:transparent;border-radius:6px;padding:8px 10px;margin-bottom:4px;'>"
                f"<div style='display:flex;justify-content:space-between;'>"
                f"<span style='color:#EAECEF;font-size:13px;font-weight:600;'>"
                f"{d['nombre'].split(' - ')[-1]}</span>"
                f"<span style='color:#EAECEF;font-size:13px;font-weight:700;'>"
                f"{formato_eur(d['valor'])} {sym}</span></div>"
                f"<div style='display:flex;justify-content:space-between;margin-top:1px;'>"
                f"<span style='color:#848E9C;font-size:11px;'>{sub}</span>"
                f"<span style='color:{color_carne};font-size:11px;font-weight:600;'>"
                f"{rent_txt}</span></div></div>"
            )
            if fila_clicable(html, key=f"rv_item_{vehiculo}_{d['id']}"):
                st.session_state.rv_activo_sel = d['id']
                st.rerun()


def panel_renta_variable():
    for clave, valor_inicial in (
            ('rv_vista', None), ('rv_estrategia_sel', None), ('rv_activo_sel', None)):
        if clave not in st.session_state:
            st.session_state[clave] = valor_inicial

    vista = st.session_state.rv_vista

    if vista is None:
        _rv_tiles()
    elif vista == 'ACCION':
        if st.session_state.rv_estrategia_sel:
            _rv_acciones_detalle_vista()
        else:
            _rv_acciones_carteras()
    elif vista in ('ETF', 'FONDOS'):
        _rv_lista_vehiculo_vista(vista)


def mostrar():
    distribucion, total = consultas.distribucion_por_pilar()

    if 'pilar_sel' not in st.session_state:
        st.session_state.pilar_sel = None
    pilar_sel = st.session_state.pilar_sel

    por_clave = {d[0]: d for d in distribucion}

    # distribucion ya viene ordenada de mayor a menor valor (y por tanto %);
    # los pilares sin ningun valor (0%) se anaden al final en el orden fijo,
    # para que siempre se vean los 8 aunque esten vacios.
    pilares_ordenados = list(distribucion)
    for p in ORDEN:
        if p not in por_clave:
            pilares_ordenados.append((p, 0, 0))

    etiquetas = [ETIQUETAS.get(d[0], d[0]) for d in pilares_ordenados]
    valores   = [d[1] for d in pilares_ordenados]
    porcs     = [d[2] for d in pilares_ordenados]
    colores   = [COLORES.get(d[0], '#848E9C') for d in pilares_ordenados]
    pilares   = [d[0] for d in pilares_ordenados]

    fila_donut = st.container(key="fila_donut_barras")
    col_donut, col_barras = fila_donut.columns([5, 6])

    with col_donut:
        fig = go.Figure(go.Pie(
            labels=etiquetas,
            values=[v if v > 0 else 0.001 for v in valores],
            hole=0.65,
            marker=dict(colors=colores, line=dict(color='#0B0E11', width=2)),
            textinfo='none',
            hovertemplate='%{label}: %{value:,.0f} &#8364;<extra></extra>',
            sort=False,
            pull=[0.06 if p == pilar_sel else 0 for p in pilares],
        ))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=0, b=0),
            height=240,
            showlegend=False,
            annotations=[dict(
                text=f"<b>{formato_eur(total)} &#8364;</b>",
                x=0.5, y=0.5,
                font=dict(size=22, color='#EAECEF'),
                showarrow=False,
            )],
        )
        st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})

    with col_barras:
        st.markdown(
            "<p style='color:#848E9C;font-size:11px;margin:0 0 8px;text-align:right;'>"
            "Pulsa una barra para ver el detalle</p>",
            unsafe_allow_html=True
        )
        for pilar, etiq, valor, porc, color in zip(
                pilares, etiquetas, valores, porcs, colores):
            activo = pilar_sel == pilar
            bg = '#1E2329' if activo else 'transparent'
            txt_color = '#F0B90B' if activo else '#EAECEF'
            fw = '700' if activo else '400'
            ancho = max(porc, 0.5)
            fila_html = (
                f"<div style='background:{bg};border-radius:5px;padding:3px 6px;"
                f"display:flex;align-items:center;gap:5px;margin-bottom:2px;'>"
                f"<span style='color:{color};font-size:8px;flex-shrink:0;width:8px;'>&#9679;</span>"
                f"<span style='color:#EAECEF;font-size:12px;font-weight:600;"
                f"min-width:62px;flex-shrink:0;'>{etiq}</span>"
                f"<div style='flex:1;background:#2B3139;border-radius:3px;height:5px;'>"
                f"<div style='width:{ancho}%;background:{color};border-radius:3px;height:5px;'>"
                f"</div></div>"
                f"<span style='color:{txt_color};font-size:12px;min-width:30px;"
                f"text-align:right;font-weight:{fw};margin-left:4px;'>{porc:.0f}%</span>"
                f"</div>"
            )
            if fila_clicable(fila_html, key=f"pilar_{pilar}"):
                nuevo_pilar = None if activo else pilar
                st.session_state.pilar_sel = nuevo_pilar
                if nuevo_pilar == 'RENTA_VARIABLE':
                    st.session_state.rv_vista = None
                    st.session_state.rv_estrategia_sel = None
                    st.session_state.rv_activo_sel = None
                elif nuevo_pilar == 'INVERSIONES_ALTERNATIVAS':
                    st.session_state.inv_alt_activo_sel = None
                st.rerun()

    st.markdown(
        "<div style='border-top:1px solid #2B3139;margin:6px 0 5px;'></div>",
        unsafe_allow_html=True
    )

    if pilar_sel:
        color_sel = COLORES.get(pilar_sel, '#F0B90B')
        detalle = consultas.detalle_pilar(pilar_sel)
        nombre_completo = NOMBRES_COMPLETOS.get(pilar_sel, pilar_sel)

        if pilar_sel == 'RENTA_VARIABLE':
            sufijo_rv = {'ACCION': 'Acciones', 'ETF': 'ETFs',
                         'FONDOS': 'Fondos y Carteras'}.get(st.session_state.get('rv_vista'))
            if sufijo_rv:
                titulo_panel = f"Renta Variable - {sufijo_rv}"
            else:
                titulo_panel = f"{nombre_completo} &mdash; Por vehiculo"
        elif pilar_sel == 'CRIPTOACTIVOS' and st.session_state.get('cripto_vista') == 'rentabilidad':
            titulo_panel = "Criptoactivos - Rentabilidad"
        else:
            titulo_panel = f"{nombre_completo} &mdash; Detalle"
        icono_panel = ICONOS_PILAR.get(pilar_sel, 'category')

        if pilar_sel == 'RENTA_VARIABLE':
            vista_rv = st.session_state.get('rv_vista')
            estrategia_sel = st.session_state.get('rv_estrategia_sel')
            activo_sel = st.session_state.get('rv_activo_sel')

            clave_volver = None
            if vista_rv == 'ACCION' and estrategia_sel:
                clave_volver = 'rv_estrategia_sel'
            elif vista_rv in ('ETF', 'FONDOS') and activo_sel:
                clave_volver = 'rv_activo_sel'
            elif vista_rv is not None:
                clave_volver = 'rv_vista'

            if clave_volver:
                with st.container(key="rv_boton_volver"):
                    if st.button("", icon=":material/arrow_back:", key="rv_volver_arriba"):
                        st.session_state[clave_volver] = None
                        st.rerun()

        if pilar_sel == 'INVERSIONES_ALTERNATIVAS' and st.session_state.get('inv_alt_activo_sel'):
            with st.container(key="plataforma_boton_volver"):
                if st.button("", icon=":material/arrow_back:", key="inv_alt_volver_arriba"):
                    st.session_state.inv_alt_activo_sel = None
                    st.rerun()

        if pilar_sel == 'CRIPTOACTIVOS' and st.session_state.get('cripto_vista') == 'rentabilidad':
            with st.container(key="cripto_boton_volver"):
                if st.button("", icon=":material/arrow_back:", key="cripto_volver_arriba"):
                    st.session_state.cripto_vista = 'arbol'
                    st.rerun()

        with st.container(key="panel_detalle"):
            st.markdown(
                f"<div style='display:flex;align-items:center;justify-content:space-between;"
                f"margin-bottom:8px;'>"
                f"<span style='display:flex;align-items:center;gap:6px;'>"
                f"<span style='font-family:&quot;Material Symbols Rounded&quot;;font-size:16px;"
                f"color:{TITULO_AMARILLO};'>{icono_panel}</span>"
                f"<span style='color:{TITULO_AMARILLO};font-size:14px;font-weight:700;'>"
                f"{titulo_panel}</span></span>"
                f"<span style='display:inline-block;width:22px;height:5px;border-radius:3px;"
                f"background:{color_sel};'></span>"
                f"</div>",
                unsafe_allow_html=True
            )

            if pilar_sel == 'LIQUIDEZ':
                panel_liquidez(detalle)
            elif pilar_sel == 'MATERIAS_PRIMAS':
                panel_materias_primas(detalle)
            elif pilar_sel == 'CRIPTOACTIVOS':
                panel_criptoactivos(detalle)
            elif pilar_sel == 'RENTA_FIJA':
                panel_renta_fija(detalle)
            elif pilar_sel == 'INVERSIONES_ALTERNATIVAS':
                panel_inv_alternativas(detalle)
            elif pilar_sel == 'INMOBILIARIO':
                panel_inmobiliario(detalle)
            elif pilar_sel == 'NEGOCIOS':
                panel_negocios(detalle)
            elif pilar_sel == 'RENTA_VARIABLE':
                panel_renta_variable()

    else:
        st.markdown(
            "<p style='color:#2B3139;font-size:13px;text-align:center;margin:16px 0;'>"
            "Selecciona un pilar para ver el detalle</p>",
            unsafe_allow_html=True
        )