# -*- coding: utf-8 -*-
"""Estado persistente (catálogo de archivos y opciones) en JSON local.

Los archivos de entrada viven en ``datos/`` (el servidor es dueño de las
copias); el state guarda nombres de archivo, no rutas del usuario.
"""
import json
import os
import shutil

WEBAPP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIZ = os.path.dirname(WEBAPP)
SALIDA = os.path.join(RAIZ, 'salida')
STATE_PATH = os.path.join(WEBAPP, 'state.json')

# carpetas de archivos subidos
DATOS = os.path.join(RAIZ, 'datos')
DIRS = {
    'bases': os.path.join(DATOS, 'bases'),
    'complementos': os.path.join(DATOS, 'complementos'),
    'fotos': os.path.join(DATOS, 'fotos'),
    'plantillas': os.path.join(DATOS, 'plantillas'),
    # plantillas VACÍAS por categoría (las que se usan para publicar);
    # 'plantillas' queda como archivo de plantillas de EJEMPLO (rellenas)
    'plantillas-categorias': os.path.join(DATOS, 'plantillas-categorias'),
}
#: orden en que se busca una plantilla: primero la de categoría
ORDEN_PLANTILLAS = ('plantillas-categorias', 'plantillas')
EXTS = ('.xlsx', '.xlsm')

# plantilla NUEVA de Mercado Libre (base para convertir planillas viejas) y
# carpeta de planillas antiguas que el usuario sube para convertirlas
PLANTILLAS_NUEVAS = os.path.join(DATOS, 'plantillas-nuevas')
PLANILLAS_ANTIGUAS = os.path.join(DATOS, 'planillas-antiguas')
# plantilla nueva que la persona sube AL MOMENTO de convertir (la descargada
# de Mercado Libre para la cuenta nueva); se pisa en cada subida
PLANTILLA_ACTUAL = os.path.join(DATOS, 'plantilla-actual.xlsx')

DEFAULT = {
    'bases': [],          # [{nombre, archivo, activa}] catálogo de productos
    'complementos': [],   # nombres de archivo en datos/complementos
    'fotos': '',          # nombre de archivo en datos/fotos
    'plantilla': '',      # nombre de archivo en datos/plantillas
    'outdir': SALIDA,
    'marketplace': '',    # '' = autodetectar por plantilla
    'categoria': '',      # categoría a rellenar (última elegida)
    'prefijo': '',
    'limite': '',
    'modelos': '',
    'usar_ml': True,
    'max_ml': '30',
    'usar_ia': False,
    'predecir_cat': False,   # predecir categorías ML que falten (internet)
    'cuenta': '',          # cuenta destino (Ripholia, Crazy Family, …)
    'prefijo_sku': '',     # prefijo a anteponer al SKU de salida (ej. L -> L-RIP-...)
    'color_defecto': '',   # color a usar si un producto queda sin color
    'ultima_salida': '',
    'plantilla_actual': '',   # nombre original de la plantilla nueva subida
    'plantilla_categorias': [],  # categorías (hojas) de esa plantilla nueva
}


def cargar():
    st = dict(DEFAULT)
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, encoding='utf-8') as fh:
                st.update(json.load(fh))
        except Exception:
            pass
    # Si la carpeta se movió, salida vuelve a la predeterminada
    if not st.get('outdir') or not os.path.isdir(os.path.dirname(st['outdir'] or '')):
        st['outdir'] = SALIDA
    if _migrar(st):
        guardar(st)   # persiste la migración una sola vez
    return st


