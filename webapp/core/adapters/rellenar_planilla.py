# -*- coding: utf-8 -*-
"""Adaptador que envuelve la lógica de *rellenar_planilla*.
Este archivo solo delega en los helpers y en la función
_elegir_hoja, añadiendo la categoría que envía el cliente.
"""

import os
from .. import loader
from ...helpers import (
    _elegir_hoja,
    _cargar_bases,
    _cargar_complemento,
    _cargar_fotos,
    _tabla_categorias,
    _post_procesar_salida,
    _leer_plantilla_previa,
)
from .. import state as S


def detectar_plantilla(path):
    """Indica si el archivo corresponde a la plantilla esperada."""
    if not path or not os.path.isfile(path):
        return False
    import openpyxl
    rp = loader.importar('rellenar_planilla')
    wb = openpyxl.load_workbook(path, data_only=True)
    try:
        nombre, *_ = rp.detectar_hoja_productos(wb)
        return nombre is not None
    finally:
        wb.close()


def generar(cfg, prog):
    """Genera la planilla a partir de bases y complementos."""
    prog.fase('Cargando archivos')
    prog.pct(5)

    bases = [p for p in (cfg.get('bases') or []) if p]
    prefijo = (cfg.get('prefijo') or '').strip() or None
    log = prog.log

    log(f'Cargando {len(bases)} base(s)…')
    productos = _cargar_bases(bases, prefijo=prefijo, log=log)

    complementos = []
    for c in (cfg.get('complementos') or []):
        if c:
            log(f'Complemento: {os.path.basename(c)}')
            complementos.append(_cargar_complemento(c))

    fotos = _cargar_fotos(cfg['fotos']) if cfg.get('fotos') else {}
    if fotos:
        log(f'Fotos URL: {len(fotos)} modelos')

    # ------------------------------------------------------------------
    # 1) Detectar la hoja a usar (con fallback de categoría)
    # ------------------------------------------------------------------
    # Los valores que vienen del workbook actual:
    wb = loader.importar('rellenar_planilla').abrir_ultima_salida()
    hojas_encontradas = wb.sheetnames
    hoja_actual = cfg.get('hoja_actual')
    cat_actual = cfg.get('cat_actual')

    # ---- Línea modificada ----  (añadimos la categoría que el cliente envía)
    hoja_elegida = _elegir_hoja(
        hojas_encontradas,
        hoja_actual,
        cat_actual,
        categoria_usuario=cfg.get('categoria')
    )
    # ---------------------------------------------------------------

    # 2) Categorizar los productos (setea prod["categoria"])
    prog.fase('Categorizando productos')
    prog.pct(15)
    filas = _tabla_categorias(productos, complementos)
    log(f'Categorías encontradas: {len(filas)}')

    # 3) Ruta de salida
    prog.fase('Generando planilla')
    prog.pct(40)
    outdir = cfg.get('outdir') or S.SALIDA
    os.makedirs(outdir, exist_ok=True)
    cuenta = (cfg.get('cuenta') or '').strip()
    nombre = cfg.get('nombre_salida') or ''
    if not nombre:
        nombre = 'planilla' + ('_' + cuenta if cuenta else '') + '.xlsx'
    if not nombre.lower().endswith('.xlsx'):
        nombre += '.xlsx'
    path_salida = os.path.join(outdir, nombre)

    # 4) Llamar a la rutina real que rellena la hoja
    stats = loader.importar('rellenar_planilla').rellenar(
        cfg['plantilla'],
        path_salida,
        productos,
        complementos,
        fotos,
        categoria_objetivo=(cfg.get('categoria') or '').strip() or None,
        log=prog.log,
        limite_modelos=cfg.get('limite') or None,
        modelo_especifico=(cfg.get('modelos') or '').strip() or None,
        usar_ml_publico=bool(cfg.get('usar_ml')),
        max_ml=int(cfg.get('max_ml') or 0),
        cancel=prog.cancelado,
    )

    # 5) Post‑proceso (herencia de diseño, color, prefijo, etc.)
    prog.fase('Completando planilla')
    prog.pct(90)
    previas = _leer_plantilla_previa(cfg['plantilla'])
    post = _post_procesar_salida(path_salida, previas, cfg, log)

    # logs de lo que se heredó / ajustó
    if post.get('heredadas'):
        log(f'Valores heredados de la plantilla: {post["heredadas"]} celda(s)')
    if post.get('diseno'):
        log(f'Diseño copiado desde Diseño de la tela: {post["diseno"]} fila(s)')
    if post.get('composicion'):
        log(f'Composición deducida del título/descripción: {post["composicion"]} fila(s)')
    if post.get('color'):
        log(f'Color por defecto "{cfg.get("color_defecto")}" aplicado: {post["color"]} fila(s)')
    if post.get('color_ajustadas'):
        log(f'Color ajustado al más parecido de la lista: {post["color_ajustadas"]} fila(s)')
    if post.get('color_sin_lista'):
        log('⚠ Colores sin equivalente en la lista (se dejaron tal cual): '
            + ', '.join(post['color_sin_lista']))
    if post.get('fotos'):
        log(f'Fotos separadas por coma (sin espacios): {post["fotos"]} fila(s)')

    n_pref = post.get('prefijo', 0)
    if n_pref:
        log('Prefijo "%s-" aplicado a %d SKUs'
            % ((cfg.get('prefijo_sku') or '').upper().rstrip('-'), n_pref))

    prog.fase('Completado')
    prog.pct(100)

    resumen = {
        'archivo': nombre,
        'ruta': path_salida,
        'bytes': os.path.getsize(path_salida) if os.path.exists(path_salida) else 0,
        'modelos': stats.get('modelos', 0),
        'avisos': post.get('avisos', []),
    }
    return resumen