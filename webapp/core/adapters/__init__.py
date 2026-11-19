# -*- coding: utf-8 -*-
"""Registro de adaptadores y auto-detección por plantilla."""
from .mercadolibre import AdaptadorML
from .cencosud import AdaptadorCencosud

REGISTRO = [AdaptadorML, AdaptadorCencosud]


def detectar(path):
    """Devuelve la clase de adaptador cuya plantilla coincida, o None."""
    for cls in REGISTRO:
        try:
            if cls.detectar_plantilla(path):
                return cls
        except Exception:
            continue
    return None


def obtener(nombre):
    """Devuelve el adaptador por nombre; si no, ML por defecto."""
    for cls in REGISTRO:
        if cls.nombre == nombre:
            return cls
    return AdaptadorML
