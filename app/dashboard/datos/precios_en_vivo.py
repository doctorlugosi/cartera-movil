"""
Reexporta las funciones de precios en vivo (Metals.Dev, CoinGecko) definidas
en scripts/precios_en_vivo.py, para que el dashboard use la misma logica
que la cadena de actualizacion en vez de duplicarla.
"""
import os
import sys

RUTA_SCRIPTS = os.path.join(os.path.dirname(__file__), '..', '..', 'scripts')
if RUTA_SCRIPTS not in sys.path:
    sys.path.insert(0, RUTA_SCRIPTS)

from precios_en_vivo import (  # noqa: F401
    historico_metal,
    precio_actual_metal,
    historico_cripto,
    precio_actual_cripto,
    precio_actual_cripto_eur,
)