def guardar(st):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, 'w', encoding='utf-8') as fh:
        json.dump(st, fh, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------------------
# Migración: rutas absolutas (formato viejo) -> archivos dentro de datos/
# ---------------------------------------------------------------------------

def _migrar(st):
    """Convierte rutas de usuario en archivos copiados a datos/.

    Idempotente: si el formato ya es el nuevo, no hace nada.
    Devuelve True si cambió algo (para persistir).
    """
    # bases: ['C:\\…\\a.xlsx', …] -> [{nombre, archivo, activa}, …]
    bases = st.get('bases') or []
    nuevas = []
    migrar_algo = False
    for b in bases:
        if isinstance(b, str):
            migrar_algo = True
            archivo = _copiar_a(b, 'bases')
            if archivo:
                nombre = os.path.splitext(os.path.basename(b))[0]
                nuevas.append({'nombre': nombre, 'archivo': archivo,
                               'activa': True})
            # si el archivo ya no existe, se descarta
        elif isinstance(b, dict) and b.get('archivo'):
            nuevas.append(b)
    if migrar_algo:
        st['bases'] = nuevas

    # complementos: rutas -> nombres en datos/complementos
    comps = st.get('complementos') or []
    if comps and isinstance(comps[0], str) and ('\\' in comps[0] or '/' in comps[0]):
        nuevos = []
        for c in comps:
            archivo = _copiar_a(c, 'complementos')
            if archivo:
                nuevos.append(archivo)
        st['complementos'] = nuevos
        migrar_algo = True

    # fotos / plantilla: ruta -> nombre en su carpeta
    for campo, sub in (('fotos', 'fotos'), ('plantilla', 'plantillas')):
        v = st.get(campo) or ''
        if v and ('\\' in v or '/' in v):
            st[campo] = _copiar_a(v, sub) or ''
            migrar_algo = True
    return migrar_algo


def _copiar_a(ruta_origen, sub):
    """Copia un archivo a datos/<sub>/ y devuelve el nombre; '' si falla."""
    if not ruta_origen or not os.path.isfile(ruta_origen):
        return ''
    ext = os.path.splitext(ruta_origen)[1].lower()
    if ext not in EXTS:
        return ''
    destino_dir = DIRS[sub]
    os.makedirs(destino_dir, exist_ok=True)
    nombre = os.path.basename(ruta_origen)
    destino = os.path.join(destino_dir, nombre)
    try:
        if os.path.abspath(ruta_origen) != os.path.abspath(destino):
            shutil.copy2(ruta_origen, destino)
    except Exception:
        return ''
    return nombre


# ---------------------------------------------------------------------------
# Resolución de nombres de archivo -> rutas del servidor
# ---------------------------------------------------------------------------

def ruta(sub, archivo):
    """Ruta completa de un archivo dentro de datos/<sub>/ ('' si no hay)."""
    if not archivo:
        return ''
    return os.path.join(DIRS[sub], os.path.basename(str(archivo)))


def ruta_plantilla(archivo):
    """Ruta de una plantilla: primero en plantillas-categorias/, luego en
    plantillas/ (ejemplos). Si no existe en ninguna, la de categoría."""
    if not archivo:
        return ''
    nombre = os.path.basename(str(archivo))
    for sub in ORDEN_PLANTILLAS:
        p = os.path.join(DIRS[sub], nombre)
        if os.path.isfile(p):
            return p
    return os.path.join(DIRS[ORDEN_PLANTILLAS[0]], nombre)


def plantillas_disponibles():
    """Nombres de las plantillas VACÍAS por categoría (lo que se elige)."""
    return archivos_en(ORDEN_PLANTILLAS[0])


def bases_activas(st=None):
    """Rutas completas de las bases activas que existen en disco.

    Las que faltan se ignoran (el caller puede avisar con ``bases_faltantes``).
    """
    st = st or cargar()
    rutas = []
    for b in st.get('bases') or []:
        if isinstance(b, dict) and b.get('activa', True) and b.get('archivo'):
            p = ruta('bases', b['archivo'])
            if os.path.isfile(p):
                rutas.append(p)
    return rutas


def bases_faltantes(st=None):
    """Entradas activas cuyo archivo ya no existe en datos/bases/."""
    st = st or cargar()
    faltan = []
    for b in st.get('bases') or []:
        if isinstance(b, dict) and b.get('activa', True) and b.get('archivo'):
            if not os.path.isfile(ruta('bases', b['archivo'])):
                faltan.append(b.get('nombre') or b['archivo'])
    return faltan


def archivos_en(sub):
    """Nombres .xlsx/.xlsm de datos/<sub>/ (para 'ya subidos')."""
    d = DIRS.get(sub, '')
    if not os.path.isdir(d):
        return []
    return sorted(n for n in os.listdir(d)
                  if n.lower().endswith(EXTS) and not n.startswith('~$'))
