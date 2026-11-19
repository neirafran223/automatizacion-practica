# -*- coding: utf-8 -*-
"""Orquesta: resolver adaptador → analizar/generar en hilo con progreso."""
import threading
import traceback

from . import adapters
from . import state as S
from .adapters.base import Progreso

_lock = threading.Lock()
_prog = {
    'activo': False, 'fase': '', 'detalle': '', 'pct': 0,
    'cancelar': False, 'log': [],
    'resultado': None, 'error': None,
}


def progreso():
    with _lock:
        p = dict(_prog)
        p['log'] = list(_prog['log'])[-40:]
        return p


def cancelar():
    with _lock:
        _prog['cancelar'] = True


def resolver(cfg):
    """Elige el adaptador: por nombre, o autodetectando la plantilla."""
    nombre = (cfg.get('marketplace') or '').strip()
    if nombre:
        return adapters.obtener(nombre)
    plantilla = cfg.get('plantilla') or ''
    cls = adapters.detectar(plantilla) if plantilla else None
    return cls or adapters.obtener('')


class _ProgImpl(Progreso):
    """Progreso concreto ligado al estado global _prog."""

    def fase(self, nombre):
        with _lock:
            _prog['fase'] = nombre

    def pct(self, valor):
        with _lock:
            _prog['pct'] = valor

    def log(self, msg):
        with _lock:
            _prog['log'].append(str(msg))
            _prog['detalle'] = str(msg)
            # sube el % con cada detalle que imprime rellenar()
            if 40 <= _prog['pct'] < 85:
                _prog['pct'] += 1

    def cancelado(self):
        with _lock:
            return _prog['cancelar']


def analizar(cfg):
    cls = resolver(cfg)
    res = cls.analizar(cfg, log=lambda m: None)
    res['marketplace_detectado'] = cls.nombre
    return res


def generar(cfg):
    with _lock:
        if _prog['activo']:
            return {'ok': False, 'error': 'Ya hay una generación en curso.'}
        _prog.update(activo=True, cancelar=False, fase='Iniciando',
                     pct=0, resultado=None, error=None, log=[])
    threading.Thread(target=_hilo, args=(dict(cfg),), daemon=True).start()
    return {'ok': True}


def _hilo(cfg):
    prog = _ProgImpl()
    try:
        cls = resolver(cfg)
        prog.log('Marketplace: %s' % cls.etiqueta)
        resumen = cls.generar(cfg, prog)
        with _lock:
            _prog['resultado'] = resumen
            _prog['activo'] = False
            _prog['fase'] = 'Completado'
            _prog['pct'] = 100
    except Exception as e:
        with _lock:
            _prog['error'] = '%s: %s' % (type(e).__name__, e)
            _prog['activo'] = False
            _prog['fase'] = 'Error'
        with _lock:
            _prog['log'].append(traceback.format_exc())
