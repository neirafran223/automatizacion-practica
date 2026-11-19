# -*- coding: utf-8 -*-
"""Funciones auxiliares reutilizables para la aplicación Flask.

Este módulo contiene todas las utilidades que antes estaban mezcladas en
`app.py`: manejo de errores, guardado de archivos, lógica de conversión,
extracción de datos de Excel, etc. Cada ruta importa solo lo que necesita
para mantener los archivos de rutas pequeños y legibles.
"""

import os
import re
import threading
import random
from flask import jsonify
import openpyxl
from pathlib import Path

# Importar los submódulos de core con ruta relativa
from .core import loader, pipeline as P, state as S
from .config import (
    CAMPOS,
    COLS_NUM,
    PLACEHOLDERS_NUEVA,
    ULTIMA_FILA_FORMULAS,
    EN_INGLES,
    TRAD_TITULO,
)

# ----------------------------------------------------------------------
# Bloqueo global para la planilla generada (previene lecturas/escrituras simultáneas)
_lock_salida = threading.Lock()

# ----------------------------------------------------------------------
# Gestión de errores y límite de carga
def _err(e, code=500):
    return jsonify({'ok': False, 'error': f"{type(e).__name__}: {e}"}), code


def _too_large(e):  # Flask error handler (registrado en la app)
    return jsonify({'ok': False, 'error': 'Archivo demasiado grande (máx. 100 MB).'}), 413


# ----------------------------------------------------------------------
# Configuración de opciones enviadas por el cliente
def _cfg_opciones(data, st):
    """Solo opciones del cliente; los archivos se agregan con _cfg_archivos."""
    return {k: data.get(k, st.get(k, '')) for k in CAMPOS}


def _cfg_archivos(cfg, st):
    """Resuelve archivos desde el catálogo/state (fuente única de verdad).
    Devuelve (cfg, bases_faltantes_en_disco).
    """
    faltan = S.bases_faltantes(st)
    cfg['bases'] = S.bases_activas(st)
    cfg['plantilla'] = S.ruta_plantilla(st.get('plantilla'))
    cfg['fotos'] = S.ruta('fotos', st.get('fotos'))
    cfg['complementos'] = [S.ruta('complementos', c) for c in (st.get('complementos') or [])]
    cfg['avisos_bases'] = faltan
    if not cfg['bases']:
        raise RuntimeError('Subí al menos un Excel de productos y dejalo activo en el catálogo.')
    return cfg, faltan


# ----------------------------------------------------------------------
# Guardado de archivos sin sobrescribir (añade "(1)", "(2)", ...)
def _guardar_unico(destino_dir, file_storage, nombre):
    """Guarda con nombre no repetido: 'a.xlsx' -> 'a (1).xlsx' si hace falta."""
    base, ext = os.path.splitext(nombre)
    cand = nombre
    i = 1
    while os.path.exists(os.path.join(destino_dir, cand)):
        cand = f"{base} ({i}){ext}"
        i += 1
    file_storage.save(os.path.join(destino_dir, cand))
    return cand


# ----------------------------------------------------------------------
# Helpers de la planilla (última salida, abrir workbook, etc.)
def _ultima_salida():
    st = S.cargar()
    ruta = st.get('ultima_salida') or ''
    return ruta if ruta and os.path.isfile(ruta) else ''


def _abrir_salida(data_only=True):
    """Abre la última planilla y devuelve (wb, ws, fila_hdr, fila_inicio, idx, ruta)."""
    import openpyxl
    ruta = _ultima_salida()
    if not ruta:
        raise RuntimeError('Aún no hay planilla generada.')
    wb = openpyxl.load_workbook(ruta, data_only=data_only)
    rp = loader.importar('rellenar_planilla')
    nombre, fh, fi, _cat = rp.detectar_hoja_productos(wb)
    if not nombre:
        wb.close()
        raise RuntimeError('No detecté la hoja de productos.')
    ws = wb[nombre]
    idx = rp.mapear_columnas(ws, fh)
    return wb, ws, fh, fi, idx, ruta


