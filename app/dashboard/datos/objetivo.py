"""
DISTRIBUCION OBJETIVO (para la pestana Analisis)
================================================
Lee la distribucion objetivo del usuario (imports/Objetivos/objetivo_distribucion.csv,
jerarquico por 'ruta') y la tabla de sectores por escenario macro
(objetivo_sectores.csv), y las CRUZA con la distribucion real (consultas del dashboard)
para el informe comparativo (semaforo + rebalanceo en euros).

El CSV lleva el peso RELATIVO a su grupo (los hermanos suman 100 dentro de cada nivel);
aqui se calcula el peso ABSOLUTO (% del total) multiplicando por la cadena de padres.
"""
import os
import csv
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_OBJ = os.path.join(RAIZ, 'imports', 'Objetivos', 'objetivo_distribucion.csv')
CSV_SEC = os.path.join(RAIZ, 'imports', 'Objetivos', 'objetivo_sectores.csv')
CSV_RF = os.path.join(RAIZ, 'imports', 'Objetivos', 'rf_bloques.csv')

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


def cargar_objetivo():
    """Devuelve {ruta: nodo} con nodo = {ruta, etiqueta, peso_pct (rel. padre),
    peso_abs (% total), nota, padre, hijos:[rutas]}."""
    nodos = {}
    with open(CSV_OBJ, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            ruta = (r.get('ruta') or '').strip()
            if not ruta:
                continue
            peso = (r.get('peso_pct') or '').strip().replace(',', '.')
            partes = ruta.split(' > ')
            nodos[ruta] = {
                'ruta': ruta,
                'etiqueta': (r.get('etiqueta') or partes[-1]).strip(),
                'peso_pct': float(peso) if peso else None,
                'nota': (r.get('nota') or '').strip(),
                'padre': ' > '.join(partes[:-1]) if len(partes) > 1 else None,
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

    for ruta, n in nodos.items():
        n['peso_abs'] = peso_abs(ruta)
    return nodos


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


def cargar_rf_bloques():
    """{isin: 'conservador'|'rentabilidad'} para repartir la renta fija por bloque."""
    res = {}
    if os.path.exists(CSV_RF):
        with open(CSV_RF, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                isin = (r.get('isin') or '').strip()
                bloque = (r.get('bloque') or '').strip().lower()
                if isin and bloque:
                    res[isin] = bloque
    return res


def cargar_sectores(escenario='estable'):
    """{sector: peso_pct} para el escenario dado (crecimiento/estable/recesion)."""
    col = escenario if escenario in ('crecimiento', 'estable', 'recesion') else 'estable'
    res = {}
    with open(CSV_SEC, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            res[r['sector'].strip()] = float(str(r[col]).replace(',', '.'))
    return res


# ---------------------------------------------------------------------------
# Comparacion objetivo <-> real
# ---------------------------------------------------------------------------
def comparativa_pilares():
    """Nivel 1. Devuelve (filas, total_eur). Cada fila:
    {clave, etiqueta, obj, act_pct, act_eur, desv (pp), ajuste_eur}."""
    from datos import consultas
    distrib, total = consultas.distribucion_por_pilar()
    actual = {p: (v, pct) for p, v, pct in distrib}
    filas = []
    for clave, etiqueta, obj in pilares_objetivo():
        obj = obj or 0.0
        act_eur, act_pct = actual.get(clave, (0.0, 0.0))
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
        mapa = cargar_rf_bloques()   # {isin: 'conservador'|'rentabilidad'}
        clave_de = {'conservador': 'BLOQUE_CONSERVADOR', 'rentabilidad': 'BLOQUE_RENTABILIDAD'}
        conn = consultas.conectar()
        c = conn.cursor()
        rows = c.execute("SELECT id, isin, tipo FROM activos "
                         "WHERE activo=1 AND pilar='RENTA_FIJA'").fetchall()
        agg = {}
        for aid, isin, tipo in rows:
            v = consultas.valor_actual_activo(c, aid) or 0.0
            bloque = _bloque_rf(isin, tipo, mapa)
            clave = clave_de.get(bloque, 'BLOQUE_RENTABILIDAD')
            agg[clave] = agg.get(clave, 0.0) + v
        conn.close()
        total = sum(agg.values())
        filas, _ = _filas_desde(hijos_objetivo('RENTA_FIJA'), agg, total)
        bloques.append(('Por bloque', filas))

    return bloques
