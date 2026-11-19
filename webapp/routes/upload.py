# -*- coding: utf-8 -*-
"""Rutas para subir archivos y gestionar rutas.

Endpoints:
- POST /api/upload  → subir bases, complementos, fotos o plantilla.
- POST /api/paths   → actualizar referencias simples.
"""

from flask import Blueprint, jsonify, request

from ..helpers import _err, _guardar_unico, _cfg_opciones, _cfg_archivos
from ..core import state as S

bp = Blueprint('upload', __name__)

@bp.route('/api/upload', methods=['POST'])
def api_upload():
    """Sube archivos (drag & drop o selector) a datos/<tipo>/.
    tipo: bases | complementos | fotos | plantilla.
    """
    try:
        tipo = request.form.get('tipo') or ''
        sub = 'plantillas' if tipo == 'plantilla' else tipo
        if sub not in S.DIRS:
            return jsonify({'ok': False, 'error': f'Tipo inválido: {tipo!r}'}), 400
        files = [f for f in request.files.getlist('archivos') if f and getattr(f, 'filename', '')]
        if not files:
            return jsonify({'ok': False, 'error': 'No se recibió ningún archivo.'}), 400
        destino_dir = S.DIRS[sub]
        os.makedirs(destino_dir, exist_ok=True)
        st = S.cargar()
        avisos = []
        for f in files:
            nombre = os.path.basename(f.filename.replace('\\\\', '/')).strip()
            ext = os.path.splitext(nombre)[1].lower()
            if ext not in S.EXTS:
                avisos.append(f'Ignorado (no es .xlsx): {nombre}')
                continue
            ruta = os.path.join(destino_dir, nombre)
            if not os.path.isfile(ruta):
                nombre = _guardar_unico(destino_dir, f, nombre)
                ruta = os.path.join(destino_dir, nombre)
            # actualizar state según tipo
            if tipo == 'bases':
                if any(b.get('archivo') == nombre for b in st.get('bases', [])):
                    continue
                st['bases'].append({'nombre': os.path.splitext(nombre)[0],
                                    'archivo': nombre,
                                    'activa': True})
            elif tipo == 'complementos':
                if nombre not in st.get('complementos', []):
                    st['complementos'].append(nombre)
            elif tipo == 'fotos':
                st['fotos'] = nombre
            elif tipo in ('plantilla', 'plantillas-categorias'):
                st['plantilla'] = nombre
        S.guardar(st)
        resp = {'ok': True, 'avisos': avisos}
        if tipo == 'bases':
            resp['bases'] = st['bases']
        elif tipo == 'complementos':
            resp['complementos'] = st['complementos']
        elif tipo == 'fotos':
            resp['fotos'] = st['fotos']
        elif tipo in ('plantilla', 'plantillas-categorias'):
            resp['plantilla'] = st['plantilla']
        resp['disponibles'] = {k: S.archivos_en(k) for k in S.DIRS}
        return jsonify(resp)
    except Exception as e:
        return _err(e)

@bp.route('/api/paths', methods=['POST'])
def api_paths():
    """Actualiza rutas simples (plantilla, fotos, complementos, outdir)."""
    try:
        st = S.cargar()
        data = request.get_json(force=True) or {}
        for k in ('plantilla', 'fotos', 'complementos', 'outdir'):
            if k in data:
                st[k] = data[k]
        S.guardar(st)
        return jsonify({'ok': True})
    except Exception as e:
        return _err(e)
