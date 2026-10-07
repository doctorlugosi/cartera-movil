"""
DISTRIBUCION OBJETIVO (para la pestana Analisis)
================================================
Lee la distribucion objetivo del usuario (imports/Objetivos/objetivo_distribucion.csv)
y la tabla de sectores por escenario macro (objetivo_sectores.csv), y las CRUZA con la
distribucion real (consultas del dashboard) para el informe comparativo (semaforo +
rebalanceo en euros).

FORMATO del CSV (columnas indentadas, facil de editar en Excel): columnas
  Pilar | Categoria | Subcategoria | Detalle | Peso | Nota
Cada fila rellena SOLO la columna de su nivel (las de arriba se heredan de la fila
anterior); el peso es RELATIVO a su grupo (los hermanos suman 100). Aqui se reconstruye
el arbol y se calcula el peso ABSOLUTO (% del total) multiplicando por la cadena de padres.
Los lectores toleran que Excel guarde el CSV con ';' y/o con BOM.
"""
import os
import csv
import json
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_OBJ = os.path.join(RAIZ, 'imports', 'Objetivos', 'objetivo_distribucion.csv')
CSV_SEC = os.path.join(RAIZ, 'imports', 'Objetivos', 'objetivo_sectores.csv')
CSV_RF = os.path.join(RAIZ, 'imports', 'Objetivos', 'rf_bloques.csv')
# EL NIVEL 1 YA NO SALE DEL CSV: LO MANDA EL PLAN (01-10-2026)
# ------------------------------------------------------------
# El CSV traia un 65/12/6/5/5/4/2/1 fijo. El plan de independencia financiera NO tiene un
# objetivo fijo: tiene una SENDA, porque entre hoy y 2030 hay que construir el colchon del
# que se vive el puente, y la bolsa pasa del 67 % al 52 % mientras la renta fija va del 16 %
# al 33,5 %. Con el objetivo estatico, esta pestana le decia «compra 22.962 EUR de bolsa»
# donde el plan dice 59.566, y le pedia comprar crowdlending (Inversiones Alternativas)
# justo del bloque que la senda baja del 4,6 % al 1,5 %.
#
# Asi que los pesos de NIVEL 1 vienen de exports/objetivo_vigente.json, que escribe el libro
# del plan y NO se teclea. Los SUBNIVELES siguen en el CSV, que es donde tienen sentido: al
# modelo le da igual si la bolsa esta en acciones, fondos o ETFs.
#
# Si el JSON no esta —porque el plan no se ha generado todavia— se usa el CSV y se avisa en
# el diccionario que devuelve cargar_objetivo(), para que la pantalla lo pueda decir en vez
# de ensenar un objetivo viejo como si fuera el bueno.
JSON_OBJ = os.path.join(RAIZ, 'exports', 'objetivo_vigente.json')

ESCENARIOS = [('crecimiento', 'Crecimiento'), ('estable', 'Estable'),
              ('recesion', 'Recesión / estanflación')]

# Renta fija: 'conservador' = solo AAA. Para deuda soberana el pais del emisor va
# en el prefijo del ISIN; esta es la lista de soberanos AAA (consenso S&P/Moody's/
# Fitch, ~2026). Lo que no sea BONO soberano AAA (corporativos, ETFs) -> rentabilidad.
# Es una heuristica editable: cualquier caso se puede forzar en rf_bloques.csv.
AAA_SOBERANOS = {'DE', 'NL', 'LU', 'DK', 'SE', 'NO', 'CH', 'AU', 'SG', 'CA', 'LI'}


def _bloque_rf(isin, tipo, mapa):
    """Bloque de una posicion de renta fija: rf_bloques.csv manda; si no esta,
    se auto-clasifica (AAA soberano -> conservador; resto -> rentabilidad)."""
    b = mapa.get(isin or '')
    if b:
        return b
    if tipo == 'BONO' and (isin or '')[:2].upper() in AAA_SOBERANOS:
        return 'conservador'
    return 'rentabilidad'


def _norm(s):
    """Normaliza un nombre de sector para casar objetivo con real (sin acentos,
    mayusculas, solo alfanumerico)."""
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode()
    return ''.join(ch for ch in s.upper() if ch.isalnum())


def _clave(label):
    """Clave interna estable a partir de una etiqueta legible (sin acentos, en
    mayusculas, con '_'). Ej.: 'Yield farming' -> 'YIELD_FARMING', 'ETFs' -> 'ETFS'."""
    s = unicodedata.normalize('NFKD', str(label or '')).encode('ascii', 'ignore').decode().upper()
    out, hueco = [], False
    for ch in s:
        if ch.isalnum():
            out.append(ch); hueco = False
        elif not hueco:
            out.append('_'); hueco = True
    return ''.join(out).strip('_')


