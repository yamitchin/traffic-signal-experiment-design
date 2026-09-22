#!/usr/bin/env python
# coding: utf-8
"""
Descarga los sprites de vehiculos y semaforos desde el repositorio original.

Las imagenes son de Gandhi, M., Solanki, D., Daptardar, R. & Baloorkar, N.
(2020), 'Smart Control of Traffic Light Using Artificial Intelligence',
IEEE ICRAIE 2020, publicado bajo Apache License 2.0:

    https://github.com/mihir-m-gandhi/Adaptive-Traffic-Signal-Timer

No se versionan aqui porque no son obra propia. Este script las trae.

Uso:
    python fetch_assets.py
"""

import os
import sys
import urllib.request

BASE = ("https://raw.githubusercontent.com/mihir-m-gandhi/"
        "Adaptive-Traffic-Signal-Timer/main/Code/YOLO/darkflow/images")

DIRECCIONES = ['right', 'down', 'left', 'up']
VEHICULOS = ['car', 'bus', 'truck', 'bike']

# destino local -> ruta en el repo original
ARCHIVOS = {
    'red.png': 'signals/red.png',
    'yellow.png': 'signals/yellow.png',
    'green.png': 'signals/green.png',
    'intersection.png': 'mod_int.png',
}
for d in DIRECCIONES:
    for v in VEHICULOS:
        ARCHIVOS[os.path.join('images', d, v + '.png')] = f'{d}/{v}.png'


def descargar(destino, remoto):
    url = f'{BASE}/{remoto}'
    os.makedirs(os.path.dirname(destino) or '.', exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            datos = r.read()
    except Exception as e:
        print(f'  FALLO  {destino}  ({e})')
        return False
    with open(destino, 'wb') as fh:
        fh.write(datos)
    print(f'  ok     {destino}  ({len(datos)//1024} KB)')
    return True


def main():
    raiz = os.path.dirname(os.path.abspath(__file__))
    os.chdir(raiz)
    print(f'Descargando {len(ARCHIVOS)} imagenes desde el repositorio original...')
    ok = sum(descargar(d, r) for d, r in sorted(ARCHIVOS.items()))
    print(f'\n{ok}/{len(ARCHIVOS)} descargadas.')
    if ok < len(ARCHIVOS):
        print('Faltaron archivos. El simulador no arrancara sin ellos.')
        sys.exit(1)
    print('Listo. Ya puedes correr:  python simulator.py')


if __name__ == '__main__':
    main()
