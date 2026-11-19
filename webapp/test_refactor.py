# -*- coding: utf-8 -*-
"""Verificación del refactor multi-marketplace."""
import sys
sys.path.insert(0, '.')

from core import adapters, loader, pipeline

print('1) REGISTRO:', [c.nombre for c in adapters.REGISTRO])

RIP = r'C:\Users\neira\OneDrive\Escritorio\RIP-mercadolibre'
PLANTILLA = RIP + r'\RIP-2323-A.xlsx'
BASE = RIP + r'\Ripholia_Normal(15%).xlsx'

cls = adapters.detectar(PLANTILLA)
print('2) detectar RIP-2323-A ->', cls.nombre if cls else None)
assert cls is adapters.AdaptadorML, 'Fallo detección ML'

print('3) obtener("") ->', adapters.obtener('').nombre)
print('4) resolver auto ->',
      pipeline.resolver({'plantilla': PLANTILLA}).nombre)
print('5) resolver cencosud ->',
      pipeline.resolver({'marketplace': 'cencosud'}).nombre)

print('--- analizar ---')
res = pipeline.analizar({
    'bases': [BASE],
    'complementos': [],
    'fotos': '',
    'plantilla': PLANTILLA,
    'marketplace': '',
    'prefijo': '',
    'predecir_cat': False,
})
print('6) modelos:', res['total_modelos'],
      '| categorías:', len(res['categorias']),
      '| prefijos:', len(res['prefijos']),
      '| mp:', res['marketplace_detectado'])
assert res['total_modelos'] > 0
assert res['marketplace_detectado'] == 'mercadolibre'

print('OK: detección + analizar')

# ---------- generación end-to-end ----------
import os
import openpyxl
from core.adapters.base import Progreso


class ProgTest(Progreso):
    def fase(self, nombre):
        print('  fase:', nombre)

    def pct(self, valor):
        pass

    def log(self, msg):
        print('  log:', str(msg).encode('cp1252', 'replace').decode('cp1252'))

    def cancelado(self):
        return False


print('--- generar (5 modelos, prefijo SKU L) ---')
outdir = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'salida')
cfg = {
    'bases': [BASE],
    'complementos': [],
    'fotos': '',
    'plantilla': PLANTILLA,
    'outdir': outdir,
    'marketplace': '',
    'categoria': '',            # sin filtro: todas
    'prefijo': '',
    'limite': '5',
    'modelos': '',
    'usar_ml': False,
    'max_ml': '0',
    'usar_ia': False,
    'predecir_cat': False,
    'cuenta': 'TestRefactor',
    'prefijo_sku': 'L',
    'nombre_salida': 'planilla_TestRefactor.xlsx',
}
res = adapters.AdaptadorML.generar(cfg, ProgTest())
print('7) resumen:', {k: res[k] for k in
                      ('archivo', 'modelos', 'filas', 'prefijos_sku',
                       'marketplace')})
assert res['modelos'] > 0 and res['filas'] > 0, 'Generó vacío'
assert res['prefijos_sku'] > 0, 'No aplicó prefijo SKU'

wb = openpyxl.load_workbook(res['ruta'], data_only=True)
rp = loader.importar('rellenar_planilla')
nombre, fila_hdr, fila_inicio, _ = rp.detectar_hoja_productos(wb)
ws = wb[nombre]
idx = rp.mapear_columnas(ws, fila_hdr)
col_sku = idx['sku']
skus = []
for r in range(fila_inicio, ws.max_row + 1):
    v = ws.cell(row=r, column=col_sku + 1).value
    if v:
        skus.append(str(v))
wb.close()
print('8) filas con SKU:', len(skus), '| ej:', skus[:3])
assert skus, 'No hay SKUs en la salida'
assert all(s.upper().startswith('L-') for s in skus), \
    'Algún SKU sin prefijo L-: %r' % skus[:5]

# ---------- filtro por categoría (fix #2) ----------
print('--- generar filtrando por categoría ---')
cats = [c['ruta'] for c in pipeline.analizar({
    'bases': [BASE], 'complementos': [], 'fotos': '',
    'plantilla': PLANTILLA, 'marketplace': '', 'prefijo': '',
    'predecir_cat': False})['categorias']]
elegida = cats[0]
print('  categoría elegida:', elegida)
cfg2 = dict(cfg, categoria=elegida, nombre_salida='planilla_TestCat.xlsx',
            prefijo_sku='', cuenta='TestCat', limite='3')
res2 = adapters.AdaptadorML.generar(cfg2, ProgTest())
print('9) con filtro de categoría -> modelos:', res2['modelos'],
      'filas:', res2['filas'])
assert res2['filas'] > 0, 'Filtro de categoría dejó 0 filas (fix #2 falló)'

print('OK: generación end-to-end + filtro de categoría')
