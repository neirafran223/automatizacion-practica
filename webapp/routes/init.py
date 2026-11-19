# -*- coding: utf-8 -*-
"""Rutas de inicialización y gestión de bases.

Incluye:
- GET /api/init  → información de estado y catálogos
- POST /api/bases → actualizar la lista de bases
"""

import os
from flask import Blueprint, jsonify, request

from ..helpers import _err, _cfg_opciones, _cfg_archivos
from ..config import CAMPOS
from ..core import loader, state as S

bp = Blueprint('init', __name__)

@bp.route('/api/init')
def api_init():
    try:
        st = S.cargar()
        from ..core import adapters
        return jsonify({
            'ok': True,
            'disponible': loader.DISPONIBLE,
            'error_rp': loader.ERROR,
            'marketplaces': [{'nombre': c.nombre, 'etiqueta': c.etiqueta}
                             for c in adapters.REGISTRO],
            'archivos': {
                'bases': st.get('bases') or [],
                'complementos': st.get('complementos') or [],
                'fotos': st.get('fotos') or '',
                'plantilla': st.get('plantilla') or '',
            },
            'disponibles': {k: S.archivos_en(k) for k in S.DIRS},
            'plantillas_categoria': S.plantillas_disponibles(),
            'opciones': {k: st.get(k, '') for k in CAMPOS},
            'ultima_salida': st.get('ultima_salida', ''),
        })
    except Exception as e:
        return _err(e)

@bp.route('/api/bases', methods=['POST'])
def api_bases():
    try:
        data = request.get_json(force=True) or {}
        lista = data.get('bases')
        if not isinstance(lista, list):
            return jsonify({'ok': False, 'error': 'Falta la lista bases.'}), 400
        limpias = []
        for b in lista:
            if not isinstance(b, dict):
                continue
            archivo = os.path.basename(str(b.get('archivo') or '')).strip()
            nombre = str(b.get('nombre') or '').strip() or os.path.splitext(archivo)[0]
            if not archivo:
                continue
            limpias.append({'nombre': nombre, 'archivo': archivo,
                            'activa': bool(b.get('activa', True))})
        st = S.cargar()
        st['bases'] = limpias
        S.guardar(st)
        return jsonify({'ok': True, 'bases': limpias})
    except Exception as e:
        return _err(e)

"""Rutas de inicialización y gestión de bases.

Incluye:
- GET /api/init  → información de estado y catálogos
- POST /api/bases → actualizar la lista de bases
"""


