import type { Criticidad, Estado } from './api/types'

// Datos de ejemplo fijos para probar cada endpoint con un clic.
// Las fechas van en formato de <input type="datetime-local"> y se envían como UTC.

export interface FiltrosAlarmas {
  desde: string
  hasta: string
  tag: string
  criticidad: Criticidad[]
  criticidad_min: Criticidad | ''
  estado: Estado | ''
  size: number
}

export const ALARMAS_VACIO: FiltrosAlarmas = {
  desde: '', hasta: '', tag: '', criticidad: [], criticidad_min: '', estado: '', size: 20,
}

export const ALARMAS_EJEMPLO: FiltrosAlarmas = {
  desde: '2026-07-01T00:00',
  hasta: '2026-07-08T00:00',
  tag: 'pt_101', // escrito "sucio" a propósito: la API lo normaliza a PT-101
  criticidad: [],
  criticidad_min: 'HIGH',
  estado: '',
  size: 10,
}

export const ALARMAS_EJEMPLO_TEXTO =
  'eventos del tag pt_101 (la API lo normaliza a PT-101) con criticidad HIGH o superior, ' +
  'del 1 al 8 de julio de 2026. Resultado esperado: 324 eventos.'

export const DETALLE_EJEMPLO = 1

export interface FiltrosTopTags {
  desde: string
  hasta: string
  limit: number
  contar: 'alarmas' | 'eventos'
  criticidad_min: Criticidad | ''
}

export const TOP_TAGS_VACIO: FiltrosTopTags = { desde: '', hasta: '', limit: 10, contar: 'alarmas', criticidad_min: '' }

export const TOP_TAGS_EJEMPLO: FiltrosTopTags = {
  desde: '2026-08-01T00:00',
  hasta: '2026-09-01T00:00',
  limit: 5,
  contar: 'alarmas',
  criticidad_min: 'CRITICAL',
}

export const TOP_TAGS_EJEMPLO_TEXTO = 'los tags con más alarmas CRITICAL durante agosto de 2026 (hasta 5; solo 4 instrumentos de la planta son CRITICAL).'

export interface FiltrosRango {
  desde: string
  hasta: string
}

export const RANGO_VACIO: FiltrosRango = { desde: '', hasta: '' }
export const POR_CRITICIDAD_EJEMPLO: FiltrosRango = { desde: '2026-07-01T00:00', hasta: '2026-08-01T00:00' }
export const POR_CRITICIDAD_EJEMPLO_TEXTO = 'alarmas por criticidad durante julio de 2026.'