def _filas_datos(ws, fila_inicio, idx):
    """Filas con productos: bloque contiguo desde fila_inicio (por SKU)."""
    col = idx.get('sku')
    filas = []
    for r in range(fila_inicio, min(ws.max_row, fila_inicio + 1999) + 1):
        if col is not None:
            con_dato = ws.cell(row=r, column=col + 1).value not in (None, '')
        else:
            con_dato = any(ws.cell(row=r, column=c).value not in (None, '')
                           for c in range(1, ws.max_column + 1))
        if con_dato:
            filas.append(r)
        elif filas:
            break
    return filas


def _encabezados(ws, fila_hdr):
    fila = next(ws.iter_rows(min_row=fila_hdr, max_row=fila_hdr, values_only=True))
    return ['' if v is None else str(v).strip() for v in fila]


# ----------------------------------------------------------------------
# Conversión de valores (números, texto, etc.)
def _a_numero(t):
    s = t.replace(' ', '')
    if s.startswith('$'):
        s = s[1:]
    if ',' in s and '.' not in s:
        s = s.replace(',', '.')
    else:
        s = s.replace(',', '')
    n = float(s)
    return int(n) if n.is_integer() else n


def _con_prefijo_h(valor: str) -> str:
    """Devuelve el valor con prefijo 'H-'.

    - Si ya comienza con 'H-' (ignorando mayúsculas) lo devuelve tal cual,
      manteniendo la capitalización original.
    - Si comienza con 'H' sin guion, lo transforma a 'H-<resto>'.
    - En cualquier otro caso, antepone 'H-'.
    """
    v = (valor or "").strip()
    if not v:
        return v

    # Ya tiene el prefijo (H- o h-)
    if v.upper().startswith("H-"):
        return v

    # Caso "Hxxxxx" sin guion
    if v.upper().startswith("H"):
        resto = v[1:].lstrip("-")
        return f"H-{resto}"

    # Caso sin prefijo
    return f"H-{v}"


def _coerce_valor(original, encabezado, texto):
    """Valor a escribir en la celda editada.
    - numerico: numero
    - texto (SKU, MODELO, EAN, titulos): texto (anadiendo H- cuando sea SKU o MODELO)
    - vacio: None (borra celda)
    """
    t = (texto or '').strip()[:32767]
    if not t:
        return None

    # Añadir prefijo H- para SKU y MODELO
    if encabezado.upper() in ('SKU', 'MODELO'):
        t = _con_prefijo_h(t)

    es_num = any(h in (encabezado or '').upper() for h in COLS_NUM)
    if isinstance(original, (int, float)) and not isinstance(original, bool):
        try:
            return _a_numero(t)
        except ValueError:
            return t
    if original in (None, '') and es_num:
        try:
            return _a_numero(t)
        except ValueError:
            return t
    return t


# ----------------------------------------------------------------------
# Manipulación de títulos y SKUs
def _quitar_marca(texto):
    t = re.sub(r'\bripholia\b', ' ', str(texto or ''), flags=re.IGNORECASE)
    return ' '.join(t.split())


def _traducir_titulo(texto):
    def reemplazar(m):
        palabra = m.group(0)
        baja = palabra.lower()
        if baja in EN_INGLES:
            return palabra
        nueva = TRAD_TITULO.get(baja)
        if not nueva:
            return palabra
        if palabra[:1].isupper():
            nueva = nueva[:1].upper() + nueva[1:]
        return nueva
    return ' '.join(re.sub(r'[A-Za-z]+', reemplazar, str(texto or '')).split())


def _sku_sin_h(sku):
    s = ' '.join(str(sku or '').split())
    if len(s) > 2 and s[0].upper() == 'H' and s[1] == '-':
        s = s[2:].lstrip('- ')
    return s


def _titulo_final(titulo):
    t = _quitar_marca(titulo)
    t = _traducir_titulo(t)
    ajustado = False
    if len(t) > 60:
        corte = t[:60].rstrip()
        if ' ' in corte:
            corte = corte.rsplit(' ', 1)[0]
        t = corte
        ajustado = True
    return t, ajustado


