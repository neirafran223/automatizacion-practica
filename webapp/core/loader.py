# -*- coding: utf-8 -*-
"""Conecta con el código de RellenarPlanilla (no se duplica nada)."""
import os
import sys

# Carpeta de RellenarPlanilla: al lado de esta (Escritorio\RellenarPlanilla)
_RAIZ_WEB = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))  # ...\PlanillasML-Web
_RP_CANDIDATAS = [
    os.path.join(os.path.dirname(_RAIZ_WEB), 'RellenarPlanilla'),
    r'C:\Users\neira\OneDrive\Escritorio\RellenarPlanilla',
]

RP = None
for _c in _RP_CANDIDATAS:
    if os.path.isfile(os.path.join(_c, 'rellenar_planilla.py')):
        RP = _c
        break

if RP and RP not in sys.path:
    sys.path.insert(0, RP)

DISPONIBLE = RP is not None
ERROR = None if DISPONIBLE else (
    'No encontré la carpeta de RellenarPlanilla. Debe estar al lado de '
    'PlanillasML-Web (ej. Escritorio\\RellenarPlanilla).')


def importar(nombre):
    """Importa un módulo de RellenarPlanilla. Lanza RuntimeError si no está."""
    if not DISPONIBLE:
        raise RuntimeError(ERROR)
    try:
        return __import__(nombre)
    except Exception as e:
        raise RuntimeError('No pude importar %s de RellenarPlanilla: %s' % (nombre, e))
