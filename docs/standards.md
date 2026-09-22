# Duraciones de fase: de donde salen los numeros

Las duraciones no son inventadas. Vienen de normativa publicada.

## Ambar de arranque (rojo + ambar, antes del verde)

Reino Unido, Department for Transport, Traffic Advisory Leaflet 1/06:

> "the red + amber signal at two seconds"
> "The standard period during which an amber signal is displayed is fixed at three seconds"

Maxwell & York (2005), citado en la propuesta original del capstone, reporta
intervalos rojo+ambar de 1.0, 1.5 y 2.0 s, y 3.0 s en Rusia.

**Valor usado: 2.0 s**

## Ambar de despeje (despues del verde)

Australia, Traffic Signal Standard TS001, basado en Austroads. Varia con el
limite de velocidad de la via:

| Limite | Ambar |
|---|---|
| 40 km/h | 3.0 s |
| 50 km/h | 4.0 s |
| 60 km/h | 4.0 s |
| 70 km/h | 4.5 s |
| 80 km/h | 5.0 s |
| 90 km/h | 5.5 s |
| 100 km/h | 6.0 s |
| 110 km/h | 6.5 s |

**Valor usado: 4.0 s**, correspondiente a via urbana de 50-60 km/h.

El todo-rojo peatonal tipico es de 2 s segun la misma norma. No esta modelado.

## Por que importa

El codigo original usaba un solo parametro de 5 s para las dos cosas. Cinco
segundos corresponden a 80 km/h, no a una interseccion urbana. Y el escenario
ambar no tenia ambar de despeje, o sea pasaba de verde directo a rojo, lo que
no ocurre en ninguna interseccion real y ademas le regalaba 5 s de ciclo
frente al control.

## Fuentes

- UK DfT, Traffic Advisory Leaflet 1/06, "General principles of traffic control
  by light signals"
- Traffic Signal Standard TS001, Department for Infrastructure and Transport,
  South Australia
