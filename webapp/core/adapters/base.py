# -*- coding: utf-8 -*-
"""Interfaz común de todos los marketplaces."""


class Progreso:
    """Permite a los adaptadores avisar avance. Lo implementa pipeline."""

    def fase(self, nombre):
        pass

    def pct(self, valor):
        pass

    def log(self, msg):
        pass

    def cancelado(self):
        return False


class Adaptador:
    """Clase base de un marketplace (ML, Cencosud, Falabella, …)."""

    #: id corto, ej. 'mercadolibre'
    nombre = ''
    #: nombre para mostrar, ej. 'Mercado Libre'
    etiqueta = ''

    @classmethod
    def detectar_plantilla(cls, path):
        """¿Este .xlsx es una plantilla de este marketplace?"""
        raise NotImplementedError

    @classmethod
    def analizar(cls, cfg, log=lambda m: None):
        """Carga bases y devuelve {'categorias', 'prefijos', 'total_modelos'}."""
        raise NotImplementedError

    @classmethod
    def generar(cls, cfg, prog):
        """Escribe el xlsx. Devuelve el resumen (archivo, filas, avisos…)."""
        raise NotImplementedError
