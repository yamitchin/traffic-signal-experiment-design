#!/usr/bin/env python
# coding: utf-8
"""
Simulador de semaforos - Comparacion AMBER vs CONTROL
Yamit Chinchilla - INFO7017 Postgraduate Project B

Base: Gandhi, M., Solanki, D., Daptardar, R. & Baloorkar, N. (2020).
      'Intelligent Traffic Signal Control Using Artificial Intelligence',
      IEEE ICRAIE 2020.

======================================================================
v4 - DOS AMBARES DISTINTOS, CON DURACIONES NORMATIVAS
======================================================================
Hasta la v3 habia un solo parametro de ambar, de 5 segundos, usado para
dos cosas que son distintas. Peor: el escenario AMBER no tenia ambar de
despeje, pasaba de verde directo a rojo, algo que no ocurre en ninguna
interseccion real y que ademas le regalaba 5 segundos de ciclo frente
al control.

Son DOS intervalos diferentes:

  AMBAR DE ARRANQUE (rojo + ambar, antes del verde)
      Solo existe en el escenario AMBER. Avisa al conductor que el
      verde viene, para que empiece a reaccionar.
      Reino Unido, TAL 1/06 (DfT): "the red + amber signal at two
      seconds". Maxwell & York (2005), ya citado en el PPA, reporta
      1.0, 1.5, 2.0 s y 3.0 s en Rusia.
      -> AMBAR_ARRANQUE = 2.0 s

  AMBAR DE DESPEJE (ambar despues del verde)
      Existe en LOS DOS escenarios. Permite limpiar la interseccion
      antes del rojo.
      Australia, TS001 (basado en Austroads), por limite de velocidad:
          40 km/h  3.0 s     70 km/h  4.5 s
          50 km/h  4.0 s     80 km/h  5.0 s
          60 km/h  4.0 s    100 km/h  6.0 s
      Reino Unido, TAL 1/06: fijo en 3 segundos.
      -> AMBAR_DESPEJE = 4.0 s  (via urbana de 50-60 km/h)

Las secuencias completas quedan asi:

    AMBER    ROJO -> ROJO+AMBAR (2s) -> VERDE -> AMBAR (4s) -> ROJO
    CONTROL  ROJO ->                    VERDE -> AMBAR (4s) -> ROJO

======================================================================
DISENO DEL CICLO
======================================================================
El ambar de arranque agrega 2 segundos a la fase. Si se dejan sin
compensar, los dos escenarios dejan de tener el mismo ciclo y la
comparacion ya no aisla el efecto del ambar.

  DISENO_CICLO = "CONSTANTE"   (experimento principal)
      El ambar de arranque se paga con verde. El control recibe esos
      2 segundos como verde adicional, asi que la fase dura lo mismo
      en los dos escenarios.
          AMBER    2 + 10 + 4 = 16 s por fase
          CONTROL      12 + 4 = 16 s por fase
      Pregunta que responde: la anticipacion, compensa los 2 segundos
      de verde que hubo que ceder? Es el test conservador.

  DISENO_CICLO = "EXTENDIDO"   (analisis de sensibilidad)
      Los dos con el mismo verde. La fase del AMBER dura 2 s mas.
          AMBER    2 + 10 + 4 = 16 s por fase
          CONTROL      10 + 4 = 14 s por fase
      Es lo que hacen algunos despliegues reales, pero el resultado
      mezcla dos efectos: la anticipacion y el ciclo mas largo.

======================================================================
FASES CON MOVIMIENTOS OPUESTOS CONCURRENTES (desde v3)
======================================================================
Los movimientos opuestos no son conflictivos y se habilitan juntos:
    Fase 0  Norte-Sur   : down + up
    Fase 1  Este-Oeste  : right + left
El modelo no incluye giros, asi que no hay conflicto. Si se agregan
giros a la izquierda habria que darles fase protegida.

======================================================================
METRICAS
======================================================================
M1  idle_time       segundos detenido, acumulado por vehiculo
M2  prt_gastado     segundos de reaccion efectivamente consumidos
M3  start_up_lost   segundos entre el inicio del verde y el cruce del
                    primer vehiculo de la cola, medido por acceso
"""

import csv
import os
import random
import sys
import threading
import time

import pygame

# ======================================================================
# CONFIGURACION DEL EXPERIMENTO
# ======================================================================
ESCENARIO = "AMBER"            # "AMBER"  o  "CONTROL"
DISENO_CICLO = "CONSTANTE"     # "CONSTANTE"  o  "EXTENDIDO"
RANDOM_SEED = 42               # una semilla distinta = una replica distinta