def _filas_csv(path):
    """Lee un CSV tolerando lo que hace Excel al guardar: BOM (utf-8-sig) y el
    separador ';' (habitual en Espanol) ademas de ','."""
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8-sig', newline='') as f:
        cabecera = f.readline()
        f.seek(0)
        delim = ';' if cabecera.count(';') > cabecera.count(',') else ','
        return list(csv.DictReader(f, delimiter=delim))


NIVELES = ['Pilar', 'Categoria', 'Subcategoria', 'Detalle']


def cargar_objetivo():
    """Devuelve {ruta: nodo} con nodo = {ruta, etiqueta, peso_pct (rel. padre),
    peso_abs (% total), nota, padre, hijos:[rutas]}. La 'ruta' se compone de claves
    internas (p.ej. 'CRIPTOACTIVOS > ETH > STAKING') derivadas de las etiquetas."""
    nodos = {}
    actual = [None, None, None, None]   # clave vigente en cada nivel
    for r in _filas_csv(CSV_OBJ):
        nivel, etiqueta = None, None
        for i, col in enumerate(NIVELES):
            v = (r.get(col) or '').strip()
            if v:
                nivel, etiqueta = i, v
        if nivel is None:
            continue
        actual[nivel] = _clave(etiqueta)
        for j in range(nivel + 1, 4):
            actual[j] = None
        partes = [actual[k] for k in range(nivel + 1)]
        ruta = ' > '.join(partes)
        peso = (r.get('Peso') or '').strip().replace(',', '.')
        nodos[ruta] = {
            'ruta': ruta,
            'etiqueta': etiqueta,
            'peso_pct': float(peso) if peso else None,
            'nota': (r.get('Nota') or '').strip(),
            'padre': ' > '.join(partes[:-1]) if nivel > 0 else None,
            'hijos': [],
        }
    for ruta, n in nodos.items():
        if n['padre'] and n['padre'] in nodos:
            nodos[n['padre']]['hijos'].append(ruta)

    cache = {}

    def peso_abs(ruta):
        if ruta in cache:
            return cache[ruta]
        n = nodos[ruta]
        p = n['peso_pct']
        if p is None:
            cache[ruta] = None
        elif not n['padre']:
            cache[ruta] = p
        else:
            pa = peso_abs(n['padre'])
            cache[ruta] = (pa * p / 100.0) if pa is not None else None
        return cache[ruta]

    # ── el nivel 1 lo manda el plan ────────────────────────────────────────────────────
    plan, origen = _objetivo_del_plan(), 'csv'
    if plan:
        origen = f"plan {plan.get('ano_vigente')}"
        for ruta, n in nodos.items():
            if n['padre'] is None and ruta in plan['pilares']:
                n['peso_pct'] = plan['pilares'][ruta]
                n['nota'] = (f"Lo fija la senda del plan para {plan.get('ano_vigente')}. "
                             + (n['nota'] or '')).strip()
        # EL REPARTO DENTRO DE LA RENTA FIJA TAMBIEN LO MANDA LA SENDA. No es una
        # preferencia: el bloque indexado es el colchon del que se vive el puente y tiene
        # que ir del 10,8 % de la renta fija en 2026 al 82,1 % en 2030. Tecleado a mano
        # habia un 36 % que no es el de ningun ano. Lo que SIGUE siendo suyo es como parte
        # el trozo nominal entre conservador y rentabilidad: eso el modelo no lo mira.
        idx, nom = plan.get('rf_indexada'), plan.get('rf_nominal')
        if idx is not None and nom is not None:
            hijos_rf = [r for r in nodos if nodos[r]['padre'] == 'RENTA_FIJA']
            r_idx = next((r for r in hijos_rf if 'INDEXADA' in r), None)
            r_nom = [r for r in hijos_rf if r != r_idx]
            if r_idx and r_nom:
                nodos[r_idx]['peso_pct'] = idx
                nodos[r_idx]['nota'] = (f"Lo fija la senda: el colchón del puente. "
                                        + (nodos[r_idx]['nota'] or '')).strip()
                # el trozo nominal se reparte entre los demas hijos CONSERVANDO su
                # proporcion relativa, que esa si es decision suya
                viejo = sum(nodos[r]['peso_pct'] or 0 for r in r_nom) or 1
                for r in r_nom:
                    nodos[r]['peso_pct'] = nom * (nodos[r]['peso_pct'] or 0) / viejo

        # un pilar del plan que el CSV no tiene (no deberia pasar, pero si pasa no se pierde)
        for clave, peso in plan['pilares'].items():
            if clave not in nodos:
                nodos[clave] = {'ruta': clave, 'etiqueta': clave.replace('_', ' ').title(),
                                'peso_pct': peso, 'nota': 'Pilar del plan que no está en el '
                                'CSV de subniveles.', 'padre': None, 'hijos': []}
        # y uno del CSV que el plan no tiene -> a cero: no esta en el perimetro del plan
        for ruta, n in nodos.items():
            if n['padre'] is None and ruta not in plan['pilares']:
                n['peso_pct'] = 0.0
                n['nota'] = ("Fuera del perímetro del plan: no entra en el objetivo. "
                             + (n['nota'] or '')).strip()

    for ruta, n in nodos.items():
        n['peso_abs'] = peso_abs(ruta)
        n['origen_nivel1'] = origen
    return nodos


