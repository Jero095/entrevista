export type Seccion = 'resumen' | 'graficas' | 'alarmas' | 'detalle' | 'top' | 'criticidad' | 'catalogo' | 'calidad' | 'errores'

export const SECCIONES: { id: Seccion; titulo: string; endpoint: string }[] = [
  { id: 'resumen', titulo: 'Resumen', endpoint: 'Vista general' },
  { id: 'graficas', titulo: 'Gráficas', endpoint: 'Valor vs. tiempo y umbral' },
  { id: 'alarmas', titulo: 'Alarmas', endpoint: 'GET /alarmas' },
  { id: 'detalle', titulo: 'Detalle de evento', endpoint: 'GET /alarmas/{id}' },
  { id: 'top', titulo: 'Top tags', endpoint: 'GET /metricas/top-tags' },
  { id: 'criticidad', titulo: 'Por criticidad', endpoint: 'GET /metricas/por-criticidad' },
  { id: 'catalogo', titulo: 'Catálogo', endpoint: 'GET /tags' },
  { id: 'calidad', titulo: 'Calidad de datos', endpoint: 'GET /etl/…' },
  { id: 'errores', titulo: 'Pruebas de errores', endpoint: '422 · 404 · 401' },
]
