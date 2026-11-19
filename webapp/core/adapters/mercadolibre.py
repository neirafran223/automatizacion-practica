# -*- coding: utf-8 -*-
"""Adaptador de Mercado Libre: envuelve RellenarPlanilla."""
import difflib
import os
import re

from .base import Adaptador
from .. import loader
from .. import state as S


class AdaptadorML(Adaptador):
    nombre = 'mercadolibre'
    etiqueta = 'Mercado Libre'

    # ---------- detección ----------
    @classmethod
    def detectar_plantilla(cls, path):
        if not path or not os.path.isfile(path):
            return False
        import openpyxl
        rp = loader.importar('rellenar_planilla')
        # modo normal: en read_only ws.max_row puede ser None y
        # detectar_hoja_productos truena comparándolo con 5
        wb = openpyxl.load_workbook(path, data_only=True)
        try:
            nombre, *_ = rp.detectar_hoja_productos(wb)
            return nombre is not None
        finally:
            wb.close()

    # ---------- analizar ----------
    @classmethod
    def analizar(cls, cfg, log=lambda m: None):
        rp = loader.importar('rellenar_planilla')
        bases = [p for p in (cfg.get('bases') or []) if p]
        if not bases:
            raise RuntimeError('Agregá al menos un Excel base.')
        prefijo = (cfg.get('prefijo') or '').strip() or None
        productos = rp.cargar_bases(bases, prefijo=prefijo, log=log)
        complementos = [rp.cargar_complemento(c)
                        for c in (cfg.get('complementos') or []) if c]
        fotos = rp.cargar_fotos(cfg['fotos']) if cfg.get('fotos') else {}

        # predicción opcional de categorías ML para modelos sin categoría
        if cfg.get('predecir_cat'):
            cls._predecir_categorias(productos, complementos, log)

        # tabla_categorias es la que setea prod["categoria"] (obligatorio
        # para que rellenar() pueda filtrar por la categoría elegida)
        filas = rp.tabla_categorias(productos, complementos)
        categorias = [{'ruta': c, 'modelos': n, 'variantes': nv}
                      for c, n, nv in filas]
        return {
            'categorias': categorias,
            'total_modelos': len(productos),
            'total_complementos': len(complementos),
            'tiene_fotos': bool(fotos),
            'prefijos': _detectar_prefijos(productos),
            'marketplace': cls.nombre,
        }

    @classmethod
    def _predecir_categorias(cls, productos, complementos, log):
        """Completa prod['categoria_ml'] (prioridad máxima en resolver) para
        modelos que no tienen categoría en ningún archivo."""
        mc = loader.importar('ml_categories')
        rp = loader.importar('rellenar_planilla')
        faltan = [(mb, p) for mb, p in productos.items()
                  if not rp.resolver(mb, p, complementos, 'categoria')]
        if not faltan:
            return
        log('Prediciendo categorías de ML para %d modelos…' % len(faltan))
        cache = {}
        for i, (mb, prod) in enumerate(faltan, 1):
            titulo = prod.get('titulo') or ''
            clave = titulo[:60].lower()
            if clave in cache:
                ruta = cache[clave]
            else:
                _, cat_id, _ = mc.predict(titulo)
                ruta = mc.category_path(cat_id) if cat_id else ''
                cache[clave] = ruta
            if ruta:
                prod['categoria_ml'] = ruta
            if i % 25 == 0:
                log('  · %d/%d categorías predichas' % (i, len(faltan)))

    # ---------- generar ----------
    @classmethod
    def generar(cls, cfg, prog):
        rp = loader.importar('rellenar_planilla')

        # 1) cargar insumos
        prog.fase('Cargando archivos')
        prog.pct(5)
        for n in cfg.get('avisos_bases') or []:
            prog.log('⚠ Base omitida (no encontrada): %s' % n)
        bases = [p for p in (cfg.get('bases') or []) if p]
        prefijo = (cfg.get('prefijo') or '').strip() or None
        log = prog.log
        log('Cargando %d base(s)…' % len(bases))
        productos = rp.cargar_bases(bases, prefijo=prefijo, log=log)
        complementos = []
        for c in (cfg.get('complementos') or []):
            if c:
                log('Complemento: %s' % os.path.basename(c))
                complementos.append(rp.cargar_complemento(c))
        fotos = rp.cargar_fotos(cfg['fotos']) if cfg.get('fotos') else {}
        if fotos:
            log('Fotos URL: %d modelos' % len(fotos))
        if cfg.get('predecir_cat'):
            cls._predecir_categorias(productos, complementos, log)
        log('Productos cargados: %d modelos' % len(productos))
        # Filas de base sin TALLA pierden su COLOR (el loader las saltea):
        # RIP-400-2 (cofia) trae 'Azul Rey' en COLOR COMERCIAL pero TALLA
        # vacía. Releen el base SOLO para modelos con variantes sin color.
        n_color = _completar_color_ml(productos, bases, log)
        if prog.cancelado():
            raise RuntimeError('Cancelado por el usuario.')

        # 2) categorizar: setea prod["categoria"] (obligatorio antes de rellenar)
        prog.fase('Categorizando productos')
        prog.pct(15)
        filas = rp.tabla_categorias(productos, complementos)
        log('Categorías encontradas: %d' % len(filas))
        if prog.cancelado():
            raise RuntimeError('Cancelado por el usuario.')

        # 3) ruta de salida
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

        usar_ml = bool(cfg.get('usar_ml'))
        max_ml = int(cfg.get('max_ml') or 0)

        # 3.5) filas que la plantilla YA trae (si son datos rellenos): se usan
        # para heredar campos que ninguna fuente trae (diseño de tela, color,
        # composición, EAN real) cuando la misma plantilla se reutiliza.
        previas = _leer_plantilla_previa(cfg['plantilla'])

        # 4) rellenar (la función real de RellenarPlanilla)
        stats = rp.rellenar(
            cfg['plantilla'], path_salida, productos, complementos, fotos,
            categoria_objetivo=(cfg.get('categoria') or '').strip() or None,
            log=prog.log,
            limite_modelos=cfg.get('limite') or None,
            modelo_especifico=(cfg.get('modelos') or '').strip() or None,
            usar_ml_publico=usar_ml,
            max_ml=max_ml if usar_ml else 0,
            cancel=prog.cancelado,
        )

        # 5) post-proceso: herencia de la plantilla, diseno, composición
        # desde el texto, color por defecto y prefijo de cuenta en el SKU.
        prog.fase('Completando planilla')
        prog.pct(90)
        post = _post_procesar_salida(path_salida, previas, cfg, log)
        if post.get('heredadas'):
            log('Valores heredados de la plantilla: %d celda(s)'
                % post['heredadas'])
        if post.get('diseno'):
            log('Diseño copiado desde Diseño de la tela: %d fila(s)'
                % post['diseno'])
        if post.get('composicion'):
            log('Composición deducida del título/descripción: %d fila(s)'
                % post['composicion'])
        if post.get('color'):
            log('Color por defecto "%s" aplicado: %d fila(s)'
                % (cfg.get('color_defecto'), post['color']))
        if post.get('color_ajustadas'):
            log('Color ajustado al más parecido de la lista: %d fila(s)'
                % post['color_ajustadas'])
        if post.get('color_sin_lista'):
            log('⚠ Colores sin equivalente en la lista (se dejaron tal cual): '
                + ', '.join(post['color_sin_lista']))
        if post.get('fotos'):
            log('Fotos separadas por coma (sin espacios): %d fila(s)'
                % post['fotos'])
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
            'filas': stats.get('filas', 0),
            'cuenta': cuenta,
            'prefijos_sku': n_pref,
            'color_ml': n_color,
            'heredadas': post.get('heredadas', 0),
            'color_ajustadas': post.get('color_ajustadas', 0),
            'color_sin_lista': post.get('color_sin_lista', []),
            'marketplace': cls.nombre,
            'sin_fotos': stats.get('sin_fotos', []),
            'sin_precio': stats.get('sin_precio', []),
            'sin_guia': stats.get('sin_guia', []),
            'faltantes': stats.get('faltantes', {}),
            'sku_repetidos': stats.get('sku_repetidos', 0),
        }
        st = S.cargar()
        st['ultima_salida'] = path_salida
        S.guardar(st)
        return resumen