# ----------------------------------------------------------------------
# Parametros compartidos. IDENTICOS en los dos escenarios.
# ----------------------------------------------------------------------
FPS = 60
SIMULATION_TIME = 300          # segundos de simulacion

PRT = 1.5                      # Perception-Reaction Time, en segundos

LIMITE_VELOCIDAD = 60          # km/h, solo documenta de donde sale el ambar
AMBAR_ARRANQUE = 2.0           # rojo+ambar, solo escenario AMBER (UK TAL 1/06)
AMBAR_DESPEJE = 4.0            # despues del verde, ambos (AU TS001, 50-60 km/h)
VERDE_BASE = 10.0              # verde del escenario AMBER

stoppingGap = 15
movingGap = 15

speedsPerSecond = {'car': 135.0, 'bus': 108.0, 'truck': 108.0, 'bike': 150.0}

EXPORT_CSV = True
MOSTRAR_IDLE_EN_PANTALLA = True

# ----------------------------------------------------------------------
# Derivados
# ----------------------------------------------------------------------
if ESCENARIO not in ("AMBER", "CONTROL"):
    raise SystemExit("ESCENARIO debe ser 'AMBER' o 'CONTROL'")
if DISENO_CICLO not in ("CONSTANTE", "EXTENDIDO"):
    raise SystemExit("DISENO_CICLO debe ser 'CONSTANTE' o 'EXTENDIDO'")

ANTICIPATION = (ESCENARIO == "AMBER")

if ESCENARIO == "AMBER":
    VERDE = VERDE_BASE
elif DISENO_CICLO == "CONSTANTE":
    VERDE = VERDE_BASE + AMBAR_ARRANQUE   # el control recibe el verde cedido
else:
    VERDE = VERDE_BASE

DURACION_FASE = VERDE + AMBAR_DESPEJE + (AMBAR_ARRANQUE if ESCENARIO == "AMBER" else 0.0)

FASES = [
    ('down', 'up'),      # Fase 0: eje Norte-Sur
    ('right', 'left'),   # Fase 1: eje Este-Oeste
]
FASE_DE = {'down': 0, 'up': 0, 'right': 1, 'left': 1}
NOMBRE_FASE = {0: "Norte-Sur", 1: "Este-Oeste"}
noOfFases = len(FASES)
DURACION_CICLO = DURACION_FASE * noOfFases

ETIQUETA_INTERVALO = {
    'red': 'ROJO',
    'amber_start': 'ROJO+AMBAR',
    'green': 'VERDE',
    'amber_clear': 'AMBAR',
}

random.seed(RANDOM_SEED)

# ======================================================================
# ESTADO GLOBAL
# ======================================================================
currentFase = 0
currentPhase = 'red'          # 'red' | 'amber_start' | 'green' | 'amber_clear'
intervaloFin = 0.0

simClock = 0.0
wallElapsed = 0

lane_counters = {'right': 0, 'down': 0, 'left': 0, 'up': 0}
vehicleRecords = []
phaseRecords = []

x = {'right': [0, 0, 0], 'down': [755, 727, 697],
     'left': [1400, 1400, 1400], 'up': [602, 627, 657]}
y = {'right': [348, 370, 398], 'down': [0, 0, 0],
     'left': [498, 466, 436], 'up': [800, 800, 800]}

vehicles = {
    'right': {0: [], 1: [], 2: [], 'crossed': 0},
    'down':  {0: [], 1: [], 2: [], 'crossed': 0},
    'left':  {0: [], 1: [], 2: [], 'crossed': 0},
    'up':    {0: [], 1: [], 2: [], 'crossed': 0},
}
vehicleTypes = {0: 'car', 1: 'bus', 2: 'truck', 3: 'bike'}
directionNumbers = {0: 'right', 1: 'down', 2: 'left', 3: 'up'}

signalCoods = [(530, 230), (810, 230), (810, 570), (530, 570)]
signalTimerCoods = [(530, 210), (810, 210), (810, 550), (530, 550)]
stopLines = {'right': 590, 'down': 330, 'left': 800, 'up': 535}
defaultStop = {'right': 580, 'down': 320, 'left': 810, 'up': 545}
timeElapsedCoods = (1090, 50)

pygame.init()
simulation = pygame.sprite.Group()


