import streamlit as st


def formato_eur(valor):
    """
    Formatea un numero como moneda en formato espanol.
    Ejemplo: 288462.0 -> "288.462"
    Si el modo privado esta activo, envuelve el texto en un span
    que estilo.py difumina (para no exponer importes en pantalla).
    """
    texto = f"{valor:,.0f}".replace(",", ".")
    if st.session_state.get("modo_privado", False):
        return f"<span class='valor-privado'>{texto}</span>"
    return texto


def formato_moneda(valor, divisa="EUR"):
    """
    Formatea un numero con su simbolo de divisa correspondiente.
    Ejemplo: formato_moneda(5364, "USD") -> "5.364 $"
    """
    simbolos = {
        "EUR": "€",
        "USD": "$",
        "GBP": "£",
    }
    simbolo = simbolos.get(divisa, divisa)
    return f"{formato_eur(valor)} {simbolo}"


def rango_y_grafico(valores, margen=0.3):
    """
    Rango fijo para el eje Y de un grafico de evolucion, dejando 'margen'
    (30% por defecto) del valor maximo visible por encima y por debajo, para
    que la linea no toque los bordes y se vea mejor la evolucion.
    """
    maximo = max((v for v in valores if v is not None), default=0)
    if maximo <= 0:
        return 0, 1
    return maximo * (1 - margen), maximo * (1 + margen)


def variacion_periodo(valores):
    """
    % de variacion entre el primer y el ultimo valor de la lista (el periodo
    que se este mostrando en cada momento), para que la rentabilidad
    enseñada coincida siempre con el rango de meses seleccionado.
    """
    if len(valores) < 2 or not valores[0]:
        return None
    return (valores[-1] - valores[0]) / valores[0] * 100