# ---------- funciones auxiliares del módulo ----------

def _detectar_prefijos(productos):
    """Segmentos alfabéticos antes del primer número ('RIP-AMAPOLA-1' → RIP,
    RIP-AMAPOLA; 'H-A-107' crudo → H, H-A). El filtro de RellenarPlanilla
    hace startswith(prefijo + '-'), así que todos sirven."""
    prefijos = set()
    for mb, prod in productos.items():
        crudo = str(prod.get('modelo') or mb or '')
        acum = []
        for seg in crudo.upper().replace(' ', '').split('-'):
            if not seg or seg[0].isdigit():
                break
            acum.append(seg)
            prefijos.add('-'.join(acum))
    return sorted(prefijos)


def _completar_color_ml(productos, bases, log):
    """Completa prod['color_ml'] para modelos con variantes sin color.

    El loader de RellenarPlanilla saltea las filas de base sin TALLA, y en
    esas filas modelo (p.ej. la cofia RIP-400-2) suele estar el COLOR
    COMERCIAL. Relee el base SOLO para los modelos afectados y, si hay un
    único color candidato, lo usa como color del producto.
    """
    necesitan = {mb for mb, p in productos.items()
                 if p.get('color_ml') in (None, '')
                 and any(v.get('color') in (None, '') for v in p['variantes'])}
    if not necesitan:
        return 0
    import openpyxl
    rp = loader.importar('rellenar_planilla')
    encontrados = {}
    for path in bases:
        if not path or not os.path.isfile(path):
            continue
        try:
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        except Exception:
            continue
        try:
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                filas = ws.iter_rows(values_only=True)
                idx = None
                for n, fila in enumerate(filas):
                    hn = [rp.norm(c) if c is not None else None for c in fila]
                    if idx is None:
                        if (any(h in hn for h in rp.COLS_BASE['modelo'])
                                and any(h in hn for h in rp.COLS_BASE['color'])):
                            idx = rp._buscar_columnas(hn, rp.COLS_BASE)
                        if n > 8:
                            break
                        continue
                    im, ic = idx.get('modelo'), idx.get('color')
                    if im is None or im >= len(fila) or not fila[im]:
                        continue
                    mb = rp.modelo_base(str(fila[im]))
                    if mb not in necesitan or mb in encontrados:
                        continue
                    v = fila[ic] if ic is not None and ic < len(fila) else None
                    if v in (None, ''):
                        ia = idx.get('color_alt')
                        v = fila[ia] if ia is not None and ia < len(fila) else None
                    if v not in (None, ''):
                        encontrados.setdefault(mb, set()).add(str(v).strip())
        finally:
            wb.close()
    n = 0
    multi = 0
    for mb, vals in encontrados.items():
        if len(vals) == 1:
            productos[mb]['color_ml'] = next(iter(vals))
            n += 1
        else:
            multi += 1
    if n:
        log('  · Color completado desde el base: %d modelo(s)' % n)
    if multi:
        log('  ⚠ %d modelo(s) con varios colores en el base: '
            'completar a mano o elegir color por defecto' % multi)
    return n