class Vehicle(pygame.sprite.Sprite):
    def __init__(self, lane, vehicleClass, direction_number, direction):
        pygame.sprite.Sprite.__init__(self)
        self.lane = lane
        self.vehicleClass = vehicleClass
        self.speed = speedsPerSecond[vehicleClass] / FPS
        self.direction_number = direction_number
        self.direction = direction
        self.fase = FASE_DE[direction]
        self.x = x[direction][lane]
        self.y = y[direction][lane]
        self.crossed = 0

        # Metricas
        self.idle_time = 0.0
        self.queued = False
        self.was_moving = True
        self.prt_remaining = 0.0
        self.prt_total = 0.0
        self.spawn_time = simClock
        self.cross_time = None

        vehicles[direction][lane].append(self)
        self.index = len(vehicles[direction][lane]) - 1

        path = os.path.join("images", direction, vehicleClass + ".png")
        self.image = pygame.image.load(path)

        # Ver NOTA S1 al final: sin coordenada de parada por vehiculo.
        self.stop = defaultStop[direction]

        if direction == 'right':
            x[direction][lane] -= self.image.get_rect().width + stoppingGap
        elif direction == 'left':
            x[direction][lane] += self.image.get_rect().width + stoppingGap
        elif direction == 'down':
            y[direction][lane] -= self.image.get_rect().height + stoppingGap
        else:
            y[direction][lane] += self.image.get_rect().height + stoppingGap

        simulation.add(self)

    # ------------------------------------------------------------------
    def getLeader(self):
        if self.index == 0:
            return None
        return vehicles[self.direction][self.lane][self.index - 1]

    def hasGreen(self):
        """Derecho de paso: su fase activa y en verde. Nunca en ambar."""
        return self.fase == currentFase and currentPhase == 'green'

    def isCued(self, leader):
        """
        M2. Momento en que el conductor recibe el estimulo para arrancar.

        Con alguien adelante que aun no cruza, el estimulo es que ESE
        vehiculo se mueva. Eso reproduce la onda de arranque de la cola,
        que es donde se genera el start-up lost time.

        Siendo el primero, el estimulo es el semaforo de su fase:
            CONTROL : solo el verde
            AMBER   : tambien el rojo+ambar, 2 segundos antes
        El ambar de DESPEJE nunca es estimulo de arranque.
        """
        if leader is not None and leader.crossed == 0:
            return leader.was_moving

        if self.fase != currentFase:
            return False
        if currentPhase == 'green':
            return True
        if ANTICIPATION and currentPhase == 'amber_start':
            return True
        return False

    def beforeStopLine(self, w, h):
        if self.direction == 'right':
            return (self.x + w) <= self.stop
        if self.direction == 'down':
            return (self.y + h) <= self.stop
        if self.direction == 'left':
            return self.x >= self.stop
        return self.y >= self.stop

    def hasRoom(self, leader, w, h):
        if leader is None:
            return True
        lw = leader.image.get_rect().width
        lh = leader.image.get_rect().height
        if self.direction == 'right':
            return (self.x + w) < (leader.x - movingGap)
        if self.direction == 'down':
            return (self.y + h) < (leader.y - movingGap)
        if self.direction == 'left':
            return self.x > (leader.x + lw + movingGap)
        return self.y > (leader.y + lh + movingGap)

    # ------------------------------------------------------------------
    def update_vehicle(self, dt):
        w = self.image.get_rect().width
        h = self.image.get_rect().height
        leader = self.getLeader()

        # M2. descuento del tiempo de reaccion
        if self.queued and self.prt_remaining > 0 and self.isCued(leader):
            consumido = min(dt, self.prt_remaining)
            self.prt_remaining -= consumido
            self.prt_total += consumido

        reaccionando = self.queued and self.prt_remaining > 0

        if self.crossed:
            permitido = True
        elif self.beforeStopLine(w, h):
            permitido = True
        else:
            permitido = self.hasGreen()

        espacio = self.hasRoom(leader, w, h)
        se_mueve = permitido and espacio and not reaccionando

        if se_mueve:
            if self.direction == 'right':
                self.x += self.speed
            elif self.direction == 'down':
                self.y += self.speed
            elif self.direction == 'left':
                self.x -= self.speed
            else:
                self.y -= self.speed

        # M1. tiempo detenido, acumulado
        if not se_mueve and not self.crossed:
            if self.was_moving:
                self.prt_remaining = PRT
            self.queued = True
            self.idle_time += dt
        else:
            self.queued = False

        self.was_moving = se_mueve

        # Cruce
        if self.crossed == 0:
            if self.direction == 'right':
                cruzo = (self.x + w) > stopLines[self.direction]
            elif self.direction == 'down':
                cruzo = (self.y + h) > stopLines[self.direction]
            elif self.direction == 'left':
                cruzo = self.x < stopLines[self.direction]
            else:
                cruzo = self.y < stopLines[self.direction]

            if cruzo:
                self.crossed = 1
                self.cross_time = simClock
                vehicles[self.direction]['crossed'] += 1
                lane_counters[self.direction] += 1
                vehicleRecords.append({
                    'escenario': ESCENARIO,
                    'diseno_ciclo': DISENO_CICLO,
                    'semilla': RANDOM_SEED,
                    'verde_s': VERDE,
                    'fase': NOMBRE_FASE[self.fase],
                    'direccion': self.direction,
                    'carril': self.lane,
                    'tipo': self.vehicleClass,
                    'spawn_s': round(self.spawn_time, 3),
                    'cruce_s': round(self.cross_time, 3),
                    'demora_total_s': round(self.cross_time - self.spawn_time, 3),
                    'idle_time_s': round(self.idle_time, 3),
                    'prt_gastado_s': round(self.prt_total, 3),
                })


