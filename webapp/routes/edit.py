# -*- coding: utf-8 -*-
"""Rutas para editar y guardar la planilla completa.

Endpoints:
- GET  /api/planilla/edit   → devuelve todas las filas y encabezados
- POST /api/planilla/edit   → guarda los cambios enviados por el cliente
"""

from flask import Blueprint, jsonify, request

from ..helpers import _err, _lock_salida, _abrir_salida, _encabezados, _filas_datos, _coerce_valor

bp = Blueprint('edit', __name__)

@bp.route('/api/planilla/edit')
def api_planilla_editar():
    """Devuelve todas las filas de productos (sin recortar) para editarlas en la UI."""
    try:
        with _lock_salida:
            wb, ws, fh, fi, idx, ruta = _abrir_salida()
            enc = _encabezados(ws, fh)
            cols = [i for i, h in enumerate(enc) if h]
            if not cols:
                cols = list(range(len(enc)))
            filas = []
            for r in _filas_datos(ws, fi, idx):
                celdas = []
                for i in cols:
                    v = ws.cell(row=r, column=i + 1).value
                    celdas.append('' if v is None else str(v))
                filas.append({'fila': r, 'celdas': celdas})
            return jsonify({
                'ok': True,
                'archivo': os.path.basename(ruta),
                'encabezados': [{'col': i, 'texto': enc[i]} for i in cols],
                'filas': filas,
            })
    except Exception as e:
        return _err(e)

@bp.route('/api/planilla/edit', methods=['POST'])
def api_planilla_guardar():
    """Guarda los cambios de celdas enviados por el cliente."""
    try:
        data = request.get_json(force=True) or {}
        cambios = data.get('cambios')
        if not isinstance(cambios, list) or not cambios:
            return jsonify({'ok': False, 'error': 'No hay cambios para guardar.'}), 400
        if len(cambios) > 5000:
            return jsonify({'ok': False,
                            'error': 'Demasiados cambios de una vez (máx. 5000).'}), 400
        with _lock_salida:
            wb, ws, fh, fi, idx, ruta = _abrir_salida(data_only=False)
            tmp = ruta + '.tmp'
            try:
                enc = _encabezados(ws, fh)
                guardados = 0
                for c in cambios:
                    try:
                        fila = int(c.get('fila'))
                        col = int(c.get('col'))
                    except (TypeError, ValueError):
                        return jsonify({'ok': False,
                                        'error': 'Fila/columna inválida.'}), 400
                    if not (fi <= fila <= fi + 1999) or not (0 <= col < 500):
                        return jsonify({'ok': False,
                                        'error': f'Celda fuera de rango: fila {fila} columna {col}.'}), 400
                    valor = c.get('valor')
                    if not isinstance(valor, str):
                        valor = '' if valor is None else str(valor)
                    celda = ws.cell(row=fila, column=col + 1)
                    celda.value = _coerce_valor(celda.value,
                                                enc[col] if col < len(enc) else '',
                                                valor)
                    guardados += 1
                wb.save(tmp)
                os.replace(tmp, ruta)
                return jsonify({'ok': True, 'guardados': guardados})
            finally:
                wb.close()
                if os.path.isfile(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
    except Exception as e:
        return _err(e)