CAMPOS_HEREDADOS = ('diseno', 'diseno_tela', 'color', 'composicion', 'ean')


def _leer_plantilla_previa(path):
    """Lee las filas que la plantilla YA trae (si son datos rellenos) para
    heredar después campos que ninguna fuente de datos trae:
    diseño de tela, color, composición o EAN real. Devuelve
    {(MODELO, TALLA): {campo: valor}}; con plantilla en blanco queda vacío."""
    previas = {}
    if not path or not os.path.isfile(path):
        return previas
    import openpyxl
    rp = loader.importar('rellenar_planilla')
    try:
        wb = openpyxl.load_workbook(path, data_only=True)
    except Exception:
        return previas
    try:
        nombre, fh, fi, _ = rp.detectar_hoja_productos(wb)
        if not nombre:
            return previas
        ws = wb[nombre]
        idx = rp.mapear_columnas(ws, fh)
        if 'modelo' not in idx or 'talla' not in idx:
            return previas
        campos = [c for c in CAMPOS_HEREDADOS if c in idx]
        for r in range(fi, ws.max_row + 1):
            modelo = ws.cell(row=r, column=idx['modelo'] + 1).value
            talla = ws.cell(row=r, column=idx['talla'] + 1).value
            if not modelo or not talla:
                continue
            key = (str(modelo).strip().upper(), str(talla).strip().upper())
            d = previas.setdefault(key, {})
            for c in campos:
                if d.get(c) not in (None, ''):
                    continue
                v = ws.cell(row=r, column=idx[c] + 1).value
                if isinstance(v, float) and v.is_integer():
                    v = int(v)
                if isinstance(v, str):
                    v = v.strip()
                if v not in (None, ''):
                    d[c] = v
    finally:
        wb.close()
    return previas


