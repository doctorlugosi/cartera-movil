import streamlit as st
import plotly.graph_objects as go
import sys
import os

RUTA_DASHBOARD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RUTA_DASHBOARD not in sys.path:
    sys.path.insert(0, RUTA_DASHBOARD)

from datos import consultas
from utilidades import formato_eur, formato_moneda, rango_y_grafico, variacion_periodo
from componentes import fila_clicable


def mes_snapshot(fecha_iso):
    MESES_ES = {
        1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr',
        5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Ago',
        9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'
    }
    mes, dia = int(fecha_iso[5:7]), int(fecha_iso[8:10])
    if dia <= 3:
        mes = mes - 1 if mes > 1 else 12
    return MESES_ES[mes]


def filtrar_historico(historico, meses):
    if meses is None or len(historico) <= meses:
        return historico
    return historico[-meses:]


MESES_ES_CORTO = {
    1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr',
    5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Ago',
    9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'
}


def _etiqueta_mes(fecha_iso):
    anio, mes = int(fecha_iso[:4]), int(fecha_iso[5:7])
    return f"{MESES_ES_CORTO[mes]} {anio % 100:02d}"


def _vista_historico_plataforma(broker):
    st.markdown(
        f"<p style='color:#EAECEF;font-size:14px;font-weight:700;margin:0 0 4px;'>"
        f"{broker}</p>",
        unsafe_allow_html=True
    )

    historico = consultas.historico_mensual_por_broker(broker)
    if not historico:
        st.markdown(
            "<p style='color:#5C6470;font-size:13px;margin:8px 0;'>"
            "Todavia no hay historico mensual guardado para esta plataforma. "
            "Se ira completando con cada actualizacion periodica.</p>",
            unsafe_allow_html=True
        )
        return

    n_puntos = len(historico)
    valor_actual = historico[-1][1]
    etiquetas = [_etiqueta_mes(h[0]) for h in historico]
    valores = [h[1] for h in historico]

    st.markdown(
        f"<p style='color:#EAECEF;font-size:28px;font-weight:600;margin:4px 0 0;line-height:1.0;'>"
        f"{formato_eur(valor_actual)} &#8364;</p>",
        unsafe_allow_html=True
    )
    variacion = variacion_periodo(valores)
    if variacion is not None:
        signo = '+' if variacion >= 0 else ''
        color_var = '#0ECB81' if variacion >= 0 else '#F6465D'
        flecha = '&#8599;' if variacion >= 0 else '&#8600;'
        st.markdown(
            f"<p style='color:{color_var};font-size:13px;margin:2px 0 10px;'>"
            f"{flecha} {signo}{variacion:.1f}% en el periodo mostrado</p>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            "<p style='color:#5C6470;font-size:11px;margin:2px 0 10px;'>"
            "Solo hay 1 snapshot mensual guardado todavia.</p>",
            unsafe_allow_html=True
        )

    y_min, y_max = rango_y_grafico(valores)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=etiquetas, y=valores, fill='tozeroy', fillcolor='rgba(240,185,11,0.12)',
        line=dict(color='#F0B90B', width=2, shape='spline', smoothing=0.8), mode='lines+markers',
        marker=dict(size=5, color='#F0B90B'),
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