def _objetivo_del_plan():
    """Pesos de nivel 1 que escribe el libro del plan, o None si todavia no existen."""
    try:
        with open(JSON_OBJ, encoding='utf-8') as f:
            d = json.load(f)
        ano = d.get('ano_vigente')
        x = d['anos'][ano]
        return {'pilares': x['pilares'], 'ano_vigente': ano, 'generado': d.get('generado'),
                'rf_indexada': x.get('rf_indexada'), 'rf_nominal': x.get('rf_nominal'),
                'destino_ahorro': x.get('destino_ahorro')}
    except (FileNotFoundError, KeyError, ValueError):
        return None


def pilares_objetivo():
    """[(clave, etiqueta, peso_abs_pct)] de nivel 1, en el orden del CSV."""
    nodos = cargar_objetivo()
    return [(r, n['etiqueta'], n['peso_abs']) for r, n in nodos.items()
            if n['padre'] is None]


def hijos_objetivo(ruta):
    """[(clave_ultimo_tramo, etiqueta, peso_pct_rel_padre, nota)] de los hijos de 'ruta'."""
    nodos = cargar_objetivo()
    n = nodos.get(ruta)
    if not n:
        return []
    out = []
    for h in n['hijos']:
        hn = nodos[h]
        out.append((h.split(' > ')[-1], hn['etiqueta'], hn['peso_pct'], hn['nota']))
    return out


CSV_BONOS = os.path.join(RAIZ, 'imports', 'clasificacion', 'bonos.csv')


def cargar_rf_bloques():
    """{isin: 'conservador'|'rentabilidad'|'indexada'} para repartir la renta fija.

    EL BLOQUE «INDEXADA» NO SE TECLEA: sale de la columna `ligado` de
    imports/clasificacion/bonos.csv, que es donde ya vive todo lo demas de cada bono y lo
    que usa el plan. Antes habia que escribirlo tambien en rf_bloques.csv y nadie lo hizo:
    el OAT€i FR001400JI88 estaba marcado ligado=1 en un fichero y no aparecia en el otro,
    asi que el bloque indexada -el 36 % de la renta fija objetivo- salia VACIO para siempre
    y nadie lo notaba. Lo cazo Jose el 01-10-2026 comparando las dos pantallas.
    rf_bloques.csv sigue mandando si alguien quiere forzar un caso concreto.
    """
    res = {}
    try:
        for r in _filas_csv(CSV_BONOS):
            isin = (r.get('isin') or '').strip()
            if isin and (r.get('ligado') or '').strip() in ('1', 'si', 'sí', 'true', 'True'):
                res[isin] = 'indexada'
    except (FileNotFoundError, OSError):
        pass
    for r in _filas_csv(CSV_RF):          # el override manual manda sobre lo anterior
        isin = (r.get('isin') or '').strip()
        bloque = (r.get('bloque') or '').strip().lower()
        if isin and bloque:
            res[isin] = bloque
    return res


def cargar_sectores(escenario='estable'):
    """{sector: peso_pct} para el escenario dado (crecimiento/estable/recesion)."""
    col = escenario if escenario in ('crecimiento', 'estable', 'recesion') else 'estable'
    res = {}
    for r in _filas_csv(CSV_SEC):
        res[(r.get('sector') or '').strip()] = float(str(r.get(col) or 0).replace(',', '.'))
    return res


