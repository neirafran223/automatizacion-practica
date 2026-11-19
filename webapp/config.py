# -*- coding: utf-8 -*-
"""Configuraciones estáticas del proyecto.

Se separan aquí todas las constantes que antes estaban mezcladas en
`app.py`.  De esta forma cualquier módulo puede importarlas con
`from .config import …` sin crear dependencias circulares.
"""

# Opciones que el cliente envía y que se guardan en `state.json`.
CAMPOS = (
    'marketplace', 'categoria', 'prefijo', 'limite', 'modelos',
    'usar_ml', 'max_ml', 'usar_ia', 'predecir_cat',
    'cuenta', 'prefijo_sku', 'color_defecto'
)

# Columnas que deben guardarse como número (excluyendo EAN que es texto).
COLS_NUM = (
    'PRECIO', 'STOCK', 'ANCHO', 'ALTO', 'PROFUNDIDAD', 'PESO',
    'COSTO ENVIO', 'TIEMPO', 'CANTIDAD', 'LARGO TITULO'
)

# Texto que aparecen en plantillas nuevas como marcador de posición.
PLACEHOLDERS_NUEVA = ('Escribe o elige un valor', 'Seleccionar')

# Última fila que contiene fórmulas en la plantilla nueva.
ULTIMA_FILA_FORMULAS = 1001

# Palabras en inglés que se **mantienen** en los títulos.
EN_INGLES = frozenset((
    'stretch', 'jersey', 'body', 'boxer', 'polo', 'jeans', 'jean',
    'print', 'premium', 'basic', 'sport', 'runner', 'slim', 'regular',
    'full', 'expandes', 't-shirt', 'short', 'top', 'look',
))

# Traducción inglés → español para los títulos.
TRAD_TITULO = {
    'long': 'largo', 'women': 'mujer', 'woman': 'mujer', 'man': 'hombre',
    'men': 'hombre', 'girl': 'niña', 'boy': 'niño', 'kids': 'niños',
    'child': 'niño', 'children': 'niños', 'dress': 'vestido',
    'shirt': 'camisa', 'pants': 'pantalón', 'jacket': 'chaqueta',
    'coat': 'abrigo', 'cap': 'gorra', 'glove': 'guante',
    'gloves': 'guantes', 'mask': 'mascarilla', 'apron': 'delantal',
    'cotton': 'algodón', 'elastic': 'elástico', 'sleeve': 'manga',
    'sleeves': 'mangas', 'pocket': 'bolsillo', 'pockets': 'bolsillos',
    'white': 'blanco', 'black': 'negro', 'blue': 'azul', 'red': 'rojo',
    'green': 'verde', 'gray': 'gris', 'grey': 'gris', 'pink': 'rosa',
    'size': 'talla', 'sizes': 'tallas', 'scrub': 'uniforme',
    'fluid': 'fluidos', 'resistant': 'resistente', 'protective': 'protector',
}
