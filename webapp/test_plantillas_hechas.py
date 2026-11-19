# -*- coding: utf-8 -*-
"""Genera con las plantillas HECHAS de RIP-mercadolibre y compara fila a fila
con el resultado que dejaron ellas (referencia real de cómo se rellenan)."""
import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import openpyxl  # noqa: E402

from core.adapters.mercadolibre import AdaptadorML  # noqa: E402
from core.adapters.base import Progreso  # noqa: E402

DIR_REF = r'C:\Users\neira\OneDrive\Escritorio\RIP-mercadolibre'
BASE = r'C:\Users\neira\OneDrive\Escritorio\PlanillasML-Web\datos\bases\Ripholia_Normal(15%).xlsx'
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'salida_verif')

CASOS = [
    ('RIP-716.xlsx', 'RIP-716'),
    ('RIP-2254.xlsx', 'RIP-2254'),
    ('RIP-2250 (1).xlsx', 'RIP-2250'),
    ('RIP-2230.xlsx', 'RIP-2230'),
    ('RIP-2323-A.xlsx', 'RIP-2323-A'),
]

IGNORAR = {'ean', 'resumen_errores'}   # ean se genera con semilla propia


class _Prog(Progreso):
    def log(self, msg):
        pass


def leer_filas(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    from core import loader
    rp = loader.importar('rellenar_planilla')
    nombre, fh, fi, _ = rp.detectar_hoja_productos(wb)
    ws = wb[nombre]
    idx = rp.mapear_columnas(ws, fh)
    filas = {}
    for r in range(fi, ws.max_row + 1):
        sku = ws.cell(row=r, column=idx['sku'] + 1).value
        if not sku:
            continue
        fila = {}
        for k, ci in idx.items():
            v = ws.cell(row=r, column=ci + 1).value
            if isinstance(v, float) and v.is_integer():
                v = int(v)
            if isinstance(v, str):
                v = v.strip()
            fila[k] = v
        filas[str(sku).strip()] = fila
    wb.close()
    return filas


def norm_sku(sku, prefijo):
    s = str(sku).strip().upper()
    if prefijo and s.startswith(prefijo.upper() + '-'):
        s = s[len(prefijo) + 1:]
    return s


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    fallos = 0
    for arch, modelo in CASOS:
        ref_path = os.path.join(DIR_REF, arch)
        if not os.path.isfile(ref_path):
            print('FALTA referencia:', arch)
            fallos += 1
            continue
        wb = openpyxl.load_workbook(ref_path, data_only=True)
        cat = wb[wb.sheetnames[0]].cell(row=1, column=1).value
        wb.close()
        salida = os.path.join(OUTDIR, 'gen_%s.xlsx' % modelo)
        cfg = {
            'bases': [BASE],
            'plantilla': ref_path,
            'categoria': (cat or '').strip(),
            'modelos': modelo,
            'prefijo': 'RIP',
            'prefijo_sku': '',
            'outdir': OUTDIR,
            'nombre_salida': os.path.basename(salida),
            'usar_ml': False,
            'max_ml': 0,
        }
        res = AdaptadorML.generar(cfg, _Prog())
        ref = leer_filas(ref_path)
        gen = leer_filas(res['ruta'])
        print('=' * 72)
        print('%s -> %d filas ref / %d filas gen' % (modelo, len(ref), len(gen)))
        if set(ref) != set(gen):
            print('  SKUs distintos! solo ref:', sorted(set(ref) - set(gen))[:8],
                  '| solo gen:', sorted(set(gen) - set(ref))[:8])
            fallos += 1
            continue
        diffs = {}
        iguales = {}
        for sku in ref:
            for k in ref[sku]:
                if k in IGNORAR:
                    continue
                a, b = ref[sku].get(k), gen.get(sku, {}).get(k)
                if a == b:
                    iguales[k] = iguales.get(k, 0) + 1
                else:
                    diffs.setdefault(k, []).append((sku, a, b))
        if not diffs:
            print('  OK identico en %d columnas (%s…)'
                  % (len(iguales), ', '.join(sorted(iguales)[:6])))
        else:
            fallos += 1
            for k, lst in sorted(diffs.items()):
                sku, a, b = lst[0]
                print('  DIFF %-14s %2d/%d filas | ej %s: ref=%r gen=%r'
                      % (k, len(lst), len(ref), sku, str(a)[:34], str(b)[:34]))
    print('=' * 72)
    print('casos con diferencias:', fallos)
    return 0


if __name__ == '__main__':
    sys.exit(main())
