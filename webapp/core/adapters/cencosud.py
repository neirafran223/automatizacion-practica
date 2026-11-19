# -*- coding: utf-8 -*-
"""Adaptador Cencosud (París) — pendiente de implementar con su plantilla."""
from .base import Adaptador


class AdaptadorCencosud(Adaptador):
    nombre = 'cencosud'
    etiqueta = 'Cencosud'

    @classmethod
    def detectar_plantilla(cls, path):
        # TODO: cuando tengas la plantilla de ejemplo, acá se inspeccionan
        # sus hojas/encabezados para reconocerla (ej. una hoja con un nombre
        # propio o encabezados que empiecen con un texto característico).
        return False

    @classmethod
    def analizar(cls, cfg, log=lambda m: None):
        raise RuntimeError('Cencosud aún no está implementado. '
                           'Falta la plantilla de ejemplo.')

    @classmethod
    def generar(cls, cfg, prog):
        raise RuntimeError('Cencosud aún no está implementado. '
                           'Falta la plantilla de ejemplo.')