def mostrar():
    total, desglose = consultas.patrimonio_total()
    efectivo = consultas.efectivo_por_plataforma()
    historico = consultas.historico_patrimonio()
    n_puntos = len(historico)

    RANGOS = {'1M': 2, '3M': 3, '6M': 6, '1A': 12, 'MAX': None}

    if 'rango_patrimonio' not in st.session_state:
        st.session_state.rango_patrimonio = '6M'
    if 'plataforma_sel' not in st.session_state:
        st.session_state.plataforma_sel = None


    # ── Cabecera ──────────────────────────────────────────────────────
    st.markdown(
        "<p style='color:#848E9C;font-size:12px;margin:0 0 1px;'>Patrimonio total</p>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"<p style='color:#EAECEF;font-size:34px;font-weight:600;margin:0;line-height:1.0;'>"
        f"{formato_eur(total)} &#8364;</p>",
        unsafe_allow_html=True
    )

    # ── Selector de rango ─────────────────────────────────────────────
    opciones_activas = [e for e, m in RANGOS.items() if m is None or n_puntos >= m]
    if st.session_state.rango_patrimonio not in opciones_activas:
        st.session_state.rango_patrimonio = opciones_activas[-1]

    rango_sel = st.radio(
        "Rango",
        options=opciones_activas,
        index=opciones_activas.index(st.session_state.rango_patrimonio),
        horizontal=True,
        key="radio_rango_patrimonio",
    )
    st.session_state.rango_patrimonio = rango_sel

    # ── Grafico ───────────────────────────────────────────────────────
    meses_sel = RANGOS[rango_sel]
    historico_filtrado = filtrar_historico(historico, meses_sel)

    if historico_filtrado:
        fechas = [h[0] for h in historico_filtrado]
        valores = [h[1] for h in historico_filtrado]
        etiquetas = [mes_snapshot(f) for f in fechas]

        variacion = variacion_periodo(valores)
        if variacion is not None:
            signo = "+" if variacion >= 0 else ""
            color_var = "#0ECB81" if variacion >= 0 else "#F6465D"
            flecha = "&#8599;" if variacion >= 0 else "&#8600;"
            st.markdown(
                f"<p style='color:{color_var};font-size:13px;margin:2px 0 6px;'>"
                f"{flecha} {signo}{variacion:.1f}% en {rango_sel}</p>",
                unsafe_allow_html=True
            )

        y_min, y_max = rango_y_grafico(valores)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=etiquetas, y=[y_min] * len(etiquetas),
            line=dict(color='rgba(0,0,0,0)', width=0),
            showlegend=False, hoverinfo='skip',
        ))
        fig.add_trace(go.Scatter(
            x=etiquetas, y=valores,
            fill='tonexty',
            fillcolor='rgba(240,185,11,0.12)',
            line=dict(color='#F0B90B', width=2, shape='spline', smoothing=0.8),
            mode='lines',
            hovertemplate='%{x}: %{y:,.0f} &#8364;<extra></extra>',
        ))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=4, b=0),
            height=180,
            xaxis=dict(showgrid=False, color='#848E9C',
                       tickfont=dict(size=11), fixedrange=True),
            yaxis=dict(showgrid=True, gridcolor='#1E2329', color='#848E9C',
                       tickformat=',.0f', ticksuffix=' €',
                       range=[y_min, y_max], fixedrange=True),
            hoverlabel=dict(bgcolor='#1E2329', font_color='#EAECEF'),
            showlegend=False,
        )
        st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})

    # ── Separador + tarjetas de plataforma ────────────────────────────
    st.markdown(
        "<div style='border-top:1px solid #2B3139;margin:16px 0 16px;'></div>",
        unsafe_allow_html=True
    )

    if st.session_state.plataforma_sel:
        with st.container(key="plataforma_boton_volver"):
            if st.button("", icon=":material/arrow_back:", key="plataforma_volver_arriba"):
                st.session_state.plataforma_sel = None
                st.rerun()

        with st.container(key="panel_detalle"):
            _vista_historico_plataforma(st.session_state.plataforma_sel)
        return

    with st.container(key="tarjetas_plataforma"):
        columnas = st.columns(4)
        for i, item in enumerate(desglose):
            broker = item[0]
            valor = item[1]
            with columnas[i % 4]:
                if broker in efectivo:
                    valor_ef = efectivo[broker][0]
                    divisa_ef = efectivo[broker][1]
                    texto_ef = f"Efectivo {formato_moneda(valor_ef, divisa_ef)}"
                else:
                    texto_ef = "Sin efectivo"

                html = (
                    "<div style='background-color:#1E2329;border-radius:7px;"
                    "padding:8px 11px;margin-bottom:5px;'>"
                    f"<p style='font-size:13px;color:#F0B90B;margin:0 0 2px;"
                    f"font-weight:600;line-height:1.1;'>{broker}</p>"
                    f"<p style='font-size:16px;color:#EAECEF;margin:0 0 2px;"
                    f"font-weight:700;line-height:1.1;'>{formato_eur(valor)} &#8364;</p>"
                    f"<p style='font-size:11px;color:#848E9C;margin:0;line-height:1.1;'>{texto_ef}</p>"
                    "</div>"
                )
                clave = broker.replace(' ', '_').replace('/', '_')
                if fila_clicable(html, key=f"plataforma_{clave}"):
                    st.session_state.plataforma_sel = broker
                    st.rerun()

    # ── Separador + Distribucion por divisa ───────────────────────────
    distribucion_divisa = consultas.distribucion_por_divisa()
    if distribucion_divisa:
        st.markdown(
            "<div style='border-top:1px solid #2B3139;margin:16px 0 16px;'></div>"
            "<p style='color:#848E9C;font-size:12px;margin:0 0 5px;'>Por divisa</p>",
            unsafe_allow_html=True
        )
        COLORES_DIVISA = {
            'EUR': '#F0B90B', 'USD': '#0ECB81', 'GBP': '#7B61FF',
            'CHF': '#F6465D', 'GBX': '#02C076',
        }
        for divisa, valor, porcentaje in distribucion_divisa:
            color = COLORES_DIVISA.get(divisa, '#848E9C')
            ancho = max(porcentaje, 0.5)
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:5px;"
                f"padding:3px 6px;margin-bottom:2px;'>"
                f"<span style='color:{color};font-size:8px;flex-shrink:0;width:8px;'>&#9679;</span>"
                f"<span style='color:#EAECEF;font-size:12px;font-weight:600;"
                f"min-width:45px;flex-shrink:0;'>{divisa}</span>"
                f"<div style='flex:1;background:#2B3139;border-radius:3px;height:5px;'>"
                f"<div style='width:{ancho}%;background:{color};border-radius:3px;height:5px;'>"
                f"</div></div>"
                f"<span style='color:#EAECEF;font-size:12px;min-width:30px;"
                f"text-align:right;font-weight:600;margin-left:4px;'>{porcentaje:.0f}%</span>"
                f"</div>",
                unsafe_allow_html=True
            )