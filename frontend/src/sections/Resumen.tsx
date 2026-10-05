import { useEffect, useState } from 'react'
import type { ApiContextValue } from '../api/apiContext'
import { useApi } from '../hooks/useApi'
import type { ApiResult } from '../api/client'
import type { AlarmaEvento, LoteCarga, Pagina, ResumenCriticidad, TagCatalogo, TopTagsRespuesta } from '../api/types'
import { RequestPanel } from '../components/RequestPanel'
import { BarList, Button, Card, Kpi } from '../components/ui'
import { criticidadBarClass } from '../components/styles'
import { formatNumero } from '../format'
import type { Seccion } from '../secciones'

interface Datos {
  eventos: ApiResult<Pagina<AlarmaEvento>>
  criticidad: ApiResult<ResumenCriticidad>
  top: ApiResult<TopTagsRespuesta>
  tags: ApiResult<TagCatalogo[]>
  lotes: ApiResult<LoteCarga[]>
}

async function obtenerResumen(call: ApiContextValue['call']): Promise<Datos> {
  const [eventos, criticidad, top, tags, lotes] = await Promise.all([
    call<Pagina<AlarmaEvento>>('/api/v1/alarmas', { size: 1 }),
    call<ResumenCriticidad>('/api/v1/metricas/por-criticidad'),
    call<TopTagsRespuesta>('/api/v1/metricas/top-tags', { limit: 5 }),
    call<TagCatalogo[]>('/api/v1/tags'),
    call<LoteCarga[]>('/api/v1/etl/lotes', { limit: 100 }),
  ])
  return { eventos, criticidad, top, tags, lotes }
}

export function Resumen({ irA }: { irA: (seccion: Seccion) => void }) {
  const { call } = useApi()
  const [datos, setDatos] = useState<Datos | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Si el usuario cambia de sección antes de que termine la carga, se ignora la respuesta.
    let activo = true
    obtenerResumen(call).then((d) => {
      if (activo) {
        setDatos(d)
        setLoading(false)
      }
    })
    return () => {
      activo = false
    }
  }, [call])

  const reintentar = () => {
    setLoading(true)
    obtenerResumen(call).then((d) => {
      setDatos(d)
      setLoading(false)
    })
  }

  if (loading && !datos) return <p className="animate-pulse text-sm text-slate-500">Cargando resumen…</p>
  if (!datos) return null

  // Si alguna consulta falló (API apagada, clave incorrecta), se muestra el error en lugar de cifras vacías.
  const fallida = Object.values(datos).find((r) => !r.ok)
  if (fallida) {
    return (
      <Card title="No se pudo cargar el resumen" actions={<Button onClick={reintentar} disabled={loading}>Reintentar</Button>}>
        <RequestPanel result={fallida} loading={false} />
      </Card>
    )
  }

  const primeraCarga = datos.lotes.data?.filter((l) => l.estado === 'OK').at(-1)

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi label="Eventos cargados" value={formatNumero(datos.eventos.data?.total)} sub="ACTIVE, ACK y RTN"
          info="Total de eventos en la base (cada alarma genera hasta 3: ACTIVE, ACK y RTN). Viene del campo 'total' de GET /api/v1/alarmas." />
        <Kpi label="Alarmas" value={formatNumero(datos.criticidad.data?.total)} sub="veces que saltó una alarma"
          info="Eventos ACTIVE: cuántas veces se activó una alarma. Viene de GET /api/v1/metricas/por-criticidad." />
        <Kpi label="Instrumentos" value={formatNumero(datos.tags.data?.length)} sub="en el catálogo de planta"
          info="Tags configurados en el catálogo (config/alarm_catalog.csv). Viene de GET /api/v1/tags." />
        <Kpi label="Filas rechazadas" value={formatNumero(primeraCarga?.filas_rechazadas)} sub={`de ${formatNumero(primeraCarga?.filas_leidas)} leídas del CSV`}
          info="Filas del CSV sin arreglo posible (fecha imposible, tag vacío). Se guardan con su motivo. Viene de GET /api/v1/etl/lotes." />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Alarmas por criticidad" info="Distribución de las alarmas según su urgencia (4 niveles de ISA-18.2)."
          actions={<Button variant="ghost" onClick={() => irA('criticidad')}>Explorar →</Button>}>
          <BarList items={(datos.criticidad.data?.items ?? []).map((i) => ({ label: i.criticidad, value: i.total, color: criticidadBarClass[i.criticidad] }))} />
        </Card>
        <Card title="Top 5 tags" info="Los instrumentos que más alarman ('bad actors'). Pocos tags concentran la mayoría de las alarmas."
          actions={<Button variant="ghost" onClick={() => irA('top')}>Explorar →</Button>}>
          <BarList items={(datos.top.data?.items ?? []).map((t) => ({ label: t.tag, value: t.total, hint: t.descripcion }))} />
        </Card>
      </div>

      <Card title="Cómo funciona" info="El recorrido de los datos de punta a punta.">
        <ol className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
          {[
            ['1. CSV legacy', 'Exportación del SCADA con fechas en 8 formatos, sinónimos, nulos y duplicados.'],
            ['2. ETL', 'Limpia y normaliza; rechaza con motivo lo que no tiene arreglo. Carga masiva e idempotente.'],
            ['3. SQL Server', 'Modelo normalizado con límites versionados e índices por tiempo y criticidad.'],
            ['4. API', 'FastAPI de solo lectura con validación, errores uniformes y API key.'],
          ].map(([titulo, texto]) => (
            <li key={titulo} className="rounded-lg border border-slate-200 p-3">
              <p className="font-medium text-slate-900">{titulo}</p>
              <p className="mt-1 text-slate-500">{texto}</p>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  )
}