# ----------------------------------------------------------------------
# Generación de EAN único (determinístico por SKU)
def _ean_unico(usados, semilla):
    intento = 0
    while True:
        rng = random.Random(f"{semilla}#{intento}")
        cuerpo = [rng.randint(0, 9) for _ in range(12)]
        suma = sum(d * (3 if i % 2 else 1) for i, d in enumerate(cuerpo))
        dv = (10 - suma % 10) % 10
        ean = ''.join(str(d) for d in cuerpo) + str(dv)
        if ean not in usados:
            usados.add(ean)
            return ean
        intento += 1


# ----------------------------------------------------------------------
# Mapeo de encabezados y filas (uso interno de la conversión)
def _cols_por_encabezado(ws, fila_hdr):
    rp = loader.importar('rellenar_planilla')
    out = {}
    for c in range(1, ws.max_column + 1):
        v = ws.cell(fila_hdr, c).value
        if v is None:
            continue
        k = rp.norm(v)
        if k and k not in out:
            out[k] = c
    return out


def _fila_datos(ws, hdr, cols, por_defecto):
    col = cols.get('CONDICION')
    if col:
        for r in range(hdr + 1, hdr + 12):
            if str(ws.cell(r, col).value or '').strip().lower() == 'nuevo':
                return r
    return por_defecto


def _limpiar_separador(ws, fila):
    for c in range(1, ws.max_column + 1):
        celda = ws.cell(fila, c)
        v = celda.value
        if v is None or (isinstance(v, str) and v.startswith('=')):
            continue
        try:
            celda.value = None
        except AttributeError:
            pass


# ----------------------------------------------------------------------
# Clases y detección de hojas (utilizadas por la conversión)
class SinCategoria(RuntimeError):
    """La planilla vieja es de una categoría que la plantilla nueva no tiene."""


def _hojas_producto(wb):
    rp = loader.importar('rellenar_planilla')
    hojas = []
    for s in wb.sheetnames:
        ws = wb[s]
        if not ws.max_row or ws.max_row < 5:
            continue
        for r in range(1, 8):
            valores = [rp.norm(ws.cell(row=r, column=c).value)
                       for c in range(1, min(ws.max_column, 40) + 1)]
            if not any(v and v.startswith('TITULO') for v in valores):
                continue
            if 'SKU' not in valores:
                continue
            candidatos = []
            for rr in (r - 2, r - 1):
                if rr < 1:
                    continue
                v = ws.cell(row=rr, column=1).value
                if not v or str(v).startswith('Título'):
                    continue
                texto = str(v).strip()
                if texto and len(texto) < 300:
                    candidatos.append(texto)
            cat = next((c for c in candidatos if '>' in c), None)
            if cat is None:
                cat = candidatos[0] if candidatos else s
            hojas.append((s, r, cat))
            break
    return hojas


def _segmentos(cat):
    rp = loader.importar('rellenar_planilla')
    if not cat:
        return []
    out = []
    for p in str(cat).split('>'):
        p = rp.norm(p).strip()
        if p:
            out.append(p)
    return out


def _elegir_hoja(hojas_n, hoja_v, cat_v, categoria_usuario=None):
    """
    Selecciona la hoja correcta según la categoría y la hoja actual.
    Si `cat_v` es None (no se detectó), se usa `categoria_usuario`
    (la que el cliente envió en la petición) como fallback.
    """
    # Fallback a la categoría proporcionada por el cliente
    if cat_v is None and categoria_usuario:
        cat_v = categoria_usuario

    viejo_arbol = _segmentos(cat_v)
    viejo_hoja = _segmentos(hoja_v)
    ultimo = (viejo_arbol or viejo_hoja)
    ultimo = ultimo[-1] if ultimo else ''

    if not cat_v:
        if len(hojas_n) == 1:
            return hojas_n[0]
        raise SinCategoria(
            "No pude detectar la categoría de la planilla; la plantilla "
            f"nueva tiene: {', '.join(h[0] for h in hojas_n)}"
        )

    for h in hojas_n:
        if _segmentos(h[2]) == viejo_arbol:
            return h
    for h in hojas_n:
        if ultimo and _segmentos(h[0])[-1] == ultimo:
            return h
    for h in hojas_n:
        seg = _segmentos(h[2])
        if ultimo and seg and seg[-1] == ultimo:
            return h
    if viejo_hoja:
        for h in hojas_n:
            if _segmentos(h[0]) == viejo_hoja:
                return h
    raise SinCategoria(
        f'Categoría no encontrada: {str(cat_v).strip()}. '
        f'La plantilla nueva tiene: {", ".join(h[0] for h in hojas_n)}'
    )


