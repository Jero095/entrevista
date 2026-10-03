# Dataset de alarmas (CSV legacy)

Generado por `data_generation/generate_dataset.py` (reproducible con `--seed`).
Simula la exportación del *alarm journal* de un SCADA legacy.

## Modelo conceptual

Cada **fila es un evento** del ciclo de vida de una alarma según ISA-18.2 / IEC 62682:

```
ACTIVE  (la variable cruza el límite)
  └─► ACK   (la alarma es reconocida en la HMI)   — opcional
        └─► RTN (la variable vuelve a normal)     — opcional (alarmas aún activas)
```

Una alarma genera de 1 a 3 filas. Por eso se pueden calcular métricas como el
tiempo hasta el reconocimiento (*time to acknowledge*) o la duración de la alarma.

## Columnas

| Columna       | Significado                                   | Valor canónico esperado                     |
|---------------|-----------------------------------------------|---------------------------------------------|
| `id_evento`   | ID del evento en el sistema origen            | entero único                                |
| `timestamp`   | Momento del evento                            | datetime UTC                                |
| `tag`         | Identificador del instrumento (nomenclatura ISA) | `PT-101`, `TT-301`…                      |
| `descripcion` | Descripción del instrumento                   | texto                                       |
| `area`        | Área de planta                                | Bombeo, Tanques, Reactor, Compresión, Servicios |
| `tipo_alarma` | Condición de alarma                           | HI, HIHI, LO, LOLO, DEV, ROC, DISC          |
| `criticidad`  | Criticidad (4 niveles, ISA-18.2)              | CRITICAL, HIGH, MEDIUM, LOW                 |
| `estado`      | Transición del ciclo de vida                  | ACTIVE, ACK, RTN                            |
| `valor`       | Valor de la variable en el evento             | decimal                                     |
| `limite`      | Límite (setpoint de alarma) configurado       | decimal                                     |
| `unidad`      | Unidad de ingeniería                          | bar, °C, %, m3/h…                           |

Prefijos de tag: `PT` presión, `TT` temperatura, `FT` flujo, `LT` nivel,
`AT` analizador, `VT` vibración, `ZS` posición/estado, `ET` corriente.

## Defectos inyectados intencionalmente

| Defecto | Ejemplos | Tratamiento esperado en la ingesta |
|---|---|---|
| Fechas en formatos heterogéneos | `2026-07-02T00:12:14Z`, `02/07/2026 19:11:05`, `07-01-2026 07:11:05 PM`, `2026-07-01T20:02:24.408-05:00`, epoch s/ms, `20260702T010413Z` | Parsear y normalizar a UTC |
| Fechas inválidas o nulas | `N/A`, `31/02/2026 10:00:00`, `##########`, vacío | Rechazar la fila; se guarda en `evento_rechazado` con el motivo |
| Tags sucios | `tt 301`, ` PT-101 `, `PT_101`, `PT101` | Normalizar a `XX-NNN` |
| Tag nulo | vacío | Rechazar (no se puede atribuir) |
| Criticidad con sinónimos | `Alta`, `P1`, `3`, `crit`, `Urgent` | Mapear al valor canónico |
| Criticidad nula | vacío | Completar con la criticidad configurada en el catálogo |
| Estado con sinónimos | `ACT`, `ALM`, `ACKED`, `Cleared`, `OK` | Mapear a ACTIVE/ACK/RTN |
| Valor con formato raro | `85,30`, `2.442e+01`, `6.960000  ` | Convertir a decimal |
| Valor con mala calidad | `Bad Quality`, `#####`, `NaN`, `COMM FAIL` | `NULL` + marcar calidad mala |
| Área nula | vacío, `NULL`, `null`, `-` | Se ignora: el área sale del catálogo del tag |
| Duplicados exactos | mismo `id_evento` repetido | Deduplicar |
| BOM UTF-8 al inicio del archivo | `﻿id_evento` | Leer con `utf-8-sig` |

## Supuestos

- **Zona horaria**: la planta opera en UTC-5. Los formatos *sin offset* que
  vienen de la HMI local (`dd/mm/yyyy` y `mm-dd-yyyy hh:mm:ss AM/PM`) están en hora
  local. Los que empiezan por el año (`yyyy-mm-dd HH:MM:SS`, `yyyy/mm/dd HH:MM:SS.fff`)
  vienen del servidor histórico y están en UTC, igual que epoch y los formatos con `Z`.
- **Ambigüedad día/mes**: se distingue por el separador (`/` = día primero, `-` =
  estilo US). Es un supuesto documentado: en un caso real habría que confirmarlo
  con el cliente para cada fuente de datos.
- **Distribución**: unos pocos tags *bad actors* (PT-101, FT-201, VT-401)
  concentran la mayoría de los eventos, como pasa en planta real (patrón de Pareto
  en ISA-18.2). Así el endpoint de "top tags" da resultados significativos.
- **Reconocimiento**: las alarmas CRITICAL se reconocen casi siempre y rápido; las LOW
  quedan sin reconocer con frecuencia (refleja *alarm floods*).

## Fuente plana → modelo normalizado

El CSV es intencionalmente plano y redundante: cada evento repite la descripción,
el área, la unidad, el tipo y el límite. Así exportan los SCADA legacy, y la fuente
no es nuestra para cambiarla. **La normalización ocurre en la ingesta**, no en la fuente.

| Dato del CSV | Pertenece a | Destino en la BD |
|---|---|---|
| `descripcion`, `unidad`, `area` | el instrumento | tablas `tag` y `area` |
| `tipo_alarma` | la alarma (un tag puede tener varias) | tabla `alarma`; en el evento solo sirve para identificar *cuál* alarma |
| `limite`, `criticidad` configurada | la configuración de la alarma, que puede cambiar con el tiempo | tabla `alarma_config` (versionada) |
| `id_evento`, `timestamp`, `estado`, `valor`, `criticidad` | el evento | tabla `evento_alarma` |

La configuración de la planta viene de [`config/alarm_catalog.csv`](../config/alarm_catalog.csv)
(el *Master Alarm Database* de ISA-18.2), no se deduce del CSV de eventos. El ETL
compara el `limite` y la `unidad` de cada evento contra el catálogo y avisa si no
coinciden, pero manda el catálogo.

### Resultado de la limpieza sobre el dataset (semilla 42)

| | Filas |
|---|---|
| Leídas | 22 421 |
| Duplicadas (descartadas) | 415 |
| Válidas | 21 443 |
| Rechazadas | 563 (242 fechas inválidas, 220 fechas vacías, 103 tags vacíos; 2 filas tenían dos defectos) |
| Criticidad completada desde el catálogo | 655 |
| Valor marcado como `BAD` / vacío | 690 / 652 |