# ---------------------------------------------------------------------------
# Colores: la plantilla de ML sólo admite los de su lista (data validation de
# la columna Color, que apunta a la hoja oculta 'extra info'). Si el color de
# la base no está, se usa el más parecido de esa lista.
# ---------------------------------------------------------------------------

# Similitud mínima para aceptar un candidato: con contención basta menos
# (el color está "dentro" de la opción o viceversa), sin ella hace falta que
# los textos se parezcan de verdad ("Girs"→"Gris" pasa; "Navidad"→"Lavanda"
# no, porque sería peor que dejar el color original).
_COLOR_MIN_CONT = 0.45
_COLOR_MIN_RATIO = 0.70
_COLOR_BONUS_CONT = 0.35

_RE_CELDA = re.compile(r"^([A-Z]+)(\d+)$")
_RE_REF = re.compile(
    r"""^'?([^'!]+)'?!\$?([A-Z]+)\$?(\d+)(?::\$?([A-Z]+)\$?(\d+))?$""")
_CACHE_COLORES = {}


def _dv_cubre(sqref, colL, fila):
    """¿La validación 'list' aplica a la celda columna `colL`, fila `fila`?"""
    for tok in str(sqref or '').split():
        partes = tok.split(':')
        a = _RE_CELDA.match(partes[0])
        if not a:
            continue
        b = _RE_CELDA.match(partes[-1]) or a
        c1, r1 = a.group(1), int(a.group(2))
        c2, r2 = b.group(1), int(b.group(2))
        if c1 == c2 == colL and min(r1, r2) <= fila <= max(r1, r2):
            return True
    return False


def _rango_a_valores(wb, formula):
    """`'extra info'!$A$4:$AZ$4` o `"Negro,Azul"` → lista de valores."""
    from openpyxl.utils import column_index_from_string as a_col
    f = str(formula or '').strip()
    if not f:
        return []
    if f.startswith('"') and f.endswith('"'):          # lista literal
        return [v.strip() for v in f.strip('"').split(',') if v.strip()]
    m = _RE_REF.match(f)
    if not m or m.group(1) not in wb.sheetnames:
        return []
    ws = wb[m.group(1)]
    c1, r1 = m.group(2), int(m.group(3))
    c2, r2 = m.group(4) or c1, int(m.group(5) or m.group(3))
    ci1, ci2 = a_col(c1), a_col(c2)
    out = []
    for rr in range(min(r1, r2), max(r1, r2) + 1):
        for cc in range(min(ci1, ci2), max(ci1, ci2) + 1):
            v = ws.cell(row=rr, column=cc).value
            if v in (None, ''):
                continue
            s = str(v).strip()
            # "Escribe o elige un valor": texto de ayuda, no un color
            if s and not re.search(r"\b(escribe|elige)\b", s, re.I):
                out.append(s)
    return out