# ======================================================================
# SEMAFOROS
# ======================================================================
def waitSim(segundos):
    """
    Espera N segundos DE SIMULACION, no de reloj de pared.

    El original usaba time.sleep(1) para las senales mientras los
    vehiculos se movian por frame. Si la maquina no sostenia los FPS,
    las senales corrian mas rapido que el trafico y los resultados
    cambiaban de computador a computador. Con esto una maquina lenta
    solo tarda mas: los numeros salen identicos.
    """
    objetivo = simClock + segundos
    while simClock < objetivo:
        time.sleep(0.002)


def correrIntervalo(nombre, duracion):
    global currentPhase, intervaloFin
    currentPhase = nombre
    intervaloFin = simClock + duracion
    waitSim(duracion)


def repeat():
    """
    Ciclo de dos fases. AQUI ESTA LA UNICA DIFERENCIA ENTRE ESCENARIOS.

        AMBER    rojo+ambar (2s) -> verde -> ambar (4s)
        CONTROL                     verde -> ambar (4s)

    No hace falta contador de rojo: una fase esta en rojo por definicion
    mientras la otra corre sus intervalos. Eso elimina la aritmetica
    fragil de contadores rojos que tenia el codigo original.
    """
    global currentFase

    while True:
        if ESCENARIO == "AMBER":
            correrIntervalo('amber_start', AMBAR_ARRANQUE)
        correrIntervalo('green', VERDE)
        correrIntervalo('amber_clear', AMBAR_DESPEJE)
        currentFase = (currentFase + 1) % noOfFases


def generateVehicles():
    while True:
        waitSim(1)
        vehicle_type = random.randint(0, 3)
        lane_number = random.randint(1, 2)
        temp = random.randint(0, 99)
        if temp < 25:
            direction_number = 0
        elif temp < 50:
            direction_number = 1
        elif temp < 75:
            direction_number = 2
        else:
            direction_number = 3
        Vehicle(lane_number, vehicleTypes[vehicle_type],
                direction_number, directionNumbers[direction_number])


def wallClock():
    global wallElapsed
    while True:
        time.sleep(1)
        wallElapsed += 1


# ======================================================================
# RESULTADOS
# ======================================================================
def queueLength(direction):
    n = 0
    for lane in range(3):
        for v in vehicles[direction][lane]:
            if v.crossed == 0 and v.queued:
                n += 1
    return n


def promedio(valores):
    return sum(valores) / len(valores) if valores else 0.0


def cerrarFases(abiertas):
    """Solo cuentan los accesos que tenian cola. Sin cola no hay arranque."""
    for reg in abiertas:
        if reg['cola_al_inicio'] > 0:
            phaseRecords.append(reg)


