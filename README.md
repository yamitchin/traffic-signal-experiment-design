# Traffic Signal Experiment Design

**Simulating an A/B test you cannot run on live infrastructure.**

Most of Europe shows red+amber before green. Australia, New Zealand, Canada and
South Africa do not. Does the extra phase actually improve traffic flow?

You cannot rewire Sydney's traffic signals to find out. There is no permission,
no budget, and a failed trial means collisions. When the intervention cannot be
tested in the field, the only option is to build a model that generates the
counterfactual data and run the experiment there.

This repository contains that model, the data it generated, and the analysis.

---

## TL;DR

The red-amber phase **eliminates 96% of start-up lost time** (Cohen's d = 8.6,
p < 1e-29). It does **not** improve throughput or delay, because it costs
2.0 seconds of cycle time to save 1.5 seconds of driver reaction.

That result **reverses the conclusion of my original MSc capstone**, which was
built on a confounded experiment and three metrics that measured nothing.

---

## Background

This started as my Master of Data Science capstone at Western Sydney University
in 2023 (INFO7016 / INFO7017, supervisor Paul Hurley). I revisited it in 2026,
audited my own experimental design, and found it could not support its own
conclusion.

What follows documents the rebuild. The original submission is not in this
repository.

---

## What was wrong with the original

### 1. The experiment was confounded

The two scenarios lived in separate files and had drifted apart in **six
parameters at once**:

| Parameter | Amber scenario | Control scenario |
|---|---|---|
| Perception-Reaction Time | **0 s** | **2 s** |
| Start-up time init | 2 | 4 |
| Stopping / moving gap | 15 px | 25 px |
| Green interval | fixed 10 s | random 10-20 s |
| Turning movements | no | yes, 40% |
| Vehicle selection | `randint(0,3)` | `random.choice(list)` |

No observed difference could be attributed to the amber phase.

Worse: `PRT = 0` in the treatment and `PRT = 2` in the control **encodes the
conclusion in the assumptions**. The entire hypothesis is that the amber phase
reduces effective reaction time, and that difference had been hard-coded.

**The fix is structural.** Two scenario files will always drift. One file with a
single switch cannot:

```python
# The only difference between the two arms:
if ESCENARIO == "AMBER":
    correrIntervalo('amber_start', AMBAR_ARRANQUE)   # red+amber, 2 s
    correrIntervalo('green', VERDE)
    correrIntervalo('amber_clear', AMBAR_DESPEJE)    # clearance, 4 s
else:
    correrIntervalo('green', VERDE)
    correrIntervalo('amber_clear', AMBAR_DESPEJE)
```

PRT is now the **same constant in both arms**. What differs is *when the driver
receives the cue*, with the amber, two seconds earlier. The difference in
start-up lost time emerges as a measured outcome instead of an input.

### 2. All three metrics measured something else

**Idle time was always zero.** Accumulated in one branch, wiped three lines later:

```python
self.idle_time += 1     # accumulate
...
if self.speed > 0:      # self.speed is a constant, never 0
    self.idle_time = 0  # reset every frame
```

**Start-up lost time was dead code.** Initialised to `2`, updated only under
`if self.start_up_time == 0`, a condition that never fired. The reported value
was `timeElapsed - 2`, the clock minus a constant.

**PRT never blocked movement.** The countdown sat *after* the block that had
already moved the vehicle.

### 3. Results were not reproducible

Signal timing ran on wall clock (`time.sleep(1)`) while vehicles moved per
frame with no framerate cap. On a slower machine the signals advanced faster
than the traffic, and results changed between computers.

### 4. The signal model was not an intersection

The original cycled all four approaches one at a time. Opposing movements are
not conflicting and run concurrently in any real intersection. The corrected
model uses two phases (North-South, East-West), which halves the cycle and
roughly doubles capacity.

---

## Results

Four runs: 2 scenarios x 2 cycle designs, 300 s each, identical seed.

| Metric | Amber | Control | Difference | p |
|---|---|---|---|---|
| **Start-up lost time** | **0.05 s** | **1.51 s** | **-96.5%** | 1.2e-29 |
| Vehicles cleared | 265 | 268 | -1.1% | ns |
| Idle time | 11.10 s | 9.84 s | +12.8% | 0.067 |
| Total delay | 23.90 s | 22.73 s | +5.1% | 0.258 |
| PRT consumed | 1.45 s | 1.39 s | +4.4% | ns |

### The mechanism: effective green

| Condition | Green | Phase | Cycle | Start-up | Effective green | % of cycle | Vehicles |
|---|---|---|---|---|---|---|---|
| Control / fixed cycle | 12 | 16 | 32 | 1.51 | **10.49** | **32.8%** | 268 |
| Amber / fixed cycle | 10 | 16 | 32 | 0.05 | 9.95 | 31.1% | 265 |
| Amber / extended | 10 | 16 | 32 | 0.06 | 9.94 | 31.1% | 266 |
| Control / extended | 10 | 14 | 28 | 1.54 | 8.46 | 30.2% | 264 |

Throughput follows effective green. The two amber conditions have identical
effective green and produced 265 and 266 vehicles.

### Break-even

```
Start-up lost time eliminated : 1.53 s
Cost of the starting amber    : 2.00 s
--------------------------------------
Net balance per phase         : -0.47 s   ->  LOSES
```

