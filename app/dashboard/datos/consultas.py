"""
CONSULTAS
==========
Funciones que leen de cartera.db y devuelven los datos ya calculados
que necesita cada pagina del dashboard.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'cartera.db')


def conectar():
    return sqlite3.connect(DB_PATH)


def _a_eur(c, activo_id, valor, fecha=None):
    """Convierte un importe en la divisa nativa del activo a EUR (para agregar), con el
    tipo del BCE de `fecha` o el ultimo anterior (o el mas reciente, si no hay fecha).
    tipo_cambio de divisas_fx: price_divisa = price_eur * tipo_cambio."""
    divisa = c.execute("SELECT divisa FROM activos WHERE id=?", (activo_id,)).fetchone()[0]
    if not divisa or divisa == 'EUR':
        return valor
    if fecha is None:
        fila = c.execute(
            "SELECT tipo_cambio FROM divisas_fx WHERE par=? ORDER BY fecha DESC LIMIT 1",
            (f'{divisa}/EUR',)).fetchone()
    else:
        fila = c.execute(
            "SELECT tipo_cambio FROM divisas_fx WHERE par=? AND fecha<=? ORDER BY fecha DESC LIMIT 1",
            (f'{divisa}/EUR', fecha)).fetchone()
    return valor / fila[0] if fila and fila[0] else valor


# ============================================================================
# EL VALOR DE UN ACTIVO: UNA SOLA REGLA (10-10-2026)
# ============================================================================
# Hasta el 10-10-2026 "precio x cantidad" estaba escrito CUATRO veces en este fichero
# y solo una estaba bien. La de las graficas por plataforma y la rentabilidad real
# neta (valor_activo_en_fecha) con 0 unidades devolvia el precio de UNA unidad como
# si fuera el total (el BTC transferido de eToro sumaba 56.025 EUR en su grafica),
# no convertia la divisa (el efectivo USD de eToro contaba como euros) y usaba las
# unidades de HOY en fechas pasadas (lo vendido desaparecia tambien hacia atras).
#
# Ahora todo pasa por valor_activo(). valor_actual_activo() y valor_activo_en_fecha()
# son solo sus dos nombres de siempre, para no tocar a quien los llama.

# Fuentes de 'valoraciones' cuyo campo 'precio' NO es un precio unitario sino el
# VALOR TOTAL ya calculado de la posicion. Hay que respetarlas aunque el activo
# tenga lotes FIFO: multiplicarlas por la cantidad da cifras absurdas.
#
# 'MANUAL_TOTAL' lo pone scripts/reparar_valoraciones_totales.py sobre las 58
# filas de la carga inicial del 19-20 de junio de 2026, que guardaron el total
# en esa columna. Sin este respeto, Taylor Wimpey valia 19,7 millones de euros
# en junio de 2026 y Bestinfond rendia un +14.683 %.
FUENTES_VALOR_TOTAL = ('MANUAL_TOTAL', 'SNAPSHOT')

# Que movimientos meten o sacan unidades. Son EXACTAMENTE los que usa
# scripts/motor_fifo.py para construir lotes_fifo, que es quien manda sobre cuantas
# unidades hay hoy. Si alli cambian, aqui tambien.
ENTRADAS_UNIDADES = ('COMPRA', 'TRASPASO_ENTRADA', 'STAKING')
SALIDAS_UNIDADES = ('VENTA', 'TRASPASO_SALIDA')


def _splits(c, activo_id):
    """[(fecha, ratio)] de los SPLIT del activo, leidos igual que motor_fifo.get_splits."""
    res = []
    for fecha, notas in c.execute(
            "SELECT fecha_operacion, notas FROM movimientos WHERE activo_id=? AND tipo_operacion='SPLIT' "
            "ORDER BY fecha_operacion", (activo_id,)).fetchall():
        ratio = 1.0
        if notas and 'ratio:' in notas:
            try:
                ratio = float(notas.split('ratio:')[1].split()[0].split(',')[0])
            except (ValueError, IndexError):
                ratio = 1.0
        res.append((fecha, ratio))
    return res


def unidades_en_fecha(c, activo_id, fecha=None):
    """(tiene_lotes, unidades) del activo hoy o al cierre de `fecha`.

    Hoy es lo que dice lotes_fifo. En una fecha pasada se parte de hoy y se deshace
    lo que se movio DESPUES: se restan las entradas y se suman las salidas, con las
    reglas de motor_fifo (una entrada cuenta con los splits posteriores, igual que su
    lote). Si hubo un split despues de `fecha`, se devuelven las unidades de entonces.
    Un activo sin lotes (efectivo, pensiones, carteras, inmuebles) devuelve
    (False, None): su valoracion ya es el total.
    """
    n, uds = c.execute("SELECT COUNT(*), SUM(cantidad_disponible) FROM lotes_fifo WHERE activo_id=?",
                       (activo_id,)).fetchone()
    if not n:
        return False, None
    uds = uds or 0.0
    if fecha is None:
        return True, uds
    splits = _splits(c, activo_id)

    def ratio_despues(f):
        r = 1.0
        for fs, ratio in splits:
            if fs > f:
                r *= ratio
        return r

    tipos = ENTRADAS_UNIDADES + SALIDAS_UNIDADES
    for f, tipo, cant in c.execute(
            "SELECT fecha_operacion, tipo_operacion, num_participaciones FROM movimientos "
            "WHERE activo_id=? AND fecha_operacion>? AND num_participaciones > 0 "
            f"AND tipo_operacion IN ({','.join('?' * len(tipos))})",
            (activo_id, fecha, *tipos)).fetchall():
        if tipo in ENTRADAS_UNIDADES:
            uds -= cant * ratio_despues(f)
        else:
            uds += cant
    uds = uds / ratio_despues(fecha)
    return True, max(uds, 0.0)


def valor_activo(c, activo_id, fecha=None):
    """Valor en EUR de un activo hoy (fecha=None) o al cierre de `fecha`. LA regla:

      - precio: la ultima valoracion en o antes de la fecha;
      - con lotes: precio x unidades de ESE dia (0 unidades -> 0, nunca el precio a
        secas), salvo que la valoracion sea ya un total (FUENTES_VALOR_TOTAL);
      - sin lotes (efectivo, pensiones, carteras robo, pools): la valoracion ES el
        total, en la divisa del activo, y se pasa a euros con el tipo de ESE dia;
      - inmuebles en copropiedad: x porcentaje_propiedad.

    Devuelve None si no hay ninguna valoracion en o antes de la fecha.
    """
    if fecha is None:
        fila = c.execute("SELECT precio, fuente FROM valoraciones WHERE activo_id=? "
                         "ORDER BY fecha DESC LIMIT 1", (activo_id,)).fetchone()
    else:
        fila = c.execute("SELECT precio, fuente FROM valoraciones WHERE activo_id=? AND fecha<=? "
                         "ORDER BY fecha DESC LIMIT 1", (activo_id, fecha)).fetchone()
    if not fila:
        return None
    precio, fuente = fila

    tiene_lotes, uds = unidades_en_fecha(c, activo_id, fecha)
    if not tiene_lotes:
        valor = _a_eur(c, activo_id, precio, fecha)
    elif fuente in FUENTES_VALOR_TOTAL:
        valor = precio
    else:
        valor = precio * uds

    porcentaje = c.execute(
        "SELECT porcentaje_propiedad FROM activos WHERE id=?", (activo_id,)
    ).fetchone()[0]
    if porcentaje:
        valor = valor * (porcentaje / 100)
    return valor


def valor_actual_activo(c, activo_id):
    """El valor de hoy: valor_activo() sin fecha. Se conserva el nombre porque lo usan
    exportar_plan.py, exportar_fiscal.py, objetivo.py y media pagina del dashboard."""
    return valor_activo(c, activo_id)


def valor_activo_en_fecha(c, activo_id, fecha):
    """El valor al cierre de `fecha`: valor_activo() con fecha. Se conserva el nombre
    por quien lo llama (grafica por plataforma, rentabilidad real neta, inmuebles)."""
    return valor_activo(c, activo_id, fecha)


def patrimonio_total():
    """Devuelve (valor_total_eur, desglose_por_plataforma: list of (broker, valor_eur))."""
    conn = conectar()
    c = conn.cursor()

    activos = c.execute("SELECT id, broker FROM activos WHERE activo=1").fetchall()

    por_plataforma = {}
    total = 0.0

    for activo_id, broker in activos:
        valor = valor_actual_activo(c, activo_id)
        if valor is None:
            continue
        total += valor
        por_plataforma[broker] = por_plataforma.get(broker, 0.0) + valor

    conn.close()

    desglose = sorted(por_plataforma.items(), key=lambda x: -x[1])
    return total, desglose


def posiciones_sin_precio_al_dia(dias=7, minimo_eur=1.0):
    """{broker: [aviso, ...]} de las POSICIONES ABIERTAS cuyo valor en la tarjeta no es
    de hoy. El cuadro de mando lo pinta en rojo en la tarjeta de cada plataforma.

    POR QUE (10-10-2026). Un activo sin precio no da ningun error: valor_actual_activo()
    devuelve None y la suma lo cuenta como CERO, en silencio. Paso cinco veces en quince
    dias (Bestinver, los bonos a la par, el fondo indexado, Sanofi...) y todas se
    descubrieron por casualidad. Ahora sale donde se mira, sin script de verificacion.

    Posicion abierta = activo vivo con unidades en lotes_fifo. Se avisa si:
      - no tiene NINGUNA valoracion (cuenta cero), o
      - su ultima valoracion va mas de `dias` dias por detras de la mas reciente de la
        base, es decir, de la ultima pasada de la cadena (si no se actualiza en un mes,
        no se pone todo en rojo), y vale al menos `minimo_eur` (un CVR sin mercado de
        0,35 EUR no merece una alarma para siempre).
    Las cuentas sin lotes (efectivo, pensiones, inmuebles, carteras) no entran: su valor
    se teclea o sale de un extracto, no lo trae un mercado.
    """
    from datetime import date
    conn = conectar()
    c = conn.cursor()
    ref = c.execute("SELECT MAX(fecha) FROM valoraciones").fetchone()[0]
    filas = c.execute('''
        SELECT a.id, a.broker, a.nombre,
               (SELECT SUM(cantidad_disponible) FROM lotes_fifo l WHERE l.activo_id = a.id)
        FROM activos a WHERE a.activo = 1
    ''').fetchall()
    avisos = {}
    for aid, broker, nombre, uds in filas:
        if not uds or uds <= 0.0001:
            continue
        corto = nombre.split(' - ', 1)[-1]
        ult = c.execute("SELECT fecha, precio, fuente FROM valoraciones WHERE activo_id=? "
                        "ORDER BY fecha DESC LIMIT 1", (aid,)).fetchone()
        if not ult:
            avisos.setdefault(broker, []).append(f"Sin precio: {corto}")
            continue
        fecha, precio, fuente = ult
        d, d_ref = date.fromisoformat(fecha), date.fromisoformat(ref)
        if (d_ref - d).days <= dias:
            continue
        if (valor_activo(c, aid) or 0.0) < minimo_eur:
            continue
        cuando = d.strftime('%d-%m') if d.year == d_ref.year else d.strftime('%d-%m-%Y')
        avisos.setdefault(broker, []).append(f"Precio del {cuando}: {corto}")
    conn.close()
    return avisos


def distribucion_por_divisa():
    """Devuelve list of (divisa, valor_eur, porcentaje) segun la divisa nativa
    de cada activo (columna 'divisa' de activos), ordenada de mayor a menor
    valor. El valor en si siempre esta en EUR (ya convertido); 'divisa' solo
    indica la exposicion de moneda del activo subyacente."""
    conn = conectar()
    c = conn.cursor()

    activos = c.execute("SELECT id, divisa FROM activos WHERE activo=1").fetchall()

    por_divisa = {}
    total = 0.0

    for activo_id, divisa in activos:
        valor = valor_actual_activo(c, activo_id)
        if valor is None:
            continue
        total += valor
        divisa = divisa or 'EUR'
        por_divisa[divisa] = por_divisa.get(divisa, 0.0) + valor

    conn.close()

    if total <= 0:
        return []

    desglose = sorted(por_divisa.items(), key=lambda x: -x[1])
    return [(divisa, valor, valor / total * 100) for divisa, valor in desglose]


def liquidez_cuentas():
    """Cuentas de liquidez: (broker, divisa, valor_nativo, valor_eur). El nativo es el
    saldo en su divisa (eToro en USD); el EUR es el convertido para el patrimonio."""
    conn = conectar()
    c = conn.cursor()
    res = []
    for aid, broker, divisa in c.execute(
            "SELECT id, broker, divisa FROM activos WHERE tipo='LIQUIDEZ' AND activo=1").fetchall():
        nat = c.execute(
            "SELECT precio FROM valoraciones WHERE activo_id=? ORDER BY fecha DESC LIMIT 1",
            (aid,)).fetchone()
        if not nat:
            continue
        res.append((broker, divisa or 'EUR', nat[0], valor_actual_activo(c, aid) or 0.0))
    conn.close()
    return sorted(res, key=lambda x: -x[3])


def efectivo_por_plataforma():
    """Devuelve dict {broker: (valor, divisa)} solo para activos tipo LIQUIDEZ."""
    conn = conectar()
    c = conn.cursor()

    activos = c.execute("SELECT id, broker, divisa FROM activos WHERE tipo='LIQUIDEZ' AND activo=1").fetchall()

    resultado = {}
    for activo_id, broker, divisa in activos:
        ultimo = c.execute('''
            SELECT precio FROM valoraciones WHERE activo_id=? ORDER BY fecha DESC LIMIT 1
        ''', (activo_id,)).fetchone()
        if ultimo:
            resultado[broker] = (ultimo[0], divisa)

    conn.close()
    return resultado


def _candidatas_mensuales(fechas):
    """A partir de una lista de fechas (YYYY-MM-DD), devuelve para cada mes la
    fecha mas cercana al dia 28 (dentro de la ventana 25-31), ordenadas."""
    candidatas_por_mes = {}
    for fecha in fechas:
        anio_mes = fecha[:7]
        dia = int(fecha[8:10])
        if 25 <= dia <= 31:
            distancia = abs(dia - 28)
            if anio_mes not in candidatas_por_mes or distancia < candidatas_por_mes[anio_mes][1]:
                candidatas_por_mes[anio_mes] = (fecha, distancia)
    return sorted(candidatas_por_mes.items())


def historico_mensual_por_broker(broker, meses=12):
    """Devuelve lista de (fecha, valor_total_eur) para un broker/plataforma
    concreto, usando el snapshot mas cercano al dia 28 (+/- 3 dias) de cada
    uno de los ultimos `meses` meses. Para los meses en los que hay un valor
    manual guardado en 'historico_broker_manual' (backfill de meses sin
    historico de precios por activo) se usa ese valor tal cual; el resto se
    calcula sumando valor_activo_en_fecha() de cada activo del broker."""
    conn = conectar()
    c = conn.cursor()

    activos = c.execute(
        "SELECT id FROM activos WHERE broker=? AND activo=1", (broker,)
    ).fetchall()
    activo_ids = [a[0] for a in activos]

    manuales = dict(c.execute(
        "SELECT fecha, valor_total FROM historico_broker_manual WHERE broker=?", (broker,)
    ).fetchall())

    fechas = set(manuales.keys())
    if activo_ids:
        marcadores = ','.join('?' * len(activo_ids))
        fechas.update(f[0] for f in c.execute(
            f"SELECT DISTINCT fecha FROM valoraciones WHERE activo_id IN ({marcadores})",
            activo_ids
        ).fetchall())

    if not fechas:
        conn.close()
        return []

    resultado = []
    for anio_mes, (fecha, _) in _candidatas_mensuales(sorted(fechas))[-meses:]:
        if fecha in manuales:
            resultado.append((fecha, manuales[fecha]))
            continue
        total = 0.0
        for activo_id in activo_ids:
            valor = valor_activo_en_fecha(c, activo_id, fecha)
            if valor is not None:
                total += valor
        resultado.append((fecha, total))

    conn.close()
    return resultado


def _ipc_en_fecha(c, fecha):
    """IPC de España (indices_macro) mas reciente en o antes de 'fecha'. Si no
    hay ninguno anterior (fecha muy antigua respecto al dato disponible), usa
    el primero que haya. Devuelve None si la tabla esta vacia."""
    fila = c.execute(
        "SELECT ipc_spain FROM indices_macro WHERE fecha<=? AND ipc_spain IS NOT NULL "
        "ORDER BY fecha DESC LIMIT 1", (fecha,)
    ).fetchone()
    if fila:
        return fila[0]
    fila = c.execute(
        "SELECT ipc_spain FROM indices_macro WHERE ipc_spain IS NOT NULL ORDER BY fecha ASC LIMIT 1"
    ).fetchone()
    return fila[0] if fila else None


def _tasa_fiscal_tipo(c, fecha):
    """Tasa fiscal 'tipo' (tasa_promedio_estimada de config_fiscal) del año de
    'fecha' o, si no esta configurado ese año, la del año conocido mas
    reciente anterior a ese. Devuelve el % (ej. 21.0), no la fraccion."""
    anio = int(fecha[:4])
    fila = c.execute(
        "SELECT tasa_promedio_estimada FROM config_fiscal WHERE anio<=? ORDER BY anio DESC LIMIT 1",
        (anio,)
    ).fetchone()
    if fila:
        return fila[0]
    fila = c.execute(
        "SELECT tasa_promedio_estimada FROM config_fiscal ORDER BY anio DESC LIMIT 1"
    ).fetchone()
    return fila[0] if fila else 21.0


def calcular_rentabilidad_real_neta(c, activo_id, fecha_corte, fecha_inicio_periodo=None,
                                     tipos_flujo=('APORTACION', 'REEMBOLSO')):
    """
    Rentabilidad 'real neta' de un activo (inversion alternativa tipo Mintos,
    o un fondo/cartera de Renta Variable), pensada para responder "¿ha
    merecido la pena esta inversion?" y no para declarar impuestos. Cada
    entrada/salida de capital se actualiza a euros de 'fecha_corte' segun el
    IPC de su propia fecha (tabla indices_macro); la ganancia real resultante
    (valor en fecha_corte - capital neto actualizado) tributa a la fiscalidad
    "tipo" (tasa_promedio_estimada de config_fiscal) solo si es positiva (una
    perdida no genera beneficio fiscal aqui).

    tipos_flujo: (tipo_entrada, tipo_salida) de movimientos.tipo_operacion que
    representan dinero puesto/sacado de este activo. Por defecto
    ('APORTACION','REEMBOLSO') para crowdlending (Mintos); para fondos/carteras
    de RV se usa ('COMPRA','VENTA'), que es como MyInvestor Roboadvisors y las
    compras/reembolsos de fondos Bestinver quedan registrados.

    Si se pasa fecha_inicio_periodo, es un calculo de sub-periodo (p.ej. los
    ultimos 12 meses): el valor de la cartera en esa fecha se trata como una
    aportacion inicial equivalente (tambien actualizada por IPC), y solo se
    consideran los flujos de capital posteriores a esa fecha - asi el
    resultado no se contamina con aportaciones recientes sin apenas margen
    para rendir (dilucion), a diferencia de restar dos rentabilidades
    acumuladas de distintos momentos.

    Devuelve None si no hay capital de referencia (aun no hay flujos o valor).
    """
    ipc_corte = _ipc_en_fecha(c, fecha_corte)
    tasa = _tasa_fiscal_tipo(c, fecha_corte) / 100.0
    tipo_entrada, tipo_salida = tipos_flujo

    flujos = []  # [(fecha, importe_con_signo), ...]
    fecha_desde = None
    if fecha_inicio_periodo:
        valor_inicio = valor_activo_en_fecha(c, activo_id, fecha_inicio_periodo)
        if not valor_inicio:
            # No hay suficiente historico para este sub-periodo todavia (p.ej.
            # la inversion tiene menos de 12 meses de vida) - no se aproxima
            # con un capital inicial de 0, se devuelve None sin mas.
            return None
        flujos.append((fecha_inicio_periodo, valor_inicio))
        fecha_desde = fecha_inicio_periodo

    query = (
        "SELECT fecha_operacion, tipo_operacion, importe_eur FROM movimientos "
        "WHERE activo_id=? AND tipo_operacion IN (?,?) AND fecha_operacion<=?"
    )
    params = [activo_id, tipo_entrada, tipo_salida, fecha_corte]
    if fecha_desde:
        query += " AND fecha_operacion>?"
        params.append(fecha_desde)

    for fecha, tipo, importe in c.execute(query, params).fetchall():
        signo = 1 if tipo == tipo_entrada else -1
        flujos.append((fecha, signo * importe))

    if not flujos:
        return None

    capital_ajustado = 0.0
    for fecha, importe in flujos:
        ipc_fecha = _ipc_en_fecha(c, fecha)
        factor = (ipc_corte / ipc_fecha) if (ipc_corte and ipc_fecha) else 1.0
        capital_ajustado += importe * factor

    if capital_ajustado <= 0:
        return None

    valor = valor_activo_en_fecha(c, activo_id, fecha_corte)
    if valor is None:
        return None

    # ── La foto puede ser anterior a los movimientos de SU MISMO DIA ──
    # Ni las valoraciones ni los movimientos llevan hora, asi que si el mismo
    # dia hay una valoracion y una entrada de dinero no se puede saber por los
    # datos cual fue primero. Pero se puede DETECTAR cuando la foto es la de
    # antes: si el valor se parece al capital SIN ese flujo (menos de un 10 %
    # de diferencia) y en cambio queda muy por debajo del capital CON el flujo,
    # entonces el dinero todavia no estaba dentro cuando se tomo la foto.
    #
    # Sin esto, Mintos Core Loans marcaba -19,49 % el 2026-04-28: ese dia
    # entraron 10.000 EUR y salieron 5.000, la foto (20.128,64) era de antes, y
    # se comparaba contra un capital de 25.000 que aun no habia llegado. Al mes
    # siguiente volvia a +0,79 %. No era una perdida: era una foto a destiempo.
    flujo_mismo_dia = sum(imp for f, imp in flujos if f == fecha_corte)
    aviso = None
    if flujo_mismo_dia > 0 and valor < capital_ajustado:
        capital_sin = capital_ajustado - flujo_mismo_dia
        if capital_sin > 0 and abs(valor - capital_sin) / capital_sin < 0.10:
            aviso = (f"la foto del {fecha_corte} es anterior a los "
                     f"{flujo_mismo_dia:,.2f} EUR que entraron ese mismo dia; "
                     f"se calcula sobre el capital previo")
            capital_ajustado = capital_sin

    ganancia_real = valor - capital_ajustado
    ganancia_neta = ganancia_real * (1 - tasa) if ganancia_real > 0 else ganancia_real
    rentabilidad_pct = ganancia_neta / capital_ajustado * 100

    return {
        'valor': valor,
        'capital_ajustado': capital_ajustado,
        'ganancia_neta': ganancia_neta,
        'rentabilidad_pct': rentabilidad_pct,
        'aviso': aviso,
    }


def historico_rentabilidad_mensual(activo_id, meses=24):
    """Devuelve [(fecha, rentabilidad_acumulada_pct, rentabilidad_12m_pct), ...]
    de los ultimos `meses` meses, usando el snapshot mas cercano al dia 28
    (+/- 3 dias) guardado en historico_rentabilidad_activo para cada mes."""
    conn = conectar()
    c = conn.cursor()

    filas = c.execute(
        "SELECT fecha, rentabilidad_acumulada_pct, rentabilidad_12m_pct "
        "FROM historico_rentabilidad_activo WHERE activo_id=? ORDER BY fecha",
        (activo_id,)
    ).fetchall()
    conn.close()

    if not filas:
        return []

    por_fecha = {f: (acum, doce) for f, acum, doce in filas}
    candidatas = _candidatas_mensuales([f for f, _, _ in filas])[-meses:]
    return [(fecha, por_fecha[fecha][0], por_fecha[fecha][1]) for _, (fecha, _) in candidatas]


def historico_patrimonio():
    """
    Evolucion MENSUAL del patrimonio desde la tabla historico_patrimonio.
    La tabla puede tener varios snapshots por mes; para cada mes se representa
    el del dia 28, y si no lo hay, el mas cercano a 28 dentro de la ventana
    [25, 31] (28 -3 / +3 dias). En caso de empate en distancia (p.ej. 25 y 31),
    gana el mas cercano a fin de mes (el posterior). Los snapshots fuera de esa
    ventana se ignoran. Retorna lista de (fecha, valor_total) por mes, ordenada.
    """
    conn = conectar()
    c = conn.cursor()
    filas = c.execute(
        "SELECT fecha, valor_total FROM historico_patrimonio ORDER BY fecha ASC"
    ).fetchall()
    conn.close()

    # mes 'YYYY-MM' -> (fecha, valor, distancia_al_28)
    mejor_por_mes = {}
    for fecha, valor in filas:
        dia = int(fecha[8:10])
        if not (25 <= dia <= 31):
            continue
        mes = fecha[:7]
        distancia = abs(dia - 28)
        if mes not in mejor_por_mes or distancia <= mejor_por_mes[mes][2]:
            mejor_por_mes[mes] = (fecha, valor, distancia)

    return [(f, v) for f, v, _ in
            (mejor_por_mes[m] for m in sorted(mejor_por_mes))]


# Que cuenta como inmueble: el pilar INMOBILIARIO, y como respaldo el tipo INMUEBLE cuando
# el pilar falta en la base. Es EL MISMO criterio que la funcion bloque() de
# scripts/exportar_plan.py, y ese script comprueba en cada ejecucion que las dos cuentas
# coinciden al centimo, para que no puedan separarse en silencio.
SQL_INMUEBLES = ("SELECT id FROM activos WHERE activo=1 AND "
                 "(pilar='INMOBILIARIO' OR (COALESCE(pilar,'')='' AND tipo='INMUEBLE'))")


def valor_inmuebles(c, fecha=None):
    """Valor de los inmuebles —la parte que es suya— a una fecha, o el de hoy si no se da.

    POR QUE EXISTE. El plan de independencia financiera trabaja con un perimetro distinto
    del cuadro de mando: patrimonio del plan = patrimonio total MENOS los inmuebles. No
    dan renta, no se piensan vender y no financian el puente, asi que la senda no los
    cuenta. Pero la FOTO mensual del patrimonio salia del total del cuadro de mando, con
    los inmuebles dentro, y al restarle el objetivo daba una desviacion de 37.000 EUR que
    no era una desviacion: eran los tres inmuebles de Salamanca al 1/14 que le toca.
    Lo cazo Jose el 29-09-2026 mirando la fila de septiembre.

    No duplica ninguna regla de valoracion: llama a valor_activo_en_fecha(), que ya aplica
    el porcentaje_propiedad de la copropiedad.

    Devuelve (valor, n_sin_valoracion). Si algun inmueble no tiene valoracion en o antes de
    esa fecha se cuenta aparte y NO se da por cero: quien llame decide, pero con el dato a
    la vista. Un cero inventado restaria de menos y nadie lo notaria.
    """
    total, sin_dato = 0.0, 0
    for (activo_id,) in c.execute(SQL_INMUEBLES).fetchall():
        v = (valor_activo_en_fecha(c, activo_id, fecha) if fecha
             else valor_actual_activo(c, activo_id))
        if v is None:
            sin_dato += 1
        else:
            total += v
    return total, sin_dato


# DE QUE ESTA HECHO EL PLAN DE PENSIONES, que no es lo que dice su etiqueta.
# El P.P. Repsol Materials tiene pilar='RENTA_VARIABLE' en la base de datos, asi que contado
# a pelo mete sus 63.486 EUR enteros en bolsa. Dentro lleva un 57 % de renta fija. Contado a
# pelo, el cuadro de mando decia 62,4 % de bolsa cuando lo real es el 57,0 %, y la pestana
# Analisis pedia comprar 22.962 EUR de bolsa donde el plan pide 59.566: 47.000 EUR de
# diferencia por una etiqueta. Lo cazo Jose el 01-10-2026 comparando las dos pantallas.
#
# Esta era la UNICA copia de esta regla que quedaba fuera de aqui: vivia en
# scripts/exportar_plan.py como REPARTO_PLAN. Ahora vive donde viven las demas reglas de
# valoracion y exportar_plan.py la importa.
REPARTO_PENSIONES = {"RENTA_FIJA": 0.57, "RENTA_VARIABLE": 0.26,
                     "INVERSIONES_ALTERNATIVAS": 0.13, "LIQUIDEZ": 0.04}


def distribucion_por_pilar(mirar_dentro=False):
    """Reparto del patrimonio por pilar.

    mirar_dentro=True reparte los planes de pensiones por lo que llevan DENTRO
    (REPARTO_PENSIONES) en vez de por su etiqueta. Lo usa la pestana Analisis, que es la que
    dice donde meter el dinero, y por eso necesita saber de que esta hecha la cartera.

    Por defecto va a False y la pestana Distribucion no cambia: alli el detalle de cada pilar
    lista los activos uno a uno, y un activo partido en cuatro no se puede listar en cuatro
    sitios sin que el detalle deje de sumar el total. Son dos preguntas distintas a proposito:
    Distribucion dice DONDE ESTA ETIQUETADO tu dinero y Analisis DE QUE ESTA HECHO.
    """
    conn = conectar()
    c = conn.cursor()
    activos = c.execute("SELECT id, pilar, tipo FROM activos WHERE activo=1").fetchall()
    por_pilar = {}
    for activo_id, pilar, tipo in activos:
        clave = pilar if pilar else ('LIQUIDEZ' if tipo == 'LIQUIDEZ' else None)
        if not clave:
            continue
        if mirar_dentro and tipo == 'PENSIONES':
            v = valor_actual_activo(c, activo_id)
            if v is not None:
                for k, w in REPARTO_PENSIONES.items():
                    por_pilar[k] = por_pilar.get(k, 0.0) + v * w
            continue
        valor = valor_actual_activo(c, activo_id)
        if valor is None:
            continue
        por_pilar[clave] = por_pilar.get(clave, 0.0) + valor
    total = sum(por_pilar.values())
    resultado = [
        (pilar, valor, round(valor / total * 100, 1) if total > 0 else 0)
        for pilar, valor in sorted(por_pilar.items(), key=lambda x: -x[1])
    ]
    conn.close()
    return resultado, total


def detalle_pilar(pilar):
    conn = conectar()
    c = conn.cursor()
    if pilar == 'LIQUIDEZ':
        activos = c.execute("""
            SELECT a.id, a.nombre, a.broker, a.divisa, a.composicion, a.sector,
                   a.geografia, a.vehiculo, a.ticker, a.municipio, a.destino_inmueble,
                   a.porcentaje_propiedad
            FROM activos a
            WHERE a.activo=1 AND a.tipo='LIQUIDEZ'
        """).fetchall()
    else:
        activos = c.execute("""
            SELECT a.id, a.nombre, a.broker, a.divisa, a.composicion, a.sector,
                   a.geografia, a.vehiculo, a.ticker, a.municipio, a.destino_inmueble,
                   a.porcentaje_propiedad
            FROM activos a
            WHERE a.activo=1 AND a.pilar=?
        """, (pilar,)).fetchall()
    resultado = []
    for row in activos:
        activo_id = row[0]
        valor = valor_actual_activo(c, activo_id)
        cantidad = c.execute(
            "SELECT SUM(cantidad_disponible) FROM lotes_fifo WHERE activo_id=?",
            (activo_id,)
        ).fetchone()[0] or 0
        resultado.append((*row[1:], activo_id, valor or 0, cantidad))
    conn.close()
    return sorted(resultado, key=lambda x: -x[-2])


def materias_primas_por_camara(activo_id):
    """Desglose de un activo de materia prima (Oro/Plata) por camara de
    custodia (Zurich, Londres, ...), usando el precio mas reciente del
    activo y la cantidad de cada camara segun sus lotes FIFO abiertos."""
    conn = conectar()
    c = conn.cursor()
    precio_row = c.execute(
        "SELECT precio FROM valoraciones WHERE activo_id=? ORDER BY fecha DESC LIMIT 1",
        (activo_id,)
    ).fetchone()
    precio = precio_row[0] if precio_row else None

    filas = c.execute('''
        SELECT COALESCE(m.camara, 'Sin especificar'), SUM(l.cantidad_disponible)
        FROM lotes_fifo l
        JOIN movimientos m ON m.id = l.movimiento_id
        WHERE l.activo_id = ?
        GROUP BY COALESCE(m.camara, 'Sin especificar')
        HAVING SUM(l.cantidad_disponible) > 0.0001
    ''', (activo_id,)).fetchall()
    conn.close()

    resultado = [
        (camara, cantidad, precio * cantidad if precio is not None else None)
        for camara, cantidad in filas
    ]
    return sorted(resultado, key=lambda x: -x[1])


def distribucion_rv_por_vehiculo():
    conn = conectar()
    c = conn.cursor()
    activos = c.execute("""
        SELECT a.id, a.tipo, a.vehiculo FROM activos a
        WHERE a.activo=1 AND a.pilar='RENTA_VARIABLE'
    """).fetchall()
    por_vehiculo = {}
    for activo_id, tipo, vehiculo in activos:
        clave = 'FONDOS' if vehiculo in ('FONDO', 'CARTERA') else tipo
        valor = valor_actual_activo(c, activo_id)
        if valor is None:
            continue
        por_vehiculo[clave] = por_vehiculo.get(clave, 0.0) + valor
    # El % de cada vehiculo es respecto al TOTAL del pilar Renta Variable (en EUR),
    # no respecto a todo el patrimonio.
    total = sum(por_vehiculo.values())
    resultado = {
        k: (v, round(v / total * 100, 1) if total > 0 else 0)
        for k, v in por_vehiculo.items()
    }
    conn.close()
    return resultado, total


def _coste_activo(c, activo_id):
    """Coste de adquisicion (EUR) de las posiciones abiertas de un activo,
    segun el motor FIFO."""
    coste = c.execute('''
        SELECT SUM(cantidad_disponible * precio_coste_eur)
        FROM lotes_fifo WHERE activo_id=?
    ''', (activo_id,)).fetchone()[0]
    return coste or 0.0


def _fecha_adquisicion(c, activo_id):
    fecha = c.execute('''
        SELECT MIN(fecha_compra) FROM lotes_fifo
        WHERE activo_id=? AND cantidad_disponible > 0.0001
    ''', (activo_id,)).fetchone()[0]
    return fecha


def _dividendos_netos(c, activo_id):
    total = c.execute('''
        SELECT SUM(importe_neto_eur) FROM movimientos
        WHERE activo_id=? AND tipo_operacion='DIVIDENDO'
    ''', (activo_id,)).fetchone()[0]
    return total or 0.0


def rv_acciones_por_estrategia():
    """Devuelve {estrategia: (valor_total_eur, carne_pct, [(sector, valor, pct), ...])}.
    LEE la tabla metricas_acciones (misma fuente que el Excel CarneLeche): CARNE es
    la rentabilidad real neta (IPC+IRPF) sobre el coste actualizado por IPC."""
    conn = conectar()
    c = conn.cursor()
    por = {}
    for estr, sector, valor_eur, coste_ipc_eur, rent_neta_eur in c.execute(
            "SELECT estrategia, sector, valor_eur, coste_ipc_eur, rent_neta_eur FROM metricas_acciones"):
        clave = estr or 'SIN_ESTRATEGIA'
        d = por.setdefault(clave, {'valor': 0.0, 'coste_ipc': 0.0, 'rent': 0.0, 'sectores': {}})
        d['valor'] += valor_eur or 0.0
        d['coste_ipc'] += coste_ipc_eur or 0.0
        d['rent'] += rent_neta_eur or 0.0
        sec = sector or 'Otros'
        d['sectores'][sec] = d['sectores'].get(sec, 0.0) + (valor_eur or 0.0)

    resultado = {}
    for clave, d in por.items():
        carne_pct = round(d['rent'] / d['coste_ipc'] * 100, 1) if d['coste_ipc'] > 0 else 0.0
        sectores = sorted(
            [(sec, val, round(val / d['valor'] * 100, 1) if d['valor'] > 0 else 0)
             for sec, val in d['sectores'].items()],
            key=lambda x: -x[1]
        )
        resultado[clave] = (d['valor'], carne_pct, sectores)
    conn.close()
    return resultado


def rv_acciones_detalle(estrategia):
    """Lista de acciones de una estrategia con coste, valor, Carne% y Leche%.
    LEE la tabla metricas_acciones (misma fuente que el Excel CarneLeche)."""
    conn = conectar()
    c = conn.cursor()
    cond = "estrategia IS NULL" if estrategia == 'SIN_ESTRATEGIA' else "estrategia = ?"
    params = () if estrategia == 'SIN_ESTRATEGIA' else (estrategia,)
    resultado = []
    for (tk, nombre, divisa, fecha_adq, coste_orig, valor_venta,
         coste_eur, valor_eur, carne, leche) in c.execute(
            f"SELECT ticker, nombre, divisa, fecha_adq, coste_orig, valor_venta, "
            f"coste_eur, valor_eur, carne, leche FROM metricas_acciones WHERE {cond}", params):
        resultado.append({
            'ticker': tk,
            'nombre': nombre,
            'divisa': divisa,
            'fecha_adquisicion': fecha_adq,
            'coste': coste_orig or 0.0,        # valor de adquisicion en divisa original (como el Excel)
            'valor': valor_venta or 0.0,       # valor de venta en divisa original (como CarneLeche)
            'coste_eur': coste_eur or 0.0,     # para el total y el orden
            'valor_eur': valor_eur or 0.0,
            'carne_pct': round((carne or 0.0) * 100, 1),
            'leche_pct': round((leche or 0.0) * 100, 1),
        })
    conn.close()
    return sorted(resultado, key=lambda x: -x['valor_eur'])


def inv_alt_metricas():
    """{activo_id: {'tipo', 'valor_eur', 'pct'}} desde la tabla metricas_inv_alt
    (calculada en la cadena por calcular_metricas.py). El % es el peso de cada
    activo sobre el total del pilar Inversiones Alternativas."""
    conn = conectar()
    c = conn.cursor()
    res = {r[0]: {'tipo': r[1], 'valor_eur': r[2], 'pct': r[3]}
           for r in c.execute("SELECT id, tipo, valor_eur, pct FROM metricas_inv_alt")}
    conn.close()
    return res


def rv_lista_vehiculo(vehiculo):
    """Lista de ETFs o Fondos/Carteras con valor actual (en divisa original) y
    rentabilidad. LEE la tabla metricas_etf (calculada en la cadena por
    calcular_metricas.py). vehiculo: 'ETF' o 'FONDOS' (agrupa FONDO+CARTERA)."""
    conn = conectar()
    c = conn.cursor()
    cond = "vehiculo IN ('FONDO','CARTERA')" if vehiculo == 'FONDOS' else "vehiculo = ?"
    params = () if vehiculo == 'FONDOS' else (vehiculo,)
    resultado = []
    for (aid, nombre, divisa, composicion, geografia, exposicion, exposicion_detalle,
         fecha_adq, valor_orig, valor_eur, rentab_pct) in c.execute(
            f"SELECT id, nombre, divisa, composicion, geografia, exposicion, "
            f"exposicion_detalle, fecha_adq, valor_orig, valor_eur, rentab_pct "
            f"FROM metricas_etf WHERE {cond}", params):
        resultado.append({
            'id': aid,
            'nombre': nombre,
            'divisa': divisa,
            'composicion': composicion,
            'geografia': geografia,
            'exposicion': exposicion,
            'exposicion_detalle': exposicion_detalle,
            'fecha_adquisicion': fecha_adq,
            'valor': valor_orig or 0.0,      # valor actual en divisa original
            'valor_eur': valor_eur or 0.0,
            'carne_pct': rentab_pct,         # None si no hay base (rentab. no calculable)
        })
    conn.close()
    return sorted(resultado, key=lambda x: -(x['valor_eur'] or 0.0))


def historico_valoraciones_activo(activo_id, dias=365):
    """Devuelve [(fecha, valor_eur), ...] de los ultimos `dias` para un activo: el valor
    de la posicion en cada fecha con valoracion guardada, con las unidades que habia
    ESE dia y el tipo de cambio de ESE dia (valor_activo).

    Hasta el 10-10-2026 usaba las unidades de hoy en todas las fechas ("no se lleva
    un historico de cantidad"): una venta parcial encogia el pasado entero. Ahora las
    unidades de cada dia salen de lotes_fifo deshaciendo lo movido despues."""
    conn = conectar()
    c = conn.cursor()
    fechas = [f for (f,) in c.execute("""
        SELECT DISTINCT fecha FROM valoraciones
        WHERE activo_id=? AND fecha >= date('now', ?)
        ORDER BY fecha ASC
    """, (activo_id, f'-{dias} days')).fetchall()]
    serie = []
    for fecha in fechas:
        valor = valor_activo(c, activo_id, fecha)
        if valor is not None:
            serie.append((fecha, valor))
    conn.close()
    return serie


ORDEN_ESTRATEGIA = {'HOLD': 0, 'STAKING': 1, 'YIELD_FARMING': 2, 'PERPS': 3}
NOMBRE_ESTRATEGIA = {'HOLD': 'Hold', 'STAKING': 'Staking',
                     'YIELD_FARMING': 'Yield Farming', 'PERPS': 'Perps'}


def arbol_cripto():
    """Arbol del pilar criptoactivos: Moneda -> Estrategia -> posiciones.
    Cada nivel lleva su valor en EUR y su % respecto al PADRE (la moneda sobre el
    total cripto; la estrategia sobre su moneda; la posicion sobre su estrategia).
    Las posiciones snapshot (pools/perps) incluyen rentabilidad en su divisa:
    (liquidity + earnings - valor_inicial) / valor_inicial."""
    conn = conectar()
    c = conn.cursor()
    filas = c.execute("""
        SELECT a.id, a.nombre, a.broker, p.moneda, p.estrategia, p.caracteristicas,
               p.lectura, p.divisa_inicial, p.valor_inicial, p.liq_actual, p.earn_actual,
               p.fecha_inicio, p.carne_actual, p.leche_actual, COALESCE(p.autocompone, 0)
        FROM cripto_posiciones p JOIN activos a ON a.id=p.activo_id
        WHERE a.activo=1
    """).fetchall()

    from datetime import date
    fx = c.execute("SELECT tipo_cambio FROM divisas_fx WHERE par='USD/EUR' "
                   "ORDER BY fecha DESC LIMIT 1").fetchone()
    tipo_usd = fx[0] if fx else 1.16          # price_usd = price_eur * tipo_usd

    posiciones = []
    for (aid, nombre, broker, moneda, estr, carac, lectura, divisa_ini,
         v_ini, liq, earn, f_ini, carne_a, leche_a, autoc) in filas:
        valor = valor_actual_activo(c, aid) or 0.0

        # --- carne (capital) / leche (earnings), en EUR ---
        if carne_a is not None:                       # on-chain (pools/lido/metamask)
            carne, leche = carne_a, (leche_a or 0.0)
        elif (liq is not None) and not autoc:         # snapshot manual: reparto proporcional
            tot = (liq or 0) + (earn or 0)
            carne = valor * ((liq or 0) / tot) if tot else valor
            leche = valor - carne
        else:                                         # hold / autocompuesto: todo capital
            carne, leche = valor, 0.0
        leche_pct = (leche / carne * 100) if carne else None

        # --- base (valor inicial) en EUR: valor_inicial (convertido) o coste FIFO ---
        if v_ini:
            base_eur = v_ini / (tipo_usd if (divisa_ini or 'EUR') == 'USD' else 1.0)
        else:
            coste = c.execute(
                "SELECT SUM(cantidad_disponible * precio_coste_eur) FROM lotes_fifo WHERE activo_id=?",
                (aid,)).fetchone()[0]
            base_eur = coste if (coste and coste > 0.01) else None

        dias = None
        if f_ini:
            try:
                dias = max((date.today() - date.fromisoformat(f_ini)).days, 1)
            except Exception:
                dias = None

        # carne: rentabilidad real neta desde inicio (capital, valor actualizado)
        carne_rent = ((carne - base_eur) / base_eur * 100) if (base_eur and base_eur > 0) else None
        # leche: rendimiento ANUALIZADO sobre el valor inicial
        leche_anual = None
        if leche and leche > 0.005 and base_eur and base_eur > 0 and dias:
            leche_anual = (leche / base_eur) * (365.0 / dias) * 100
        # rent global (compat): total sobre inicial
        rent = (((carne + leche) - base_eur) / base_eur * 100) if (base_eur and base_eur > 0) else None

        posiciones.append({
            'nombre': nombre, 'plataforma': broker, 'moneda': moneda,
            'estrategia': estr, 'caracteristicas': carac or '', 'valor': valor,
            'carne': carne, 'leche': leche, 'leche_pct': leche_pct,
            'carne_rent': carne_rent, 'leche_anual': leche_anual, 'dias': dias,
            'rent': rent, 'divisa': divisa_ini or 'EUR', 'lectura': lectura,
        })
    conn.close()

    total = sum(p['valor'] for p in posiciones) or 1.0
    monedas = []
    for moneda in sorted({p['moneda'] for p in posiciones}, key=lambda m: -sum(
            p['valor'] for p in posiciones if p['moneda'] == m)):
        pm = [p for p in posiciones if p['moneda'] == moneda]
        vm = sum(p['valor'] for p in pm) or 1.0
        estrategias = []
        for estr in sorted({p['estrategia'] for p in pm},
                           key=lambda e: ORDEN_ESTRATEGIA.get(e, 9)):
            pe = [p for p in pm if p['estrategia'] == estr]
            ve = sum(p['valor'] for p in pe) or 1.0
            carne_e = sum(p['carne'] for p in pe)
            leche_e = sum(p['leche'] for p in pe)
            estrategias.append({
                'estrategia': estr, 'nombre': NOMBRE_ESTRATEGIA.get(estr, estr),
                'valor': ve, 'pct': ve / vm * 100, 'carne': carne_e, 'leche': leche_e,
                'leche_pct': (leche_e / carne_e * 100) if carne_e else None,
                'posiciones': [dict(p, pct=p['valor'] / ve * 100)
                               for p in sorted(pe, key=lambda x: -x['valor'])],
            })
        monedas.append({'moneda': moneda, 'valor': vm, 'pct': vm / total * 100,
                        'carne': sum(p['carne'] for p in pm),
                        'leche': sum(p['leche'] for p in pm),
                        'estrategias': estrategias})
    return {'total': total, 'monedas': monedas}