def showStats():
    total = sum(lane_counters.values())
    idle = [r['idle_time_s'] for r in vehicleRecords]
    prt = [r['prt_gastado_s'] for r in vehicleRecords]
    demora = [r['demora_total_s'] for r in vehicleRecords]
    sult = [p['start_up_lost_s'] for p in phaseRecords
            if p['start_up_lost_s'] is not None]

    if ESCENARIO == "AMBER":
        sec = "rojo > ROJO+AMBAR %.0fs > verde %.0fs > ambar %.0fs" % (
            AMBAR_ARRANQUE, VERDE, AMBAR_DESPEJE)
    else:
        sec = "rojo > verde %.0fs > ambar %.0fs" % (VERDE, AMBAR_DESPEJE)

    print()
    print("=" * 68)
    print(" ESCENARIO: %s   |   DISENO DE CICLO: %s" % (ESCENARIO, DISENO_CICLO))
    print(" Secuencia: %s" % sec)
    print(" Fase %.0f s  |  Ciclo %.0f s  |  %d km/h  |  PRT %.1f s  |  Semilla %d" % (
        DURACION_FASE, DURACION_CICLO, LIMITE_VELOCIDAD, PRT, RANDOM_SEED))
    print("-" * 68)
    for f in range(noOfFases):
        sub = sum(lane_counters[d] for d in FASES[f])
        print("   Fase %d  %-11s : %3d vehiculos   (%s)" % (
            f, NOMBRE_FASE[f], sub,
            ", ".join("%s %d" % (d, lane_counters[d]) for d in FASES[f])))
    print("-" * 68)
    print("   Vehiculos que cruzaron   : %d" % total)
    print("   Tiempo de simulacion     : %.1f s" % simClock)
    print("   Flujo promedio           : %.3f veh/s" % (total / simClock if simClock else 0))
    print("-" * 68)
    print("   M1  Idle time promedio   : %6.2f s/veh    (n=%d)" % (promedio(idle), len(idle)))
    print("   M2  PRT gastado promedio : %6.2f s/veh" % promedio(prt))
    print("   M3  Start-up lost time   : %6.2f s/acceso (n=%d)" % (
        promedio(sult), len(sult)))
    print("       Demora total media   : %6.2f s/veh" % promedio(demora))
    print("=" * 68)

    if EXPORT_CSV:
        exportCSV()


def exportCSV():
    base = "%s_%s_seed%d" % (ESCENARIO, DISENO_CICLO, RANDOM_SEED)
    if vehicleRecords:
        f1 = "vehiculos_%s.csv" % base
        with open(f1, "w", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(vehicleRecords[0].keys()))
            wr.writeheader()
            wr.writerows(vehicleRecords)
        print("CSV escrito: %s  (%d filas)" % (f1, len(vehicleRecords)))
    if phaseRecords:
        f2 = "fases_%s.csv" % base
        with open(f2, "w", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(phaseRecords[0].keys()))
            wr.writeheader()
            wr.writerows(phaseRecords)
        print("CSV escrito: %s  (%d filas)" % (f2, len(phaseRecords)))