| Starting amber | Net balance | Outcome |
|---|---|---|
| 1.0 s | +0.53 s | gains |
| 1.5 s | +0.03 s | breaks even |
| 2.0 s (UK standard) | -0.47 s | loses |
| 3.0 s (Russia) | -1.47 s | loses |

> **The starting amber pays for itself only if it is shorter than the start-up
> lost time it removes.** At the UK's 2-second standard, against a 1.5-second
> driver reaction time, it is not.

---

## Limitations

Stated here rather than buried:

- **One replicate per condition.** The vehicle-level t-tests are
  pseudoreplication. The start-up effect is large enough to survive it. The
  throughput and delay differences are within noise and **not significant even
  with inflated power**. Proper inference needs N seeds compared at replicate
  level.
- **The intersection is saturated.** 88-89% of generated vehicles cleared, with
  queues growing throughout. Under saturation, capacity dominates and start-up
  matters less. Low-demand behaviour is untested.
- **No turning movements.** A protected left-turn phase would change the phase
  structure and the result.

---

## Running it

```bash
pip install -r requirements.txt
cd src
python fetch_assets.py     # pulls the sprites from the upstream repo, once
python simulator.py
```

The vehicle and signal images are not versioned here: they belong to the
upstream Apache-2.0 project, so `fetch_assets.py` downloads them instead.

Two lines control the experiment:

```python
ESCENARIO    = "AMBER"       # or "CONTROL"
DISENO_CICLO = "CONSTANTE"   # or "EXTENDIDO"
```

Each run writes `vehiculos_<scenario>_<design>_seed<N>.csv` and
`fases_<scenario>_<design>_seed<N>.csv`. Change `RANDOM_SEED` for a new replicate.

Analysis:

```bash
cd analysis
python analysis.py
```

**Note on pygame:** on Python 3.14 use `pygame-ce`, which ships prebuilt wheels.
Stock `pygame` 2.6.1 only publishes wheels up to cp313 and will try to compile
from source.

---

## Repository layout

```
src/simulator.py       the simulation, both scenarios, one code path
src/fetch_assets.py    downloads the sprites from the upstream repo
data/fases_*.csv       phase-level output, 146 records, the headline result
analysis/analysis.py   summary tables, tests, effective green, break-even
docs/standards.md      where the 2 s and 4 s intervals come from
```

The phase-level CSVs are committed because they carry the finding. The
vehicle-level CSVs are not: the simulation is seeded and deterministic, so
running the four configurations regenerates them byte for byte. That is a
stronger reproducibility claim than checking the output in.

### Data schema

`vehiculos_*.csv`, one row per vehicle that crossed:

| Column | Meaning |
|---|---|
| `escenario`, `diseno_ciclo`, `semilla`, `verde_s` | run configuration |
| `fase`, `direccion`, `carril`, `tipo` | phase group, approach, lane, vehicle class |
| `spawn_s`, `cruce_s` | spawn and stop-line crossing, in simulation seconds |
| `demora_total_s` | total delay |
| `idle_time_s` | accumulated seconds stopped |
| `prt_gastado_s` | perception-reaction seconds actually consumed |

`fases_*.csv`, one row per green phase per approach:

| Column | Meaning |
|---|---|
| `verde_inicio_s` | green onset |
| `cola_al_inicio` | queue length at onset |
| `primer_cruce_s` | first queued vehicle crossing the stop line |
| `start_up_lost_s` | `primer_cruce_s - verde_inicio_s` |

Phases with no queue are discarded: with nothing waiting there is no start-up
to measure.

---

## Domain calibration

Phase durations are not invented. They come from published standards:

| Interval | Value | Source |
|---|---|---|
| Red+amber (starting) | 2.0 s | UK DfT, Traffic Advisory Leaflet 1/06 |
| Amber (clearance) | 4.0 s | Australian Traffic Signal Standard TS001, 50-60 km/h |

TS001 clearance amber by posted speed: 40 km/h 3.0 s, 50-60 km/h 4.0 s,
70 km/h 4.5 s, 80 km/h 5.0 s, 100 km/h 6.0 s.

---

## Attribution

The simulation is built on the Pygame traffic simulator from **Gandhi, M.,
Solanki, D., Daptardar, R. & Baloorkar, N. (2020)**, *Smart Control of Traffic
Light Using Artificial Intelligence*, IEEE ICRAIE 2020:
[mihir-m-gandhi/Adaptive-Traffic-Signal-Timer](https://github.com/mihir-m-gandhi/Adaptive-Traffic-Signal-Timer),
Apache License 2.0. The sprite and signal images are from that project and are
fetched by `src/fetch_assets.py`.

Their code already used classes and multithreading. What is mine is the
red-amber-before-green phase ordering, the two-phase concurrent movement model,
the three instrumented metrics, the single-code-path experimental design, the
deterministic simulation clock, and the analysis.

---

## Why this is a data science project

It contains no model and no accuracy score. It is about the other half of the
discipline:

- **Experimental design**: identifying a six-parameter confound and fixing it
  structurally rather than by hand
- **Instrumentation**: validating that a metric measures what it claims
- **Reproducibility**: seeded, deterministic, machine-independent
- **Causal reasoning**: separating "the intervention has the stated effect" from
  "the intervention improves the outcome", which are different claims
- **Honest reporting**: a negative result, with the mechanism quantified and the
  limitations stated

Those are the skills that decide whether an analysis can be trusted.

---

**Yamit Chinchilla** - Data Analyst & Data Scientist
MSc Data Science, Western Sydney University