# ---------------------------------------------------------------------------
# Comparacion objetivo <-> real
# ---------------------------------------------------------------------------
def comparativa_pilares():
    """Nivel 1. Devuelve (filas, total_eur). Cada fila:
    {clave, etiqueta, obj, act_pct, act_eur, desv (pp), ajuste_eur}."""
    from datos import consultas
    # mirar_dentro=True: el plan de pensiones se reparte por lo que lleva DENTRO, no por su
    # etiqueta. Sin esto, esta pantalla cree que hay 63.486 EUR de bolsa que en un 57 % son
    # renta fija, y pide comprar 47.000 EUR menos de bolsa de los que hacen falta.
    distrib, total = consultas.distribucion_por_pilar(mirar_dentro=True)
    actual = {p: (v, pct) for p, v, pct in distrib}

    # EL PERIMETRO TIENE QUE SER EL MISMO EN LAS DOS COLUMNAS. El objetivo del plan esta
    # calculado sobre el patrimonio del PLAN, que es el del cuadro de mando MENOS los
    # inmuebles: no financian la jubilacion, no dan renta y no se piensan vender. Si se
    # comparase contra el total con inmuebles dentro, esta pantalla ensenaria «Inmobiliario:
    # objetivo 0 %, actual 4,2 %, ajuste -37.000 EUR», que se lee como «vende Salamanca», y
    # ademas inflaria el hueco de la bolsa en 30.000 EUR. Asi que cuando el objetivo lo manda
    # el plan, el inmobiliario sale de la comparacion y del denominador, y se dice.
    plan = _objetivo_del_plan()
    fuera = []
    if plan:
        inm_eur = actual.get('INMOBILIARIO', (0.0, 0.0))[0]
        if inm_eur:
            total -= inm_eur
            fuera.append(('INMOBILIARIO', inm_eur))
            actual.pop('INMOBILIARIO', None)

    filas = []
    for clave, etiqueta, obj in pilares_objetivo():
        if any(clave == f[0] for f in fuera):
            continue
        obj = obj or 0.0
        act_eur = actual.get(clave, (0.0, 0.0))[0]
        # el % se recalcula sobre el total COMPARABLE, no sobre el que venia del reparto
        act_pct = 100.0 * act_eur / total if total else 0.0
        filas.append({
            'clave': clave, 'etiqueta': etiqueta, 'obj': obj,
            'act_pct': act_pct, 'act_eur': act_eur,
            'desv': act_pct - obj,
            'ajuste_eur': obj / 100.0 * total - act_eur,
        })
    return filas, total


def _filas_desde(hijos, actual_eur, total_padre_eur):
    """Construye filas de comparacion (obj/act relativos al padre) a partir de:
    - hijos: [(clave, etiqueta, obj_pct_rel_padre, nota)]
    - actual_eur: {clave: valor_eur}
    - total_padre_eur: total del padre (para el %)."""
    tot = total_padre_eur or sum(actual_eur.values())
    filas = []
    usados = set()
    for clave, etiqueta, obj, nota in hijos:
        obj = obj if obj is not None else None
        ae = actual_eur.get(clave, 0.0)
        usados.add(clave)
        act_pct = (ae / tot * 100.0) if tot else 0.0
        fila = {'clave': clave, 'etiqueta': etiqueta, 'obj': obj,
                'act_pct': act_pct, 'act_eur': ae, 'nota': nota}
        if obj is not None:
            fila['desv'] = act_pct - obj
            fila['ajuste_eur'] = obj / 100.0 * tot - ae
        else:
            fila['desv'] = None
            fila['ajuste_eur'] = None
        filas.append(fila)
    # cualquier categoria real que el objetivo no contemple, como "Otros"
    for clave, ae in actual_eur.items():
        if clave not in usados and ae > 0.01:
            act_pct = (ae / tot * 100.0) if tot else 0.0
            filas.append({'clave': clave, 'etiqueta': clave.title(), 'obj': None,
                          'act_pct': act_pct, 'act_eur': ae, 'nota': '',
                          'desv': None, 'ajuste_eur': None})
    return filas, tot