# ======================================================================
class Main:
    def __init__(self):
        global simClock

        black = (0, 0, 0)
        white = (255, 255, 255)
        screen = pygame.display.set_mode((1400, 800))
        pygame.display.set_caption("SIMULACION - %s (%s)" % (ESCENARIO, DISENO_CICLO))

        background = pygame.image.load('intersection.png')
        redSignal = pygame.image.load('red.png')
        amberSignal = pygame.image.load('yellow.png')
        greenSignal = pygame.image.load('green.png')
        font = pygame.font.Font(None, 26)
        fontSmall = pygame.font.Font(None, 20)

        threading.Thread(name="initialization", target=repeat, daemon=True).start()
        threading.Thread(name="generateVehicles", target=generateVehicles, daemon=True).start()
        threading.Thread(name="wallClock", target=wallClock, daemon=True).start()

        clock = pygame.time.Clock()
        dt = 1.0 / FPS
        prev_key = None
        abiertas = []
        vistos = 0
        aviso = False

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    cerrarFases(abiertas)
                    showStats()
                    pygame.quit()
                    sys.exit()

            # M3. apertura y cierre del verde, un registro POR ACCESO
            key = (currentFase, currentPhase)
            if key != prev_key:
                if currentPhase == 'green':
                    abiertas = [{
                        'escenario': ESCENARIO,
                        'diseno_ciclo': DISENO_CICLO,
                        'semilla': RANDOM_SEED,
                        'verde_s': VERDE,
                        'fase': NOMBRE_FASE[currentFase],
                        'direccion': d,
                        'verde_inicio_s': round(simClock, 3),
                        'cola_al_inicio': queueLength(d),
                        'primer_cruce_s': None,
                        'start_up_lost_s': None,
                    } for d in FASES[currentFase]]
                elif abiertas:
                    cerrarFases(abiertas)
                    abiertas = []
                prev_key = key

            screen.blit(background, (0, 0))

            # Los cuatro semaforos leen el estado de SU fase
            restante = max(0.0, intervaloFin - simClock)
            for i in range(4):
                d = directionNumbers[i]
                if FASE_DE[d] == currentFase:
                    if currentPhase == 'green':
                        screen.blit(greenSignal, signalCoods[i])
                    elif currentPhase in ('amber_start', 'amber_clear'):
                        screen.blit(amberSignal, signalCoods[i])
                    else:
                        screen.blit(redSignal, signalCoods[i])
                    texto = "%.0f" % restante
                else:
                    screen.blit(redSignal, signalCoods[i])
                    texto = "---"
                screen.blit(font.render(texto, True, white, black), signalTimerCoods[i])

            for vehicle in simulation:
                screen.blit(vehicle.image, [vehicle.x, vehicle.y])
                vehicle.update_vehicle(dt)
                if MOSTRAR_IDLE_EN_PANTALLA and vehicle.crossed == 0 and vehicle.idle_time > 0.5:
                    screen.blit(fontSmall.render("%.0fs" % vehicle.idle_time, True, white),
                                (vehicle.x, vehicle.y - 18))

            for reg in abiertas:
                if reg['primer_cruce_s'] is None:
                    for r in vehicleRecords[vistos:]:
                        if r['direccion'] == reg['direccion']:
                            reg['primer_cruce_s'] = r['cruce_s']
                            reg['start_up_lost_s'] = round(
                                r['cruce_s'] - reg['verde_inicio_s'], 3)
                            break
            vistos = len(vehicleRecords)

            sult = [p['start_up_lost_s'] for p in phaseRecords
                    if p['start_up_lost_s'] is not None]
            panel = [
                "%s  /  ciclo %s  (%.0f s)" % (ESCENARIO, DISENO_CICLO, DURACION_CICLO),
                "Fase activa: %-11s  %s" % (
                    NOMBRE_FASE[currentFase], ETIQUETA_INTERVALO[currentPhase]),
                "Right %d   Down %d   Left %d   Up %d" % (
                    lane_counters['right'], lane_counters['down'],
                    lane_counters['left'], lane_counters['up']),
                "Idle promedio  : %.2f s" % promedio([r['idle_time_s'] for r in vehicleRecords]),
                "Start-up lost  : %.2f s  (%d accesos)" % (promedio(sult), len(sult)),
            ]
            for i, linea in enumerate(panel):
                screen.blit(font.render(linea, True, white, black), (20, 20 + i * 28))

            screen.blit(font.render("Tiempo: %.0f s" % simClock, True, black, white),
                        timeElapsedCoods)

            simClock += dt
            if not aviso and wallElapsed > 15 and simClock < wallElapsed - 3:
                print("NOTA: la maquina no sostiene %d fps, la corrida tardara mas"
                      " de %d s reales." % (FPS, SIMULATION_TIME))
                print("      Los resultados siguen siendo validos y reproducibles.")
                aviso = True

            pygame.display.update()
            clock.tick(FPS)

            if simClock >= SIMULATION_TIME:
                cerrarFases(abiertas)
                showStats()
                pygame.quit()
                os._exit(0)


# ======================================================================
# NOTA S1 - por que no hay coordenada de parada por vehiculo
# ======================================================================
# El codigo original calculaba self.stop al nacer el vehiculo, en funcion
# de quien tuviera adelante, y nunca lo recalculaba: la cola no se
# compactaba entre ciclos.
#
# Reiniciar esas coordenadas al empezar cada turno arreglaba la cola pero
# introducia un sesgo, porque en AMBER el reinicio ocurria antes que en
# CONTROL y los vehiculos podian avanzar en esa ventana. Ventaja
# artificial para el escenario que se quiere probar.
#
# La solucion de fondo es no tener coordenada por vehiculo: la linea de
# parada es la misma para todos y la separacion la resuelve hasRoom()
# frame a frame. Sin estado congelado no hay nada que reiniciar, y no hay
# ventana asimetrica.
#
# NOTA S2 - representacion visual del rojo+ambar
# ======================================================================
# Durante el intervalo 'amber_start' la interseccion real muestra rojo y
# ambar encendidos a la vez. Las imagenes disponibles son cabezas de
# semaforo completas, una por color, asi que en pantalla se muestra el
# ambar y el panel indica ROJO+AMBAR. Es solo presentacion: la logica de
# derecho de paso no cambia, hasGreen() solo es verdadero en verde.
# ======================================================================

if __name__ == '__main__':
    Main()
