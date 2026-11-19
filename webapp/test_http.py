# -*- coding: utf-8 -*-
"""Verificación HTTP: init, upload, catálogo, analyze, generate."""
import io
import os
import sys
import time

import requests

BASE = 'http://127.0.0.1:8778'
RIP = r'C:\Users\neira\OneDrive\Escritorio\RIP-mercadolibre'
ok = 0


def check(nombre, cond, extra=''):
    global ok
    if cond:
        ok += 1
        print('  OK  %s %s' % (nombre, extra))
    else:
        print('  FAIL %s %s' % (nombre, extra))
        sys.exit(1)


# 1) init: catálogo + disponibles
r = requests.get(BASE + '/api/init', timeout=10).json()
check('init', r['ok'])
check('  catálogo con Ripholia',
      any(b['archivo'].startswith('Ripholia') for b in r['archivos']['bases']),
      str(r['archivos']['bases']))
check('  plantilla migrada', r['archivos']['plantilla'] == 'RIP-2323-A.xlsx',
      r['archivos']['plantilla'])
check('  disponibles.bases', 'Ripholia_Normal(15%).xlsx' in r['disponibles']['bases'])

# 2) upload de complemento (multipart)
with open(os.path.join(RIP, 'Ripholia_Precios_15_corregidos.xlsx'), 'rb') as fh:
    data = fh.read()
r = requests.post(BASE + '/api/upload',
                  files=[('archivos', ('Ripholia_Precios_15.xlsx', io.BytesIO(data),
                                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))],
                  data={'tipo': 'complementos'}, timeout=60).json()
check('upload complemento', r['ok'], str(r.get('complementos')))
check('  archivo en datos/complementos',
      os.path.isfile(os.path.join(
          os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
          'datos', 'complementos', 'Ripholia_Precios_15.xlsx')))

# 3) upload repetido no duplica el archivo en disco con otro nombre raro
with open(os.path.join(RIP, 'Ripholia_Precios_15_corregidos.xlsx'), 'rb') as fh:
    data = fh.read()
r = requests.post(BASE + '/api/upload',
                  files=[('archivos', ('Ripholia_Precios_15.xlsx', io.BytesIO(data), 'application/octet-stream'))],
                  data={'tipo': 'complementos'}, timeout=60).json()
check('upload repetido idempotente',
      r['ok'] and r['complementos'].count('Ripholia_Precios_15.xlsx') == 1,
      str(r.get('complementos')))

# 4) catálogo: desactivar Ripholia -> analyze falla (sin bases activas)
cat = requests.get(BASE + '/api/init', timeout=10).json()['archivos']['bases']
cat2 = [dict(b, activa=False) for b in cat]
r = requests.post(BASE + '/api/bases', json={'bases': cat2}, timeout=10).json()
check('guardar catálogo (toggle)', r['ok'] and not r['bases'][0]['activa'])
r = requests.post(BASE + '/api/analyze', json={'marketplace': ''}, timeout=60)
check('analyze sin activas -> error', not r.json().get('ok'),
      r.json().get('error', '')[:60])

# 5) reactivar + analyze usa el catálogo (no rutas del cliente)
r = requests.post(BASE + '/api/bases', json={'bases': cat}, timeout=10).json()
check('reactivar', r['ok'] and r['bases'][0]['activa'])
r = requests.post(BASE + '/api/analyze',
                  json={'marketplace': '', 'prefijo': '', 'predecir_cat': False,
                        'bases': ['C:\\falsa\\no-debe-usarse.xlsx']},
                  timeout=120).json()
check('analyze por catálogo', r['ok'] and r['total_modelos'] == 770,
      'modelos=%s mp=%s' % (r.get('total_modelos'), r.get('marketplace_detectado')))
check('  ignora bases del cliente', r['total_modelos'] == 770)

# 6) generate vía HTTP con el catálogo (2 modelos, sin ML)
requests.post(BASE + '/api/paths', json={'complementos': []}, timeout=10)  # limpiar
r = requests.post(BASE + '/api/generate',
                  json={'marketplace': '', 'categoria': '', 'limite': '2',
                        'modelos': '', 'usar_ml': False, 'max_ml': '0',
                        'usar_ia': False, 'predecir_cat': False,
                        'cuenta': 'TestHttp', 'prefijo_sku': 'L'},
                  timeout=15).json()
check('generate lanza', r.get('ok'), str(r))
for _ in range(120):
    p = requests.get(BASE + '/api/progress', timeout=10).json()
    if not p['activo'] and p.get('resultado'):
        break
    if p.get('error'):
        print('  FAIL generate error:', p['error'])
        sys.exit(1)
    time.sleep(0.5)
check('generate completa', bool(p.get('resultado')),
      str({k: p['resultado'].get(k) for k in ('modelos', 'filas', 'prefijos_sku')}))
check('  prefijo SKU aplicado', p['resultado'].get('prefijos_sku', 0) > 0)

# 7) preview + descarga
r = requests.get(BASE + '/api/preview?rows=3', timeout=15).json()
check('preview', r['ok'] and len(r['filas']) > 0,
      'cols=%d' % len(r.get('encabezados', [])))
fn = p['resultado']['archivo']
r = requests.get(BASE + '/descargas/' + fn, timeout=15)
check('descarga', r.status_code == 200 and len(r.content) > 1000)

# 8) upload de plantilla nueva no rompe (mismo archivo, reuso en disco)
with open(os.path.join(RIP, 'RIP-2323-A.xlsx'), 'rb') as fh:
    data = fh.read()
r = requests.post(BASE + '/api/upload',
                  files=[('archivos', ('RIP-2323-A.xlsx', io.BytesIO(data), 'application/octet-stream'))],
                  data={'tipo': 'plantilla'}, timeout=60).json()
check('upload plantilla (reuso)', r['ok'] and r['plantilla'] == 'RIP-2323-A.xlsx')

print('OK: %d checks HTTP' % ok)
