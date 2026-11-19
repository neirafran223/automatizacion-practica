# -*- coding: utf-8 -*-
"""Endpoints del flujo de generación: analyze / generate / progress / cancel.

La lógica pesada vive en ``webapp.core.pipeline``; aquí solo se arma la
configuración (opciones del cliente + archivos del catálogo) y se responde.
"""

from flask import Blueprint, jsonify, request

from ..helpers import _err, _cfg_opciones, _cfg_archivos
from ..core import pipeline as P
from ..core import state as S

bp = Blueprint('analyze', __name__)


def _cfg_del_cliente():
    """Opciones del cliente (ignora cualquier 'bases' que mande) + archivos
    del catálogo. Lanza RuntimeError si no hay bases activas."""
    data = request.get_json(force=True, silent=True) or {}
    st = S.cargar()
    opciones = _cfg_opciones(data, st)
    cfg, _faltan = _cfg_archivos(dict(opciones), st)
    # persistir las opciones para la próxima carga
    st = S.cargar()
    st.update(opciones)
    S.guardar(st)
    return cfg


@bp.route('/api/analyze', methods=['POST'])
def api_analyze():
    try:
        cfg = _cfg_del_cliente()
        res = P.analizar(cfg)
        res['ok'] = True
        res['avisos'] = list(cfg.get('avisos_bases') or [])
        return jsonify(res)
    except Exception as e:
        return _err(e)


@bp.route('/api/generate', methods=['POST'])
def api_generate():
    try:
        cfg = _cfg_del_cliente()
        res = P.generar(cfg)
        if not res.get('ok'):
            return jsonify({'ok': False,
                            'error': res.get('error') or 'No pude iniciar.'}), 409
        return jsonify({'ok': True})
    except Exception as e:
        return _err(e)


@bp.route('/api/progress')
def api_progress():
    try:
        p = P.progreso()
        p['ok'] = True
        return jsonify(p)
    except Exception as e:
        return _err(e)


@bp.route('/api/cancel', methods=['POST'])
def api_cancel():
    try:
        P.cancelar()
        return jsonify({'ok': True})
    except Exception as e:
        return _err(e)
