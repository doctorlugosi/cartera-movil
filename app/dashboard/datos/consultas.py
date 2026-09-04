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


def _a_eur(c, activo_id, valor):
    """Convierte un importe en la divisa nativa del activo a EUR (para agregar).
    tipo_cambio de divisas_fx: price_divisa = price_eur * tipo_cambio."""
    divisa = c.execute("SELECT divisa FROM activos WHERE id=?", (activo_id,)).fetchone()[0]
    if not divisa or divisa == 'EUR':
        return valor
    fila = c.execute(
        "SELECT tipo_cambio FROM divisas_fx WHERE par=? ORDER BY fecha DESC LIMIT 1",
        (f'{divisa}/EUR',)).fetchone()
    return valor / fila[0] if fila and fila[0] else valor


def valor_actual_activo(c, activo_id):
    """Devuelve el valor actual en EUR de un activo: ultimo precio conocido x cantidad,
    o el precio directamente si el activo no tiene cantidad real (ej. MyInvestor Robo,
    cuentas de liquidez/pensiones tratadas como 'precio = valor total').
    Si el activo tiene porcentaje_propiedad (inmuebles en copropiedad), el valor
    se pondera por ese porcentaje sobre la tasacion total."""
    ultimo_precio = c.execute('''
        SELECT precio FROM valoraciones WHERE activo_id=? ORDER BY fecha DESC LIMIT 1
    ''', (activo_id,)).fetchone()
    if not ultimo_precio:
        return None
    precio = ultimo_precio[0]

    cantidad = c.execute('''
        SELECT SUM(cantidad_disponible) FROM lotes_fifo WHERE activo_id=?
    ''', (activo_id,)).fetchone()[0]

    if cantidad is None:
        # Sin lotes en absoluto (liquidez, pensiones, MyInvestor Robo) -> el precio YA es
        # el valor total, en la DIVISA NATIVA del activo (p.ej. la liquidez de eToro se
        # mete en USD). Se convierte a EUR para agregar (el resto de valoraciones ya
        # estan en EUR). Para EUR el factor es 1.
        valor = _a_eur(c, activo_id, precio)
    else:
        # Tiene lotes reales (aunque la cantidad actual sea 0, ej. posicion
        # vendida por completo) -> el valor es precio x cantidad, nunca el
        # precio a secas (evita mostrar el ultimo precio por accion como si
        # fuera el valor total de una posicion ya cerrada a 0 unidades)
        valor = precio * cantidad

    porcentaje = c.execute(
        "SELECT porcentaje_propiedad FROM activos WHERE id=?", (activo_id,)
    ).fetchone()[0]
    if porcentaje:
        valor = valor * (porcentaje / 100)

    return valor


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


def valor_activo_en_fecha(c, activo_id, fecha):
    """Como valor_actual_activo, pero usando el ultimo precio conocido en o
    antes de 'fecha' en vez del mas reciente sin mas."""
    precio_row = c.execute('''
        SELECT precio FROM valoraciones WHERE activo_id=? AND fecha<=? ORDER BY fecha DESC LIMIT 1
    ''', (activo_id, fecha)).fetchone()
    if not precio_row:
        return None
    precio = precio_row[0]

    cantidad = c.execute(
        'SELECT SUM(cantidad_disponible) FROM lotes_fifo WHERE activo_id=?', (activo_id,)
    ).fetchone()[0]
    valor = precio * cantidad if cantidad and cantidad > 0.0001 else precio

    porcentaje = c.execute(
        "SELECT porcentaje_propiedad FROM activos WHERE id=?", (activo_id,)
    ).fetchone()[0]
    if porcentaje:
        valor = valor * (porcentaje / 100)
    return valor


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

    ganancia_real = valor - capital_ajustado
    ganancia_neta = ganancia_real * (1 - tasa) if ganancia_real > 0 else ganancia_real
    rentabilidad_pct = ganancia_neta / capital_ajustado * 100

    return {
        'valor': valor,
        'capital_ajustado': capital_ajustado,
        'ganancia_neta': ganancia_neta,
        'rentabilidad_pct': rentabilidad_pct,
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


def evolucion_patrimonio_mensual():
    """Devuelve lista de (fecha, valor_total_eur) usando el snapshot mas cercano
    al dia 28 (+/- 3 dias) de cada mes, a partir del historial de valoraciones."""
    conn = conectar()
    c = conn.cursor()

    # Todas las fechas distintas en valoraciones, agrupadas por mes
    fechas = c.execute("SELECT DISTINCT fecha FROM valoraciones ORDER BY fecha").fetchall()
    fechas = [f[0] for f in fechas]

    candidatas_por_mes = {}
    for fecha in fechas:
        anio_mes = fecha[:7]  # YYYY-MM
        dia = int(fecha[8:10])
        if 25 <= dia <= 31:
            distancia = abs(dia - 28)
            if anio_mes not in candidatas_por_mes or distancia < candidatas_por_mes[anio_mes][1]:
                candidatas_por_mes[anio_mes] = (fecha, distancia)

    resultado = []
    for anio_mes, (fecha, _) in sorted(candidatas_por_mes.items()):
        # Para cada fecha candidata, sumar el valor de todas las valoraciones <= esa fecha (ultimo precio conocido por activo)
        activos = c.execute("SELECT id FROM activos WHERE activo=1").fetchall()
        total = 0.0
        for (activo_id,) in activos:
            precio = c.execute('''
                SELECT precio FROM valoraciones WHERE activo_id=? AND fecha<=? ORDER BY fecha DESC LIMIT 1
            ''', (activo_id, fecha)).fetchone()
            if not precio:
                continue
            cantidad = c.execute('''
                SELECT SUM(cantidad_disponible) FROM lotes_fifo WHERE activo_id=?
            ''', (activo_id,)).fetchone()[0]
            if cantidad and cantidad > 0.0001:
                total += precio[0] * cantidad
            else:
                total += precio[0]
        resultado.append((fecha, total))

    conn.close()
    return resultado

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

def distribucion_por_pilar():
    conn = conectar()
    c = conn.cursor()
    activos = c.execute("SELECT id, pilar, tipo FROM activos WHERE activo=1").fetchall()
    por_pilar = {}
    for activo_id, pilar, tipo in activos:
        clave = pilar if pilar else ('LIQUIDEZ' if tipo == 'LIQUIDEZ' else None)
        if not clave:
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
    """Devuelve [(fecha, valor_eur), ...] de los ultimos `dias` para un activo,
    usando el historial propio de valoraciones (Yahoo Finance / scrapers).
    valor_eur = precio guardado x cantidad ACTUAL en cartera (misma
    simplificacion que valor_activo_en_fecha: se usa la cantidad de hoy para
    todas las fechas pasadas, ya que no se lleva un historico de cantidad).
    Si el activo no tiene lotes (cantidad None), el precio YA es el valor total."""
    conn = conectar()
    c = conn.cursor()
    cantidad = c.execute(
        "SELECT SUM(cantidad_disponible) FROM lotes_fifo WHERE activo_id=?", (activo_id,)
    ).fetchone()[0]
    factor = cantidad if cantidad is not None else 1.0
    resultado = c.execute("""
        SELECT fecha, precio FROM valoraciones
        WHERE activo_id=? AND fecha >= date('now', ?)
        ORDER BY fecha ASC
    """, (activo_id, f'-{dias} days')).fetchall()
    conn.close()
    return [(fecha, precio * factor) for fecha, precio in resultado]


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