# ----------------------------------------------------------------------
# Conversión: planilla vieja -> formato nuevo de Mercado Libre
# ----------------------------------------------------------------------
_CONTADORES = ('sin_h', 'ean_nuevos', 'titulos_ajustados', 'duplicadas')


def _rp():
    """Módulo rellenar_planilla (se importa bajo demanda)."""
    return loader.importar('rellenar_planilla')


def _placeholders_nueva():
    rp = _rp()
    ph = {rp.norm(p) for p in PLACEHOLDERS_NUEVA}
    ph.add(rp.norm('Selecciona una guía o pega el código'))
    return ph


def _columnas(ws, fila_hdr):
    """{(clave_normalizada): (columna, texto_original)} de los encabezados."""
    rp = _rp()
    cols = {}
    for c in range(1, ws.max_column + 1):
        v = ws.cell(fila_hdr, c).value
        if v not in (None, ''):
            cols.setdefault(rp.norm(v), (c, v))
    return cols


def _emparejar(cols_v, cols_n):
    """Parejas (clave_nueva, col_vieja, col_nueva) y encabezados viejos sin
    contraparte en la plantilla nueva (se informan como descartadas)."""
    pares = []
    descartadas = []
    usados = set()
    for clave, (col_v, texto_v) in cols_v.items():
        destino = clave if clave in cols_n else None
        if destino is None and clave.startswith('TITULO'):
            # los encabezados de título cambian entre versiones de plantilla
            destino = next((k for k in cols_n if k.startswith('TITULO')), None)
        if destino is None or destino in usados:
            descartadas.append(str(texto_v))
            continue
        usados.add(destino)
        pares.append((destino, col_v, cols_n[destino][0]))
    return pares, descartadas


def _grupos_viejos(ws, hdr, ini):
    """Corridas consecutivas de filas con el mismo título (= mismo producto).
    El bloque de datos termina en la primera fila sin título ni SKU."""
    cols = _columnas(ws, hdr)
    c_tit = next((c for k, (c, _t) in cols.items() if k.startswith('TITULO')), None)
    c_sku = cols.get('SKU', (None, None))[0]
    if c_tit is None:
        raise RuntimeError('La planilla vieja no tiene columna de título.')
    filas = []
    r = ini
    while r <= ws.max_row:
        t = ws.cell(r, c_tit).value
        s = ws.cell(r, c_sku).value if c_sku else None
        if t in (None, '') and s in (None, ''):
            break
        filas.append(r)
        r += 1
    grupos = []
    for r in filas:
        tit = str(ws.cell(r, c_tit).value or '').strip()
        if not grupos or grupos[-1][0] != tit:
            grupos.append((tit, []))
        grupos[-1][1].append(r)
    return grupos, cols


def _fila_libre(ws, hdr, cols):
    """Primera fila de datos sin escribir (después del ejemplo de plantilla)."""
    simple = {k: c for k, (c, _t) in cols.items()}
    base = _fila_datos(ws, hdr, simple, hdr + 4)
    c_tit = next((c for k, (c, _t) in cols.items() if k.startswith('TITULO')), 1)
    c_sku = cols.get('SKU', (None, None))[0] or 2
    tope = min(ws.max_row or base, ULTIMA_FILA_FORMULAS)
    r = base
    while r <= tope:
        ocupada = any(
            v not in (None, '') and not (isinstance(v, str) and v.startswith('='))
            for v in (ws.cell(r, c_tit).value, ws.cell(r, c_sku).value)
        )
        if not ocupada:
            break
        r += 1
    return r


