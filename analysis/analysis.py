#!/usr/bin/env python
# coding: utf-8
"""
Analisis de los resultados del simulador.

Lee los CSV de ../data/ y produce:
  Tabla 1  resumen por condicion                     (necesita vehiculos_*.csv)
  Tabla 2  efecto del ambar, por diseno de ciclo     (fases siempre; vehiculos si estan)
  Tabla 3  consistencia del start-up lost time       (fases)
  Tabla 4  verde efectivo                            (fases; vehiculos para el orden observado)
  Tabla 5  saturacion                                (necesita vehiculos_*.csv)
  Tabla 6  punto de equilibrio del ambar de arranque (fases)

Los fases_*.csv estan versionados en el repo. Los vehiculos_*.csv tambien,
pero si faltan este script NO se cae: omite las tablas que dependen de ellos
y lo dice.

Uso:
    python analysis.py [ruta_a_data]

LEER ANTES DE CITAR CUALQUIER NUMERO DE AQUI
--------------------------------------------
1. Hay UNA sola semilla por condicion. La unidad de aleatorizacion es la
   corrida, asi que n = 1 por brazo. Las 34-42 fases-acceso son submuestras
   de esa unica corrida, no replicas. La varianza entre corridas no es
   pequena: es DESCONOCIDA, porque no hay con que estimarla.

2. El start-up lost time es casi determinista por construccion. Con
   PRT < AMBAR_ARRANQUE, el valor esperado bajo AMBER es max(0, PRT -
   AMBAR_ARRANQUE) = 0, y bajo CONTROL es PRT. Lo que se observa alrededor
   de eso es cuantizacion de frames (1/FPS), no variabilidad. Por eso este
   script imprime el tamano de efecto CON y SIN atipicos: si el numero se
   mueve un orden de magnitud al quitar una fila, el denominador es
   artefacto de medicion y el tamano de efecto no significa nada.

3. Los p-valores de aqui salen de pruebas a nivel de fase o de vehiculo.
   Dada (1), subestiman el error estandar. No son evidencia sobre el efecto
   de la intervencion entre corridas.
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
PRT = 1.5          # parametro elegido, NO calibrado. Ver README.
FPS = 60
SIM_TIME = 300.0
TASA_GENERACION = 1.0   # vehiculos por segundo

CONDICIONES = ['AMBER/CONSTANTE', 'CONTROL/CONSTANTE',
               'AMBER/EXTENDIDO', 'CONTROL/EXTENDIDO']


def cargar(data_dir, patron, obligatorio=True):
    """Devuelve un DataFrame, o None si no hay archivos y no es obligatorio."""
    archivos = sorted(glob.glob(os.path.join(data_dir, patron)))
    if not archivos:
        if obligatorio:
            sys.exit(f"No se encontraron archivos {patron} en {data_dir}")
        return None
    df = pd.concat([pd.read_csv(f) for f in archivos], ignore_index=True)
    df['cond'] = df.escenario + '/' + df.diseno_ciclo
    return df


def hedges_g(a, b):
    """Diferencia estandarizada con pooling correcto para n desiguales,
    mas la correccion de Hedges para muestras chicas. Devuelve (d, g)."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float('nan'), float('nan')
    sp2 = ((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2)
    if sp2 <= 0:
        return float('nan'), float('nan')
    d = (a.mean() - b.mean()) / np.sqrt(sp2)
    J = 1 - 3 / (4 * (na + nb) - 9)
    return d, d * J


def sin_atipicos(s, k=3):
    if s.std() == 0:
        return s
    return s[((s - s.mean()).abs() / s.std()) <= k]


def falta(nombre):
    print(f"\n  [omitida: {nombre} requiere vehiculos_*.csv, que no estan en"
          f" esta carpeta]")


def tabla1(veh, fas):
    print("=" * 96)
    print("TABLA 1 - RESUMEN POR CONDICION")
    print("=" * 96)
    if veh is None:
        return falta("Tabla 1")
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
        fa = fas[fas.cond == f'AMBER/{dis}'].start_up_lost_s
        fc = fas[fas.cond == f'CONTROL/{dis}'].start_up_lost_s
        if not len(fa) or not len(fc):
            continue
        print(f"\n--- DISENO {dis} ---")

        # --- start-up lost time (nivel fase-acceso) ---
        d = fa.mean() - fc.mean()
        pct = 100 * d / fc.mean() if fc.mean() else float('nan')
        print(f"  start-up lost (s/acceso)   AMBER {fa.mean():7.3f}"
              f"   CONTROL {fc.mean():7.3f}   dif {d:+7.3f} s  ({pct:+6.1f}%)")

        t, p = stats.ttest_ind(fa, fc, equal_var=False)
        _, g = hedges_g(fa, fc)
        fc2 = sin_atipicos(fc)
        _, g2 = hedges_g(fa, fc2)
        print(f"     Welch t={t:.2f}  p={p:.2e}   Hedges g={g:.2f}"
              f"   (n={len(fa)} vs {len(fc)})")
        print(f"     g sin atipicos del control = {g2:.2f}"
              f"   (quitando {len(fc)-len(fc2)} de {len(fc)} filas)")
        if abs(g2) > 3 * abs(g):
            print("     >> El tamano de efecto se mueve un orden de magnitud al")
            print("        quitar una fila: el denominador es cuantizacion de")
            print("        frames, no variabilidad. NO cites este g como hallazgo.")
        print(f"     Valor esperado por construccion: AMBER"
              f" {max(0.0, PRT - AMBAR_ARRANQUE):.2f} s,"
              f" CONTROL {PRT:.2f} s  (+/- 1 frame = {1/FPS:.3f} s)")

        # --- resultados a nivel de vehiculo ---
        if veh is None:
            falta("comparacion a nivel de vehiculo")
            continue
        a = veh[veh.cond == f'AMBER/{dis}']
        c = veh[veh.cond == f'CONTROL/{dis}']
        if not len(a) or not len(c):
            continue

        print(f"  {'vehiculos que cruzaron':<26} AMBER {len(a):7d}"
              f"   CONTROL {len(c):7d}   dif {len(a)-len(c):+7d}"
              f"     ({100*(len(a)-len(c))/len(c):+6.1f}%)")
        print("     (un solo numero por condicion: no hay prueba posible"
              " con una semilla)")

        for nombre, col in [('idle time (s/veh)', 'idle_time_s'),
                            ('demora total (s/veh)', 'demora_total_s'),
                            ('PRT gastado (s/veh)', 'prt_gastado_s')]:
            va, vc = a[col], c[col]
            dd = va.mean() - vc.mean()
            pp = 100 * dd / vc.mean() if vc.mean() else float('nan')
            print(f"  {nombre:<26} AMBER {va.mean():7.3f}"
                  f"   CONTROL {vc.mean():7.3f}   dif {dd:+7.3f} s"
                  f"  ({pp:+6.1f}%)")

        t, p = stats.ttest_ind(a.idle_time_s, c.idle_time_s, equal_var=False)
        _, g = hedges_g(a.idle_time_s, c.idle_time_s)
        print(f"     idle  : Welch p={p:.3f}   Hedges g={g:.2f}"
              f"   <- g chico: diferencia trivial aunque p sea bajo")
        u, pu = stats.mannwhitneyu(a.demora_total_s, c.demora_total_s)
        print(f"     demora: Mann-Whitney p={pu:.3f}"
              f"   (dominancia estocastica, no medias)")
        t, p = stats.ttest_ind(a.prt_gastado_s, c.prt_gastado_s, equal_var=False)
        print(f"     PRT   : Welch p={p:.3f}")


def tabla3(fas):
    print()
    print("=" * 96)
    print("TABLA 3 - CONSISTENCIA DEL START-UP LOST TIME")
    print("=" * 96)
    print(fas.groupby('cond').start_up_lost_s
          .describe()[['count', 'mean', 'std', 'min', 'max']]
          .to_string(float_format=lambda x: f"{x:.4f}"))
    print(f"\nValores distintos por condicion (paso de frame = {1/FPS:.4f} s):")
    for c, g in fas.groupby('cond'):
        vals = sorted(g.start_up_lost_s.round(4).unique())
        print(f"  {c:<19} {len(vals):2d} valores   {vals[:4]} ...")
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
    print("TABLA 4 - VERDE EFECTIVO")
    print("=" * 96)
    print(f"{'condicion':<19}{'verde':>6}{'fase':>7}{'ciclo':>7}{'sult':>7}"
          f"{'v.efect':>9}{'%ciclo':>9}{'veh obs':>9}")
    filas = []
    verdes = {'AMBER/CONSTANTE': 10, 'CONTROL/CONSTANTE': 12,
              'AMBER/EXTENDIDO': 10, 'CONTROL/EXTENDIDO': 10}
    for c in ['CONTROL/CONSTANTE', 'AMBER/CONSTANTE',
              'AMBER/EXTENDIDO', 'CONTROL/EXTENDIDO']:
        f = fas[fas.cond == c]
        if not len(f):
            continue
        g = veh[veh.cond == c].verde_s.iloc[0] if veh is not None else verdes[c]
        esc = c.split('/')[0]
        fase = g + AMBAR_DESPEJE + (AMBAR_ARRANQUE if esc == 'AMBER' else 0)
        ciclo = 2 * fase
        s = f.start_up_lost_s.mean()
        ef = g - s
        pct = 100 * ef / ciclo
        nveh = len(veh[veh.cond == c]) if veh is not None else 0
        filas.append((c, pct, nveh))
        print(f"{c:<19}{g:>6.0f}{fase:>7.0f}{ciclo:>7.0f}{s:>7.2f}"
              f"{ef:>9.2f}{pct:>8.1f}%{nveh if veh is not None else '-':>9}")
    if filas and veh is not None:
        pred = sorted(filas, key=lambda r: -r[1])
        obs = sorted(filas, key=lambda r: -r[2])
        print(f"\nOrden predicho por verde efectivo: "
              + " > ".join(r[0] for r in pred))
        print(f"Orden observado por vehiculos    : "
              + " > ".join(r[0] for r in obs))
        rango_ef = max(r[1] for r in filas) - min(r[1] for r in filas)
        rango_v = max(r[2] for r in filas) - min(r[2] for r in filas)
        base_v = min(r[2] for r in filas)
        print(f"\nRango de verde efectivo : {rango_ef:.2f} puntos porcentuales"
              f"  ({100*rango_ef/min(r[1] for r in filas):.1f}% relativo)")
        print(f"Rango de vehiculos      : {rango_v:.0f} vehiculos"
              f"  ({100*rango_v/base_v:.1f}% relativo)")
        print("Si el flujo siguiera al verde efectivo, los dos rangos relativos")
        print("serian parecidos. No lo son. Con 4 condiciones, 1 semilla y un")
        print("rango total de 4 vehiculos, este orden no distingue nada.")


def tabla5(veh):
    print()
    print("=" * 96)
    print("TABLA 5 - SATURACION")
    print("=" * 96)
    if veh is None:
        return falta("Tabla 5")
    generados = TASA_GENERACION * SIM_TIME
    print(f"Se genera {TASA_GENERACION:.0f} vehiculo/s durante {SIM_TIME:.0f} s"
          f" = {generados:.0f} vehiculos.")
    for c in CONDICIONES:
        v = veh[veh.cond == c]
        if not len(v):
            continue
        print(f"  {c:<19} cruzaron {len(v):3d} de {generados:.0f}"
              f" ({100*len(v)/generados:.0f}% de la demanda)"
              f"   demora p50 {v.demora_total_s.median():5.1f}s"
              f"   p90 {v.demora_total_s.quantile(.9):5.1f}s")
    print("\n  Al 88-89% de la demanda despachada la interseccion esta apenas")
    print("  sobresaturada, no en saturacion dura. Ahi un segundo de verde")
    print("  efectivo vale bastante menos que un vehiculo, que es justo por que")
    print("  el balance en segundos de la Tabla 6 no se puede leer como flujo.")


def tabla6(fas):
    print()
    print("=" * 96)
    print("TABLA 6 - PUNTO DE EQUILIBRIO DEL AMBAR DE ARRANQUE")
    print("=" * 96)
    sult = fas[fas.escenario == 'CONTROL'].start_up_lost_s.mean()
    print(f"  Start-up lost time que se elimina : {sult:.2f} s"
          f"   (= PRT + cuantizacion, no una medicion independiente)")
    print(f"  Costo del ambar de arranque       : {AMBAR_ARRANQUE:.2f} s")
    bal = sult - AMBAR_ARRANQUE
    print(f"  Balance neto por fase             : {bal:+.2f} s"
          f"   -> {'GANA' if bal > 0 else 'PIERDE'}")
    print()
    print("  ESTO NO ES UN RESULTADO EMPIRICO. Es la desigualdad")
    print("  PRT < AMBAR_ARRANQUE, reescrita. Ambos terminos son parametros")
    print("  de entrada. La simulacion no aporta nada a esta linea.")
    print()
    print(f"  Sensibilidad al PRT (fijando el ambar en"
          f" {AMBAR_ARRANQUE:.1f} s):")
    for prt in [1.0, 1.5, 2.0, 2.5, 3.0]:
        b = prt - AMBAR_ARRANQUE
        estado = 'gana' if b > 0.02 else ('pierde' if b < -0.02 else 'empata')
        marca = '  <- valor usado aqui, sin citar' if abs(prt - PRT) < 1e-9 else ''
        print(f"    PRT {prt:.1f}s  ->  balance {b:+.2f} s/fase   {estado}{marca}")
    print()
    print("  El PRT publicado va de ~1.0 a ~2.5 s segun la fuente. El signo de")
    print("  la respuesta cambia dentro de ese rango. Mientras el PRT no este")
    print("  calibrado contra datos reales, esta tabla es una condicion, no una")
    print("  conclusion.")


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else \
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
    fas = cargar(data_dir, 'fases_*.csv', obligatorio=True)
    veh = cargar(data_dir, 'vehiculos_*.csv', obligatorio=False)

    print(f"\nRegistros cargados: {len(fas)} fases,"
          f" {len(veh) if veh is not None else 0} vehiculos,"
          f" {fas.cond.nunique()} condiciones")
    if veh is None:
        print("AVISO: no hay vehiculos_*.csv en esta carpeta. Las tablas que")
        print("dependen de ellos se omiten; el resto corre igual. Para")
        print("generarlos, corre las cuatro configuraciones de simulator.py.")
    print()

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
    print("  1. UNA sola semilla por condicion. La unidad de aleatorizacion es")
    print("     la corrida, asi que n = 1 por brazo. Las fases-acceso son")
    print("     submuestras de una sola historia de trafico, no replicas, y")
    print("     comparten estado de cola entre si. La varianza entre corridas")
    print("     no es pequena: no hay con que estimarla.")
    print()
    print("  2. El efecto sobre start-up lost time no 'sobrevive' a esto: es")
    print("     una consecuencia algebraica de PRT < AMBAR_ARRANQUE y no")
    print("     necesitaba estadistica. El g y el p de arriba describen la")
    print("     resolucion del reloj del simulador, no la intervencion.")
    print()
    print("  3. Las diferencias de flujo y demora no son detectables aqui, que")
    print("     no es lo mismo que decir que no existen. No hay analisis de")
    print("     potencia ni limite de equivalencia, asi que el estudio no puede")
    print("     afirmar la nula.")
    print()
    print("  4. Las fases sin cola se descartan. Eso condiciona sobre una")
    print("     variable posterior al tratamiento y deja n desigual entre")
    print("     brazos (34 vs 36, 34 vs 42). El sesgo probablemente es chico")
    print("     bajo saturacion, pero no esta cuantificado.")
    print()
    print("  Para afirmar algo sobre flujo o demora hacen falta N semillas,")
    print("  comparadas a nivel de replica y no de vehiculo, con el PRT")
    print("  calibrado o barrido como factor.")
    print()


if __name__ == '__main__':
    main()
