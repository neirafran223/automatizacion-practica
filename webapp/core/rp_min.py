# -*- coding: utf-8 -*-
"""Subconjunto minimo de RellenarPlanilla embebido en la webapp.

Copia literal de las funciones de ``rellenar_planilla.py`` que necesita la
CONVERSION de planillas viejas (y la edicion de salidas), para que
``PlanillasML-Web`` funcione sola sin la carpeta RellenarPlanilla.

Si RellenarPlanilla esta al lado, ``webapp.core.loader`` sigue usando el
módulo original; este archivo es solo el respaldo. Cualquier otra funcion
(p. ej. ``cargar_bases``, ``rellenar``) levanta un error claro: esas
pertenecen al flujo de generacion y si requieren la carpeta completa.
"""

import re
import unicodedata


# ---------------------------------------------------------------------------
# Normalizacion de textos
# ---------------------------------------------------------------------------

def quitar_acentos(texto):
    if texto is None:
        return ""
    texto = str(texto)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto


def norm(texto):
    """Normaliza un texto: sin acentos, mayusculas, espacios simples."""
    t = quitar_acentos(texto).upper()
    t = re.sub(r"\s+", " ", t).strip()
    return t


# ---------------------------------------------------------------------------
# Busqueda de columnas por encabezados
# ---------------------------------------------------------------------------

def _buscar_columnas(headers_norm, esquema):
    """Devuelve campo->indice de columna a partir de los headers normalizados.

    El orden de los sinonimos es jerarquico: el primero de la lista tiene
    prioridad (ej: 'CATEGORIA ML' gana sobre 'CATEGORIA' si ambas existen).
    """
    idx = {}
    # 1) coincidencia EXACTA (por sinonimo, en orden de prioridad)
    for campo, sinonomimos in esquema.items():
        for s in sinonomimos:
            for i, h in enumerate(headers_norm):
                if h is not None and h == s:
                    idx[campo] = i
                    break
            if campo in idx:
                break
    # 2) busqueda por CONTIENE para las que falten (tambien por sinonimo)
    for campo, sinonomimos in esquema.items():
        if campo in idx:
            continue
        for s in sinonomimos:
            for i, h in enumerate(headers_norm):
                if h is not None and s and s in h:
                    idx[campo] = i
                    break
            if campo in idx:
                break
    return idx


# ---------------------------------------------------------------------------
# Mapeo de columnas de la plantilla ML
# ---------------------------------------------------------------------------

COLS_PLANTILLA = {
    "titulo": ["TITULO"],
    "condicion": ["CONDICION"],
    "color": ["VARIA POR: NOMBRE COMERCIAL DEL COLOR"],
    "diseno": ["VARIA POR: DISENO DE LA TELA"],
    "talla": ["TALLA"],
    "marca": ["MARCA"],
    # El fabricante se llena con la misma marca canonica (Lady Genny/Ripholia...)
    "fabricante": ["FABRICANTE"],
    "genero": ["GENERO"],
    "guia": ["CODIGO DE LA GUIA"],
    "fotos": ["FOTOS"],
    "ean": ["CODIGO UNIVERSAL DE PRODUCTO"],
    "sku": ["SKU"],
    "stock": ["STOCK"],
    "precio": ["PRECIO"],
    "moneda": ["MONEDA"],
    "descripcion": ["DESCRIPCION"],
    "ancho": ["ANCHO (CM)", "ANCHO (CM.)"],
    "alto": ["ALTO (CM)", "ALTO (CM.)"],
    "profundidad": ["PROFUNDIDAD (CM)", "PROFUNDIDAD (CM.)"],
    "peso": ["PESO FISICO (KG)"],
    "tipo_publicacion": ["TIPO DE PUBLICACION"],
    "forma_envio": ["FORMA DE ENVIO"],
    "costo_envio": ["COSTO DE ENVIO"],
    "retiro": ["RETIRO EN PERSONA"],
    "tipo_garantia": ["TIPO DE GARANTIA"],
    "tiempo_garantia": ["TIEMPO DE GARANTIA"],
    "unidad_garantia": ["UNIDAD DE TIEMPO DE GARANTIA"],
    "modelo": ["MODELO"],
    "composicion": ["COMPOSICION"],
    "material": ["MATERIAL PRINCIPAL"],
    # Atributos obligatorios de ciertas categorias (Sostenes, Poleras,
    # Calcetines, Pijamas...). El dato sale del base/complemento, de las reglas
    # de la tienda o de una publicacion publica de Mercado Libre (por modelo).
    "tipo_corpino": ["TIPO DE CORPIÑO", "TIPO DE CORPINO"],
    "relleno": ["RELLENO", "CON RELLENO"],
    "tipo_prenda": ["TIPO DE PRENDA"],
    "temporada": ["TEMPORADA", "TEMPORADA DE LANZAMIENTO"],
    "tipo_medias": ["TIPO DE MEDIAS"],
    "tipo_largo": ["TIPO DE LARGO"],
    "presentacion": ["PRESENTACION"],
    "tamano_colchon": ["TAMAÑO DEL COLCHÓN", "TAMANO DEL COLCHON"],
    "tipo_catalogo": ["TIPO DE CATALOGO"],
    "tipo_alimentacion": ["TIPO DE ALIMENTACION"],
    "diseno_tela": ["DISEÑO DE LA TELA", "DISENO DE LA TELA"],
    "resumen_errores": ["RESUMEN DE ERRORES"],
}


def detectar_hoja_productos(wb):
    """
    Detecta la hoja de productos de la plantilla: la que tiene una fila de
    encabezados con 'Titulo...' y 'SKU'. Devuelve (hoja, fila_hdr, fila_datos).
    """
    for s in wb.sheetnames:
        ws = wb[s]
        if ws.max_row < 5:
            continue
        for r in range(1, 8):
            valores = [norm(ws.cell(row=r, column=c).value)
                       for c in range(1, min(ws.max_column, 40) + 1)]
            if any(v and v.startswith("TITULO") for v in valores) and "SKU" in valores:
                # Categoria de la planilla: normalmente A1 trae el arbol completo
                # ("Vestuario y Calzado > ... > Pijamas") y A2 el nombre corto.
                # Se prefiere la ruta completa para poder comparar con la categoria
                # elegida y avisar si la plantilla es de otra categoria.
                candidatos = []
                for rr in (r - 2, r - 1):
                    if rr < 1:
                        continue
                    v = ws.cell(row=rr, column=1).value
                    if not v or str(v).startswith("Título"):
                        continue
                    texto = str(v).strip()
                    if texto and len(texto) < 300:
                        candidatos.append(texto)
                cat = next((c for c in candidatos if ">" in c), None)
                if cat is None and candidatos:
                    cat = candidatos[0]
                return s, r, r + 5, cat
    return None, None, None, None


def mapear_columnas(ws, fila_hdr):
    hn = []
    for c in range(1, ws.max_column + 1):
        v = ws.cell(row=fila_hdr, column=c).value
        hn.append(norm(v) if v is not None else None)
    return _buscar_columnas(hn, COLS_PLANTILLA)


def __getattr__(nombre):
    """Funciones fuera de este subconjunto: exigen RellenarPlanilla."""
    if nombre.startswith('__'):
        raise AttributeError(nombre)
    raise RuntimeError(
        "La funcion '%s' no esta incluida en la webapp: necesita la carpeta "
        "RellenarPlanilla completa (flujo de generacion). La conversion de "
        "planillas viejas no la necesita." % nombre)