def _ean_valido(ean):
    if not (isinstance(ean, str) and len(ean) == 13 and ean.isdigit()):
        return False
    suma = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(ean[:12]))
    return (10 - suma % 10) % 10 == int(ean[12])


def _a_ean(valor):
    """Normaliza el código de barras viejo a string ('' si no sirve)."""
    if valor in (None, '') or isinstance(valor, bool):
        return ''
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, float):
        return str(int(valor)) if valor.is_integer() else str(valor)
    s = str(valor).strip()
    if s.endswith('.0') and s[:-2].isdigit():
        s = s[:-2]
    return s


def _nuevo_ctx(hojas_n):
    """Estado compartido durante toda una ejecución de conversión."""
    return {
        'hojas_n': hojas_n,
        'cursos': {},            # hoja -> {'fila': n, 'ultima': m}
        'usados_ean': set(),
        'usados_sku': set(),
        'placeholders': _placeholders_nueva(),
        'sin_h': 0, 'ean_nuevos': 0, 'titulos_ajustados': 0, 'duplicadas': 0,
    }


def _valor_conversion(clave_n, valor, ctx, semilla):
    """Valor final para una celda de la plantilla nueva."""
    if clave_n.startswith('TITULO'):
        t = str(valor)
        final, _ajustado = _titulo_final(t)
        if final != t:
            ctx['titulos_ajustados'] += 1
        return final
    if clave_n == 'SKU':
        v = ' '.join(str(valor).split())
        final = _con_prefijo_h(v)
        if final != v:
            ctx['sin_h'] += 1
        return final
    if clave_n == 'MODELO':
        return _con_prefijo_h(' '.join(str(valor).split()))
    if clave_n.startswith('CODIGO UNIVERSAL'):
        ean = _a_ean(valor)
        if _ean_valido(ean) and ean not in ctx['usados_ean']:
            ctx['usados_ean'].add(ean)
            return ean
        ctx['ean_nuevos'] += 1
        return _ean_unico(ctx['usados_ean'], semilla)
    if any(h in clave_n for h in COLS_NUM):
        if isinstance(valor, str):
            try:
                return _a_numero(valor)
            except ValueError:
                return valor
        if isinstance(valor, float) and valor.is_integer():
            return int(valor)
        return valor
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    return valor


def _escribir_fila(ws_v, r_v, ws_n, fila, pares, cols_n, ctx, semilla):
    """Escribe una fila de datos sin pisar fórmulas ni marcadores."""
    rp = _rp()
    # 1) los marcadores de posición de la plantilla quedan vacíos en la fila
    for _k, (c_n, _t) in cols_n.items():
        celda = ws_n.cell(fila, c_n)
        v = celda.value
        if (isinstance(v, str) and not v.startswith('=')
                and rp.norm(v) in ctx['placeholders']):
            celda.value = None
    # 2) columnas pareadas con dato en la planilla vieja
    for clave_n, col_v, col_n in pares:
        destino = ws_n.cell(fila, col_n)
        actual = destino.value
        if isinstance(actual, str) and actual.startswith('='):
            continue          # nunca se pisa una fórmula de la plantilla
        valor = ws_v.cell(r_v, col_v).value
        if valor is None:
            continue
        if isinstance(valor, str):
            if valor.strip() == '':
                continue
            if rp.norm(valor) in ctx['placeholders']:
                continue      # marcador de la vieja: no se copia
        destino.value = _valor_conversion(clave_n, valor, ctx, semilla)


