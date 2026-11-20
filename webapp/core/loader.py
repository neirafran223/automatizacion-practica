# -*- coding: utf-8 -*-
"""Conecta con el código de RellenarPlanilla (no se duplica nada)."""
import os
import sys

# Carpeta de RellenarPlanilla: al lado de esta (Escritorio\RellenarPlanilla)
_RAIZ_WEB = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))  # ...\PlanillasML-Web
_RP_CANDIDATAS = [
    os.path.join(os.path.dirname(_RAIZ_WEB), 'RellenarPlanilla'),
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
    'No encontré la carpeta de RellenarPlanilla. La conversión de planillas '
    'viejas funciona igual (va incluida en la webapp); para el flujo de '
    'generación, poné RellenarPlanilla al lado de PlanillasML-Web.')


def importar(nombre):
    """Importa un módulo de RellenarPlanilla.

    Si la carpeta no está, ``rellenar_planilla`` cae al subconjunto mínimo
    embebido en la webapp (``webapp.core.rp_min``): alcanza para convertir
    planillas viejas. El resto de los módulos siguen requiriendo la carpeta.
    """
    if not DISPONIBLE:
        if nombre == 'rellenar_planilla':
            from . import rp_min
            return rp_min
        raise RuntimeError(ERROR)
    try:
        return __import__(nombre)
    except Exception as e:
        raise RuntimeError('No pude importar %s de RellenarPlanilla: %s' % (nombre, e))