def subcomparativa(clave_pilar, escenario='estable'):
    """Drill-down de un pilar. Devuelve una lista de bloques; cada bloque es
    (titulo, filas) con filas del formato de _filas_desde. Vacio si el pilar no
    tiene desglose mapeable."""
    from datos import consultas
    bloques = []

    if clave_pilar == 'RENTA_VARIABLE':
        rv, total = consultas.distribucion_rv_por_vehiculo()  # {'ACCION':(v,pct),...}
        mapa = {'ACCIONES': 'ACCION', 'ETFS': 'ETF', 'FONDOS_Y_CARTERAS': 'FONDOS'}
        actual = {k: rv.get(v, (0.0, 0.0))[0] for k, v in mapa.items()}
        filas, _ = _filas_desde(hijos_objetivo('RENTA_VARIABLE'), actual, total)
        bloques.append(('Por vehículo', filas))

        # Acciones -> Dividendos / Crecimiento
        por_estr = consultas.rv_acciones_por_estrategia()
        act_estr = {'DIVIDENDOS': (por_estr.get('DIVIDENDOS') or (0.0,))[0],
                    'CRECIMIENTO': (por_estr.get('CRECIMIENTO') or (0.0,))[0]}
        tot_acc = sum(act_estr.values())
        filas_acc, _ = _filas_desde(hijos_objetivo('RENTA_VARIABLE > ACCIONES'),
                                    act_estr, tot_acc)
        bloques.append(('Acciones por estrategia', filas_acc))

        # Dividendos -> sectores (segun escenario)
        div = por_estr.get('DIVIDENDOS')
        if div:
            _valor, _carne, sectores = div
            act_sec = {_norm(sec): val for sec, val, _pct in sectores}
            obj_sec = cargar_sectores(escenario)
            tot_sec = sum(v for _s, v, _p in sectores)
            filas_sec = []
            for sec, obj in obj_sec.items():
                ae = act_sec.get(_norm(sec), 0.0)
                act_pct = (ae / tot_sec * 100.0) if tot_sec else 0.0
                filas_sec.append({'clave': sec, 'etiqueta': sec, 'obj': obj,
                                  'act_pct': act_pct, 'act_eur': ae, 'nota': '',
                                  'desv': act_pct - obj,
                                  'ajuste_eur': obj / 100.0 * tot_sec - ae})
            filas_sec.sort(key=lambda x: -x['act_eur'])
            bloques.append((f'Dividendos por sector · escenario {escenario}', filas_sec))

    elif clave_pilar == 'CRIPTOACTIVOS':
        arbol = consultas.arbol_cripto()
        total = arbol['total']
        act_mon = {m['moneda']: m['valor'] for m in arbol['monedas']}
        filas, _ = _filas_desde(hijos_objetivo('CRIPTOACTIVOS'), act_mon, total)
        bloques.append(('Por moneda', filas))
        for m in arbol['monedas']:
            hijos = hijos_objetivo(f"CRIPTOACTIVOS > {m['moneda']}")
            if not hijos:
                continue
            act_estr = {e['estrategia']: e['valor'] for e in m['estrategias']}
            filas_e, _ = _filas_desde(hijos, act_estr, m['valor'])
            bloques.append((f"{m['moneda']} por estrategia", filas_e))

    elif clave_pilar == 'INVERSIONES_ALTERNATIVAS':
        conn = consultas.conectar()
        c = conn.cursor()
        rows = c.execute("SELECT id, composicion FROM activos "
                         "WHERE activo=1 AND pilar='INVERSIONES_ALTERNATIVAS'").fetchall()
        agg = {'PRESTAMOS': 0.0, 'BONOS': 0.0}
        for aid, comp in rows:
            v = consultas.valor_actual_activo(c, aid) or 0.0
            key = 'PRESTAMOS' if comp == 'PRESTAMOS' else ('BONOS' if comp == 'BONOS' else 'OTROS')
            agg[key] = agg.get(key, 0.0) + v
        conn.close()
        total = sum(agg.values())
        filas, _ = _filas_desde(hijos_objetivo('INVERSIONES_ALTERNATIVAS'), agg, total)
        bloques.append(('Por composición', filas))

    elif clave_pilar == 'RENTA_FIJA':
        mapa = cargar_rf_bloques()   # {isin: 'conservador'|'rentabilidad'|'indexada'|...}
        conn = consultas.conectar()
        c = conn.cursor()
        rows = c.execute("SELECT id, isin, tipo FROM activos "
                         "WHERE activo=1 AND pilar='RENTA_FIJA'").fetchall()
        agg = {}
        for aid, isin, tipo in rows:
            v = consultas.valor_actual_activo(c, aid) or 0.0
            # 'conservador' -> 'BLOQUE_CONSERVADOR', 'indexada' -> 'BLOQUE_INDEXADA', etc.
            # (casa con la clave del hijo del objetivo, que es 'Bloque X' -> BLOQUE_X)
            clave = 'BLOQUE_' + _clave(_bloque_rf(isin, tipo, mapa))
            agg[clave] = agg.get(clave, 0.0) + v
        conn.close()
        total = sum(agg.values())
        filas, _ = _filas_desde(hijos_objetivo('RENTA_FIJA'), agg, total)
        bloques.append(('Por bloque', filas))

    return bloques