def _convertir_en(ruta, wb_n, ctx, categoria_usuario=None):
    """Escribe una planilla vieja dentro de la plantilla ya abierta (wb_n)."""
    rp = _rp()
    nombre = os.path.basename(ruta)
    wb_v = openpyxl.load_workbook(ruta, data_only=True)
    try:
        hoja_v, hdr_v, ini_v, cat_v = rp.detectar_hoja_productos(wb_v)
        if not hoja_v:
            raise RuntimeError(f'No detecté la hoja de productos en {nombre}.')
        destino = _elegir_hoja(ctx['hojas_n'], hoja_v, cat_v, categoria_usuario)
        ws_v = wb_v[hoja_v]
        ws_n = wb_n[destino[0]]
        grupos, cols_v = _grupos_viejos(ws_v, hdr_v, ini_v)
        cols_n = _columnas(ws_n, destino[1])
        pares, descartadas = _emparejar(cols_v, cols_n)
        est = ctx['cursos'].get(destino[0])
        if est is None:
            est = {'fila': _fila_libre(ws_n, destino[1], cols_n), 'ultima': None}
            ctx['cursos'][destino[0]] = est
        c_sku_v = cols_v.get('SKU', (None, None))[0]
        antes = {k: ctx[k] for k in _CONTADORES}
        filas = 0
        for _tit_grupo, filas_grupo in grupos:
            # una fila en blanco entre productos y entre planillas
            if est['ultima'] is not None and est['ultima'] + 1 < ULTIMA_FILA_FORMULAS:
                sep = est['ultima'] + 1
                _limpiar_separador(ws_n, sep)
                est['fila'] = max(est['fila'], sep + 1)
            for r_v in filas_grupo:
                if est['fila'] > ULTIMA_FILA_FORMULAS:
                    break
                sku_final = ''
                if c_sku_v:
                    bruto = ws_v.cell(r_v, c_sku_v).value
                    if bruto not in (None, ''):
                        sku_final = _con_prefijo_h(' '.join(str(bruto).split()))
                if sku_final:
                    if sku_final in ctx['usados_sku']:
                        ctx['duplicadas'] += 1
                        continue
                    ctx['usados_sku'].add(sku_final)
                semilla = sku_final or f'{nombre}#{r_v}'
                _escribir_fila(ws_v, r_v, ws_n, est['fila'],
                               pares, cols_n, ctx, semilla)
                est['ultima'] = est['fila']
                est['fila'] += 1
                filas += 1
        info = {
            'filas': filas,
            'hoja': destino[0],
            'descartadas': descartadas,
            'siguiente': est['fila'],
        }
        info.update({k: ctx[k] - antes[k] for k in _CONTADORES})
        return info
    finally:
        wb_v.close()


def _convertir_planilla(ruta_origen: str,
                        destino: str,
                        ruta_plantilla: str,
                        categoria_usuario=None):
    """Convierte una planilla vieja al nuevo formato (archivo individual)."""
    wb_n = openpyxl.load_workbook(ruta_plantilla, data_only=False)
    try:
        hojas_n = _hojas_producto(wb_n)
        if not hojas_n:
            raise RuntimeError('La plantilla nueva no tiene hojas de productos.')
        ctx = _nuevo_ctx(hojas_n)
        info = _convertir_en(ruta_origen, wb_n, ctx, categoria_usuario)
        os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)
        wb_n.save(destino)
    finally:
        wb_n.close()
    res = dict(info)
    res['plantilla'] = os.path.basename(ruta_plantilla)
    return res


