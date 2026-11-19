# -*- coding: utf-8 -*-
"""Rutas relacionadas con fotos de la última planilla.

Endpoint:
- GET /api/fotos → devuelve URLs de fotos por fila.
"""

from flask import Blueprint, jsonify

from ..helpers import _err, _lock_salida, _abrir_salida

bp = Blueprint('fotos', __name__)

@bp.route('/api/fotos')
def api_fotos():
    """Fotos de cada fila de la última planilla (para revisarlas en la web)."""
    try:
        with _lock_salida:
            wb, ws, _fh, fi, idx, _ruta = _abrir_salida()
            if 'fotos' not in idx:
                return jsonify({'ok': False,
                                'error': 'Esta planilla no tiene columna de fotos.'})
            col_fotos = idx['fotos'] + 1
            def texto(r, campo):
                c = idx.get(campo)
                if c is None:
                    return ''
                v = ws.cell(row=r, column=c + 1).value
                return '' if v is None else str(v).strip()
            filas, sin, total = [], [], 0
            for r in _filas_datos(ws, fi, idx):
                crudo = ws.cell(row=r, column=col_fotos).value or ''
                urls = [u.strip() for u in str(crudo).replace('\\n', ',').split(',') if u.strip()]
                sku = texto(r, 'sku')
                if not urls:
                    sin.append(sku or f'fila {r}')
                    continue
                total += len(urls)
                filas.append({'fila': r, 'sku': sku,
                              'color': texto(r, 'color'),
                              'talla': texto(r, 'talla'),
                              'urls': urls})
            return jsonify({'ok': True, 'filas': filas,
                            'sin_fotos': sin, 'total_fotos': total})
    except Exception as e:
        return _err(e)
