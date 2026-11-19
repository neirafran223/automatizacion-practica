# -*- coding: utf-8 -*-
"""Routes that expose the conversion API.

All heavy logic lives in ``webapp.helpers``; this module only creates the
Flask Blueprint and wires the endpoint functions.
"""

from flask import Blueprint, jsonify, request
import os
from ..helpers import (
    _err,
    _guardar_unico,
    _ruta_plantilla_actual,
    _guardar_plantilla_actual,
    _convertir_planilla,
    _convertir_combinadas,
    _fuentes_conversion,
    SinCategoria,
)

bp = Blueprint('conversion', __name__)

@bp.route('/api/conversion')
def api_conversion():
    try:
        from ..core import state as S
        st = S.cargar()
        outdir = st.get('outdir') or S.SALIDA
        pl = {'existe': os.path.isfile(S.PLANTILLA_ACTUAL),
              'nombre': st.get('plantilla_actual') or '',
              'categorias': st.get('plantilla_categorias') or []}
        return jsonify({'ok': True,
                        'fuentes': _fuentes_conversion(outdir),
                        'plantilla': pl})
    except Exception as e:
        return _err(e)

@bp.route('/api/convertir', methods=['POST'])
def api_convertir():
    """Convierte planillas viejas al formato nuevo.
    Accepts multipart upload (field *archivos*) or JSON with {archivo, origen}.
    """
    try:
        from ..core import state as S
        st = S.cargar()
        outdir = st.get('outdir') or S.SALIDA
        pendientes = []

        # Categoria elegida por el cliente (puede venir en form-data o JSON)
        cat = request.form.get('categoria') or (request.get_json(silent=True) or {}).get('categoria')

        # Plantilla nueva opcional
        plant = request.files.get('plantilla')
        if plant and getattr(plant, 'filename', ''):
            try:
                _guardar_plantilla_actual(plant)
            except Exception as e:
                return jsonify({'ok': False, 'error': str(e)}), 400

        try:
            ruta_plantilla = _ruta_plantilla_actual()
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 400

        # Archivos subidos
        subidas = [f for f in request.files.getlist('archivos')
                   if f and getattr(f, 'filename', '')]
        if subidas:
            os.makedirs(S.PLANILLAS_ANTIGUAS, exist_ok=True)
            for f in subidas:
                nombre = os.path.basename(f.filename.replace('\\\\', '/')).strip()
                if os.path.splitext(nombre)[1].lower() not in S.EXTS:
                    continue
                destino_dir = S.PLANILLAS_ANTIGUAS
                if not os.path.isfile(os.path.join(destino_dir, nombre)):
                    nombre = _guardar_unico(destino_dir, f, nombre)
                pendientes.append((os.path.join(destino_dir, nombre), nombre))
        else:
            data = request.get_json(force=True) or {}
            nombre = os.path.basename(str(data.get('archivo') or '').replace('\\\\', '/'))
            origen = data.get('origen') or 'salida'
            if not nombre or os.path.splitext(nombre)[1].lower() not in S.EXTS:
                return jsonify({'ok': False, 'error': 'Archivo inválido.'}), 400
            base = outdir if origen == 'salida' else S.PLANILLAS_ANTIGUAS
            ruta = os.path.join(base, nombre)
            if not os.path.isfile(ruta):
                return jsonify({'ok': False, 'error': f'No existe: {nombre}'}), 404
            pendientes.append((ruta, nombre))

        if not pendientes:
            return jsonify({'ok': False, 'error': 'No se recibió ningún archivo .xlsx.'}), 400

        resultados = []
        if len(pendientes) > 1:
            try:
                resultados = _convertir_combinadas(pendientes, outdir, ruta_plantilla)
            except Exception as e:
                resultados = [{'ok': False,
                               'origen': ' + '.join(n for _r, n in pendientes),
                               'error': f'{type(e).__name__}: {e}'}]
        else:
            for ruta_o, nombre_o in pendientes:
                destino = os.path.join(outdir, os.path.splitext(nombre_o)[0] + '-nuevo-formato.xlsx')
                try:
                    r = _convertir_planilla(ruta_o, destino, ruta_plantilla,
                                            categoria_usuario=cat)
                    r.update({'ok': True, 'origen': nombre_o,
                              'archivo': os.path.basename(destino)})
                except SinCategoria as e:
                    r = {'ok': False, 'origen': nombre_o, 'mensaje': str(e)}
                except Exception as e:
                    r = {'ok': False, 'origen': nombre_o,
                         'error': f'{type(e).__name__}: {e}'}
                resultados.append(r)

        return jsonify({'ok': True, 'resultados': resultados})
    except Exception as e:
        return _err(e)


@bp.route('/api/plantilla', methods=['POST'])
def api_plantilla():
    try:
        f = request.files.get('plantilla')
        if not f or not getattr(f, 'filename', ''):
            return jsonify({'ok': False, 'error': 'No se recibió ningún archivo.'}), 400

        nombre, hoja, categorias = _guardar_plantilla_actual(f)

        return jsonify({
            'ok': True,
            'archivo': nombre,
            'hoja': hoja,
            'categorias': categorias,
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400


@bp.route('/api/plantilla', methods=['DELETE'])
def api_plantilla_borrar():
    try:
        from ..core import state as S
        if os.path.isfile(S.PLANTILLA_ACTUAL):
            os.remove(S.PLANTILLA_ACTUAL)
        st = S.cargar()
        st['plantilla_actual'] = ''
        st['plantilla_categorias'] = []
        S.guardar(st)
        return jsonify({'ok': True})
    except Exception as e:
        return _err(e)


@bp.route('/api/planillas-antiguas', methods=['DELETE'])
def api_planillas_antiguas_borrar():
    try:
        from ..core import state as S
        borradas = 0
        if os.path.isdir(S.PLANILLAS_ANTIGUAS):
            for nombre in sorted(os.listdir(S.PLANILLAS_ANTIGUAS)):
                if nombre.startswith('~$'):
                    continue
                if os.path.splitext(nombre)[1].lower() not in S.EXTS:
                    continue
                ruta = os.path.join(S.PLANILLAS_ANTIGUAS, nombre)
                if os.path.isfile(ruta):
                    os.remove(ruta)
                    borradas += 1
        return jsonify({'ok': True, 'borradas': borradas})
    except Exception as e:
        return _err(e)