def _convertir_combinadas(pendientes, outdir: str, ruta_plantilla: str):
    """Convierte varias planillas viejas en UN solo archivo combinado.

    `pendientes` es una lista de tuplas (ruta, nombre). Devuelve una lista
    de resultados: primero el ok combinado y después los errores sueltos.
    """
    nombres = [n for _r, n in pendientes]
    wb_n = openpyxl.load_workbook(ruta_plantilla, data_only=False)
    try:
        hojas_n = _hojas_producto(wb_n)
        if not hojas_n:
            raise RuntimeError('La plantilla nueva no tiene hojas de productos.')
        ctx = _nuevo_ctx(hojas_n)
        detalles = []
        errores = []
        totales = dict(filas=0, sin_h=0, ean_nuevos=0,
                       titulos_ajustados=0, duplicadas=0)
        descartadas = []
        hojas_usadas = []
        for ruta, nombre in pendientes:
            try:
                info = _convertir_en(ruta, wb_n, ctx, None)
            except SinCategoria as e:
                errores.append({'ok': False, 'origen': nombre,
                                'mensaje': str(e)})
                continue
            except Exception as e:
                errores.append({'ok': False, 'origen': nombre,
                                'error': f'{type(e).__name__}: {e}'})
                continue
            detalles.append({'origen': nombre, 'filas': info['filas'],
                             'hoja': info['hoja'],
                             'duplicadas': info['duplicadas'], 'aviso': ''})
            for k in totales:
                totales[k] += info[k]
            for c in info['descartadas']:
                if c not in descartadas:
                    descartadas.append(c)
            if info['hoja'] not in hojas_usadas:
                hojas_usadas.append(info['hoja'])
        if not detalles:
            return errores
        archivo = 'planillas-combinadas-nuevo-formato.xlsx'
        os.makedirs(outdir, exist_ok=True)
        wb_n.save(os.path.join(outdir, archivo))
        combinado = {
            'ok': True,
            'archivo': archivo,
            'origen': ' + '.join(nombres),
            'planillas': len(detalles),
            'filas': totales['filas'],
            'hoja': ', '.join(hojas_usadas),
            'plantilla': os.path.basename(ruta_plantilla),
            'descartadas': descartadas,
            'sin_h': totales['sin_h'],
            'ean_nuevos': totales['ean_nuevos'],
            'titulos_ajustados': totales['titulos_ajustados'],
            'duplicadas': totales['duplicadas'],
            'siguiente': None,
            'detalle': detalles,
        }
        return [combinado] + errores
    finally:
        wb_n.close()


def _fuentes_conversion(outdir: str):
    """Fuentes del selector de conversión: salidas generadas (``salida``)
    primero y planillas antiguas subidas (``subida``) después."""
    outdir = outdir or S.SALIDA
    fuentes = []
    if os.path.isdir(outdir):
        for nombre in sorted(os.listdir(outdir)):
            if nombre.lower().endswith(S.EXTS) and not nombre.startswith('~$'):
                fuentes.append({'origen': 'salida', 'nombre': nombre})
    # PLANILLAS_ANTIGUAS es una ruta (no una clave de DIRS): se lista directo
    if os.path.isdir(S.PLANILLAS_ANTIGUAS):
        for nombre in sorted(os.listdir(S.PLANILLAS_ANTIGUAS)):
            if nombre.lower().endswith(S.EXTS) and not nombre.startswith('~$'):
                fuentes.append({'origen': 'subida', 'nombre': nombre})
    return fuentes


def _ruta_plantilla_actual() -> str:
    """Devuelve la ruta del archivo de plantilla actual guardada en datos/."""
    from .core import state as S
    if not os.path.isfile(S.PLANTILLA_ACTUAL):
        raise RuntimeError(
            'No hay plantilla cargada. Subí primero una plantilla nueva de Mercado Libre.'
        )
    return S.PLANTILLA_ACTUAL


def _guardar_plantilla_actual(file_storage):
    """Guarda la plantilla nueva de ML en la ruta fija PLANTILLA_ACTUAL,
    detecta todas sus hojas de producto y devuelve
    (nombre, hojas, categorías)."""
    # Guardar en la ruta fija que usa todo el sistema
    os.makedirs(os.path.dirname(S.PLANTILLA_ACTUAL), exist_ok=True)
    file_storage.save(S.PLANTILLA_ACTUAL)

    nombre_original = os.path.basename(file_storage.filename or 'plantilla.xlsx')

    # Abrir el workbook y detectar las hojas de productos y sus categorías
    wb = openpyxl.load_workbook(S.PLANTILLA_ACTUAL, data_only=True)
    try:
        hojas = _hojas_producto(wb)
    finally:
        wb.close()
    if not hojas:
        raise RuntimeError(
            'La plantilla no tiene hojas de productos de Mercado Libre.'
        )

    nombres = [h[0] for h in hojas]
    categorias = []
    for _s, _r, cat in hojas:
        if cat and cat not in categorias:
            categorias.append(cat)

    # Actualizar el state
    st = S.cargar()
    st['plantilla_actual'] = nombre_original
    st['plantilla_categorias'] = categorias   # lista de rutas completas
    S.guardar(st)

    return nombre_original, ', '.join(nombres), categorias