def leer_colores_plantilla(path):
    """Colores que admite la plantilla, o None si no tiene lista."""
    if not path or not os.path.isfile(path):
        return None
    # la clave incluye mtime/tamaño: si el usuario sube otra plantilla con el
    # mismo nombre, la lista se vuelve a leer
    try:
        st = os.stat(path)
    except OSError:
        return None
    clave = (path, st.st_mtime, st.st_size)
    if clave in _CACHE_COLORES:
        return _CACHE_COLORES[clave]
    import openpyxl
    rp = loader.importar('rellenar_planilla')
    valores = None
    try:
        wb = openpyxl.load_workbook(path)
    except Exception:
        return None
    try:
        nombre, fh, fi, _ = rp.detectar_hoja_productos(wb)
        ws = wb[nombre] if nombre else None
        idx = rp.mapear_columnas(ws, fh) if ws is not None else {}
        if ws is not None and 'color' in idx:
            colL = openpyxl.utils.get_column_letter(idx['color'] + 1)
            for dv in ws.data_validations.dataValidation:
                if dv.type == 'list' and _dv_cubre(dv.sqref, colL, fi):
                    v = _rango_a_valores(wb, dv.formula1)
                    if v:
                        valores = v
                    break
    finally:
        wb.close()
    _CACHE_COLORES[clave] = valores
    return valores


def _variantes_color(color, rp):
    """Textos con los que comparar un color: el de la base, su equivalente en
    MAPA_COLORES y cada palabra traducida ('Morado Oscuro' → 'Violeta',
    'Azul Rey' → 'Azul')."""
    out, vistos = [], set()

    def add(txt):
        if not txt:
            return
        s = str(txt).strip()
        n = rp.norm(s) if s else ''
        if s and n and n not in vistos:
            vistos.add(n)
            out.append(s)

    add(color)
    add(rp.mapear_color(color))
    palabras = rp.norm(color).split()
    for p in palabras:
        add(rp.MAPA_COLORES.get(p))
    for i in range(len(palabras) - 1):
        add(rp.MAPA_COLORES.get(' '.join(palabras[i:i + 2])))
    return out


def _contencion(a, b):
    """¿La parte corta aparece como palabra(s) completas de la larga?

    Evita aciertos accidentales: 'AR' sí está dentro de 'MARRON', pero no
    como palabra, así que no cuenta."""
    largo, corto = (a, b) if len(a) >= len(b) else (b, a)
    if not corto:
        return False
    return re.search(r"(?<![0-9A-Z])" + re.escape(corto) + r"(?![0-9A-Z])",
                     largo) is not None


def color_mas_parecido(color, opciones):
    """Valor de `opciones` más parecido a `color`.

    Devuelve None si no hay candidato razonable: en ese caso se conserva el
    color original en vez de inventar uno que no corresponda."""
    if not color or not opciones:
        return None
    rp = loader.importar('rellenar_planilla')
    variantes = _variantes_color(color, rp)
    if not variantes:
        return None
    # 1) alguna variante coincide exacto con un valor de la lista
    for v in variantes:
        nv = rp.norm(v)
        for o in opciones:
            if rp.norm(o) == nv:
                return o
    # 2) el más parecido (con bonus si uno contiene al otro)
    mejor, puntaje, con_cont = None, 0.0, False
    for o in opciones:
        no = rp.norm(o)
        for v in variantes:
            nv = rp.norm(v)
            r = difflib.SequenceMatcher(None, nv, no).ratio()
            cont = _contencion(nv, no)
            if cont:
                r += _COLOR_BONUS_CONT
            if r > puntaje:
                mejor, puntaje, con_cont = o, r, cont
    if mejor is None:
        return None
    minimo = _COLOR_MIN_CONT if con_cont else _COLOR_MIN_RATIO
    return mejor if puntaje >= minimo else None


_RE_COMP = re.compile(r"\d{1,3}\s*%\s*[A-Za-zÁÉÍÓÚáéíóúñÑ]{3,}(?:[ /-]+[A-Za-zÁÉÍÓÚáéíóúñÑ]{2,})*")


