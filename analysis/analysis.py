#!/usr/bin/env python
# coding: utf-8
"""
Analisis de los resultados del simulador.

Lee los CSV de ../data/ y produce:
  Tabla 1  resumen por condicion
  Tabla 2  efecto del ambar, por diseno de ciclo, con pruebas
  Tabla 3  consistencia del start-up lost time
  Tabla 4  verde efectivo, que es el mecanismo que explica el resultado
  Tabla 5  saturacion
  Tabla 6  punto de equilibrio del ambar de arranque

Uso:
    python analysis.py [ruta_a_data]
"""

import glob
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

# Parametros del experimento, deben coincidir con simulator.py
AMBAR_ARRANQUE = 2.0
AMBAR_DESPEJE = 4.0
PRT = 1.5
SIM_TIME = 300.0

CONDICIONES = ['AMBER/CONSTANTE', 'CONTROL/CONSTANTE',
               'AMBER/EXTENDIDO', 'CONTROL/EXTENDIDO']


def cargar(data_dir, patron):
    archivos = sorted(glob.glob(os.path.join(data_dir, patron)))
    if not archivos:
        sys.exit(f"No se encontraron archivos {patron} en {data_dir}")
    df = pd.concat([pd.read_csv(f) for f in archivos], ignore_index=True)
    df['cond'] = df.escenario + '/' + df.diseno_ciclo
    return df


def promedio(v):
    return float(np.mean(v)) if len(v) else 0.0


def tabla1(veh, fas):
    print("=" * 96)
    print("TABLA 1 - RESUMEN POR CONDICION")
    print("=" * 96)
    filas = []
    for c in CONDICIONES:
        v, f = veh[veh.cond == c], fas[fas.cond == c]
        if not len(v):
            continue
        filas.append(dict(
            condicion=c, verde=v.verde_s.iloc[0], n_veh=len(v),
            flujo=len(v) / SIM_TIME,
            idle=v.idle_time_s.mean(), demora=v.demora_total_s.mean(),
            prt=v.prt_gastado_s.mean(),
            sult=f.start_up_lost_s.mean(), n_fases=len(f),
            cola=f.cola_al_inicio.mean()))
    print(pd.DataFrame(filas).to_string(index=False,
                                        float_format=lambda x: f"{x:.3f}"))


def tabla2(veh, fas):
    print()
    print("=" * 96)
    print("TABLA 2 - EFECTO DEL AMBAR, POR DISENO DE CICLO")
    print("=" * 96)
    for dis in ['CONSTANTE', 'EXTENDIDO']:
        a, c = veh[veh.cond == f'AMBER/{dis}'], veh[veh.cond == f'CONTROL/{dis}']
        fa, fc = fas[fas.cond == f'AMBER/{dis}'], fas[fas.cond == f'CONTROL/{dis}']
        if not len(a) or not len(c):
            continue
        print(f"\n--- DISENO {dis} ---")
        print(f"  {'vehiculos':<26} AMBER {len(a):7d}   CONTROL {len(c):7d}"
              f"   dif {len(a)-len(c):+7d}     ({100*(len(a)-len(c))/len(c):+6.1f}%)")

        def cmp(nombre, va, vc):
            d = va.mean() - vc.mean()
            pct = 100 * d / vc.mean() if vc.mean() else float('nan')
            print(f"  {nombre:<26} AMBER {va.mean():7.3f}   CONTROL {vc.mean():7.3f}"
                  f"   dif {d:+7.3f} s  ({pct:+6.1f}%)")

        cmp('start-up lost (s/acceso)', fa.start_up_lost_s, fc.start_up_lost_s)
        cmp('idle time (s/veh)', a.idle_time_s, c.idle_time_s)
        cmp('demora total (s/veh)', a.demora_total_s, c.demora_total_s)
        cmp('PRT gastado (s/veh)', a.prt_gastado_s, c.prt_gastado_s)

        # Advertencia importante: esto es pseudorreplicacion con una sola semilla.
        t, p = stats.ttest_ind(fa.start_up_lost_s, fc.start_up_lost_s,
                               equal_var=False)
        sp = np.sqrt((fa.start_up_lost_s.var(ddof=1)
                      + fc.start_up_lost_s.var(ddof=1)) / 2)
        d = (fa.start_up_lost_s.mean() - fc.start_up_lost_s.mean()) / sp
        print(f"     start-up: Welch t={t:.2f}  p={p:.3e}  Cohen d={d:.2f}")

        t, p = stats.ttest_ind(a.idle_time_s, c.idle_time_s, equal_var=False)
        sp = np.sqrt((a.idle_time_s.var(ddof=1) + c.idle_time_s.var(ddof=1)) / 2)
        d = (a.idle_time_s.mean() - c.idle_time_s.mean()) / sp
        print(f"     idle    : Welch t={t:.2f}  p={p:.3f}      Cohen d={d:.2f}")

        u, pu = stats.mannwhitneyu(a.demora_total_s, c.demora_total_s)
        print(f"     demora  : Mann-Whitney U p={pu:.3f}")


