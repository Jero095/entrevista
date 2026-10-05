// Tipos de las respuestas de la API (ver api/schemas.py en el backend).

export type Criticidad = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type Estado = 'ACTIVE' | 'ACK' | 'RTN'

export const CRITICIDADES: Criticidad[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
export const ESTADOS: Estado[] = ['ACTIVE', 'ACK', 'RTN']

export interface AlarmaEvento {
  id: number
  id_evento_origen: number
  timestamp_utc: string
  tag: string
  descripcion: string
  area: string
  tipo_alarma: string
  criticidad: Criticidad
  estado: Estado
  valor: number | null
  calidad_valor: 'GOOD' | 'BAD' | null
  unidad: string | null
  limite: number
  desviacion_limite: number | null
}

export interface Pagina<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export interface TopTag {
  tag: string
  descripcion: string
  area: string
  total: number
}

export interface TopTagsRespuesta {
  contar: 'alarmas' | 'eventos'
  desde: string | null
  hasta: string | null
  items: TopTag[]
}

export interface ResumenCriticidad {
  desde: string | null
  hasta: string | null
  total: number
  items: { criticidad: Criticidad; nivel: number; total: number }[]
}

export interface TagCatalogo {
  tag: string
  descripcion: string
  area: string
  unidad: string | null
  alarmas: { tipo_alarma: string; limite: number; criticidad: Criticidad; vigente_desde: string }[]
}

export interface LoteCarga {
  id: number
  archivo: string
  inicio: string
  fin: string | null
  estado: 'EN_CURSO' | 'OK' | 'ERROR'
  mensaje_error: string | null
  filas_leidas: number | null
  filas_duplicadas: number | null
  filas_ya_cargadas: number | null
  filas_cargadas: number | null
  filas_rechazadas: number | null
}

export interface RechazosLote {
  lote_id: number
  total: number
  motivos: { motivo: string; total: number }[]
  items: { id: number; motivo: string; fila_original: Record<string, string> | string }[]
}

export interface Health {
  estado: string
  base_de_datos: string
}

export interface ErrorRespuesta {
  error: {
    codigo: string
    mensaje: string
    detalle: { campo: string; mensaje: string }[] | null
  }
}