def _post_procesar_salida(path, previas, cfg, log):
    """Única pasada final sobre la planilla generada (un solo guardar):

    1. hereda de la plantilla rellenada los campos vacíos (diseño, color,
       composición, EAN) para el mismo MODELO+TALLA;
    2. copia 'Diseño de la tela' a la columna variante 'Diseño' si existe;
    3. si 'Composición' sigue vacía, la deduce del título/descripción;
    4. aplica el color por defecto si el producto quedó sin color;
    5. antepone el prefijo de cuenta al SKU;
    6. si el color no está en la lista de la plantilla, usa el más parecido;
    7. junta las fotos con coma y sin espacios (lo que espera ML).
    """
    rp = loader.importar('rellenar_planilla')
    import openpyxl
    wb = openpyxl.load_workbook(path)
    nombre, fh, fi, _ = rp.detectar_hoja_productos(wb)
    if not nombre:
        wb.close()
        raise RuntimeError('No detecté la hoja de productos en la salida.')
    ws = wb[nombre]
    idx = rp.mapear_columnas(ws, fh)
    res = {'heredadas': 0, 'diseno': 0, 'composicion': 0, 'color': 0,
           'prefijo': 0, 'color_ajustadas': 0, 'color_sin_lista': [],
           'fotos': 0}
    color_def = str(cfg.get('color_defecto') or '').strip()
    prefijo = str(cfg.get('prefijo_sku') or '').strip().upper().rstrip('-')

    # la lista de colores válidos vive en la PLANTILLA, no en la salida
    opciones = leer_colores_plantilla(cfg.get('plantilla'))
    permitidos = {rp.norm(o) for o in opciones} if opciones else None

    def cel(r, c):
        return ws.cell(row=r, column=idx[c] + 1)

    for r in range(fi, ws.max_row + 1):
        if 'sku' in idx and not cel(r, 'sku').value:
            continue
        modelo = cel(r, 'modelo').value if 'modelo' in idx else None
        talla = cel(r, 'talla').value if 'talla' in idx else None
        prev = previas.get((str(modelo or '').strip().upper(),
                            str(talla or '').strip().upper()))

        # 1) herencia desde la plantilla rellenada
        if prev:
            for c in CAMPOS_HEREDADOS:
                if c not in idx or cel(r, c).value not in (None, ''):
                    continue
                v = prev.get(c)
                if v not in (None, ''):
                    cel(r, c).value = v
                    res['heredadas'] += 1

        # 2) diseno variante <- diseno_tela
        if ('diseno' in idx and 'diseno_tela' in idx
                and cel(r, 'diseno').value in (None, '')
                and cel(r, 'diseno_tela').value not in (None, '')):
            cel(r, 'diseno').value = cel(r, 'diseno_tela').value
            res['diseno'] += 1

        # 3) composicion desde el titulo/descripcion
        if 'composicion' in idx and cel(r, 'composicion').value in (None, ''):
            texto = ' '.join(str(cel(r, c).value or '')
                             for c in ('titulo', 'descripcion') if c in idx)
            m = _RE_COMP.search(texto)
            if m:
                cel(r, 'composicion').value = m.group(0).strip()
                res['composicion'] += 1

        # 4) color por defecto
        if (color_def and 'color' in idx
                and cel(r, 'color').value in (None, '')):
            cel(r, 'color').value = color_def
            res['color'] += 1

        # 5) prefijo de cuenta en el SKU
        if prefijo and 'sku' in idx:
            sku = str(cel(r, 'sku').value or '')
            if sku and not sku.upper().startswith(prefijo + '-'):
                cel(r, 'sku').value = prefijo + '-' + sku
                res['prefijo'] += 1

        # 6) el color debe pertenecer a la lista de la plantilla
        if permitidos and 'color' in idx:
            v = cel(r, 'color').value
            if v not in (None, '') and rp.norm(str(v)) not in permitidos:
                nuevo = color_mas_parecido(str(v), opciones)
                if nuevo:
                    cel(r, 'color').value = nuevo
                    res['color_ajustadas'] += 1
                elif str(v).strip() not in res['color_sin_lista']:
                    res['color_sin_lista'].append(str(v).strip())

        # 7) fotos: "url1 , url2" -> "url1,url2" (ML no quiere espacios)
        if 'fotos' in idx:
            f = cel(r, 'fotos').value
            if isinstance(f, str) and ',' in f:
                limpio = ','.join(p.strip() for p in f.split(',') if p.strip())
                if limpio != f:
                    cel(r, 'fotos').value = limpio
                    res['fotos'] += 1

    wb.save(path)
    wb.close()
    return res