def tabla3(fas):
    print()
    print("=" * 96)
    print("TABLA 3 - CONSISTENCIA DEL START-UP LOST TIME")
    print("=" * 96)
    print(fas.groupby('cond').start_up_lost_s
          .describe()[['count', 'mean', 'std', 'min', 'max']]
          .to_string(float_format=lambda x: f"{x:.3f}"))
    print("\nAtipicos (fuera de +-3 DE). Suelen ser vehiculos que llegaron en")
    print("movimiento en vez de arrancar desde cola detenida:")
    hubo = False
    for c, g in fas.groupby('cond'):
        if g.start_up_lost_s.std() == 0:
            continue
        z = (g.start_up_lost_s - g.start_up_lost_s.mean()).abs() / g.start_up_lost_s.std()
        for _, r in g[z > 3].iterrows():
            hubo = True
            print(f"  {c:<18} t={r.verde_inicio_s:7.1f}s  {r.direccion:<6}"
                  f"  cola={r.cola_al_inicio:2.0f}  sult={r.start_up_lost_s:.3f}")
    if not hubo:
        print("  ninguno")


def tabla4(veh, fas):
    print()
    print("=" * 96)
    print("TABLA 4 - VERDE EFECTIVO: EL MECANISMO QUE EXPLICA EL RESULTADO")
    print("=" * 96)
    print(f"{'condicion':<19}{'verde':>6}{'fase':>7}{'ciclo':>7}{'sult':>7}"
          f"{'v.efect':>9}{'%ciclo':>9}{'veh obs':>9}")
    filas = []
    for c in ['CONTROL/CONSTANTE', 'AMBER/CONSTANTE',
              'AMBER/EXTENDIDO', 'CONTROL/EXTENDIDO']:
        v, f = veh[veh.cond == c], fas[fas.cond == c]
        if not len(v):
            continue
        g = v.verde_s.iloc[0]
        esc = c.split('/')[0]
        fase = g + AMBAR_DESPEJE + (AMBAR_ARRANQUE if esc == 'AMBER' else 0)
        ciclo = 2 * fase
        s = f.start_up_lost_s.mean()
        ef = g - s
        pct = 100 * ef / ciclo
        filas.append((c, pct, len(v)))
        print(f"{c:<19}{g:>6.0f}{fase:>7.0f}{ciclo:>7.0f}{s:>7.2f}"
              f"{ef:>9.2f}{pct:>8.1f}%{len(v):>9}")
    if filas:
        pred = " > ".join(r[0] for r in sorted(filas, key=lambda r: -r[1]))
        obs = " > ".join(r[0] for r in sorted(filas, key=lambda r: -r[2]))
        print(f"\nOrden predicho por verde efectivo: {pred}")
        print(f"Orden observado por vehiculos    : {obs}")


def tabla5(veh):
    print()
    print("=" * 96)
    print("TABLA 5 - SATURACION")
    print("=" * 96)
    print("Se genera 1 vehiculo por segundo, o sea ~300 en la corrida.")
    for c in CONDICIONES:
        v = veh[veh.cond == c]
        if not len(v):
            continue
        print(f"  {c:<19} cruzaron {len(v):3d} ({100*len(v)/SIM_TIME:.0f}%)"
              f"   demora p50 {v.demora_total_s.median():5.1f}s"
              f"   p90 {v.demora_total_s.quantile(.9):5.1f}s")


def tabla6(fas):
    print()
    print("=" * 96)
    print("TABLA 6 - PUNTO DE EQUILIBRIO DEL AMBAR DE ARRANQUE")
    print("=" * 96)
    sult = fas[fas.escenario == 'CONTROL'].start_up_lost_s.mean()
    print(f"  Start-up lost time que se elimina : {sult:.2f} s")
    print(f"  Costo del ambar de arranque       : {AMBAR_ARRANQUE:.2f} s")
    bal = sult - AMBAR_ARRANQUE
    print(f"  Balance neto por fase             : {bal:+.2f} s"
          f"   -> {'GANA' if bal > 0 else 'PIERDE'}")
    print()
    for ar in [1.0, 1.5, 2.0, 2.5, 3.0]:
        b = sult - ar
        estado = 'gana' if b > 0.02 else ('pierde' if b < -0.02 else 'empata')
        print(f"    ambar de arranque {ar:.1f}s  ->  balance {b:+.2f} s/fase   {estado}")
    print()
    print("  Regla: el ambar de arranque conviene solo si dura menos que el")
    print("  start-up lost time que elimina.")


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else \
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
    veh = cargar(data_dir, 'vehiculos_*.csv')
    fas = cargar(data_dir, 'fases_*.csv')

    print(f"\nRegistros cargados: {len(veh)} vehiculos, {len(fas)} fases,"
          f" {veh.cond.nunique()} condiciones\n")

    tabla1(veh, fas)
    tabla2(veh, fas)
    tabla3(fas)
    tabla4(veh, fas)
    tabla5(veh)
    tabla6(fas)

    print()
    print("=" * 96)
    print("ADVERTENCIA METODOLOGICA")
    print("=" * 96)
    print("  Hay UNA sola replica por condicion. Las pruebas de arriba son a")
    print("  nivel de vehiculo, o sea pseudorreplicacion: inflan la potencia.")
    print("  El efecto sobre start-up es tan grande que sobrevive igual, pero")
    print("  las diferencias de flujo y demora estan dentro del ruido y NO son")
    print("  significativas ni con la potencia inflada.")
    print("  Para afirmar algo sobre flujo hacen falta N semillas, comparadas")
    print("  a nivel de replica y no de vehiculo.")
    print()


if __name__ == '__main__':
    main()
