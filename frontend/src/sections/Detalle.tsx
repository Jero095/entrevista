import { useEffect, useState, type ReactNode } from 'react'
import { useApi } from '../hooks/useApi'
import type { AlarmaEvento } from '../api/types'
import { RequestPanel } from '../components/RequestPanel'
import { Button, Card, CriticidadBadge, EjemploNota, Field } from '../components/ui'
import { inputClass } from '../components/styles'
import { DETALLE_EJEMPLO } from '../ejemplos'
import { formatFechaUtc, formatNumero } from '../format'
import { useRequest } from '../hooks/useRequest'

export function Detalle({ idInicial }: { idInicial: number | null }) {
  const { call } = useApi()
  const [id, setId] = useState(idInicial ? String(idInicial) : '')
  const [esEjemplo, setEsEjemplo] = useState(false)
  const { result, loading, run } = useRequest<AlarmaEvento>()

  const consultar = (valor: string) => run(() => call<AlarmaEvento>(`/api/v1/alarmas/${encodeURIComponent(valor.trim())}`))

  useEffect(() => {
    // Al llegar desde la tabla de alarmas ("Detalle") se consulta de inmediato.
    if (idInicial) {
      run(() => call<AlarmaEvento>(`/api/v1/alarmas/${idInicial}`))
    }
  }, [idInicial, call, run])

  const evento = result?.data

  return (
    <Card
      title="Detalle de un evento"
      info="GET /api/v1/alarmas/{id} — un evento por su id interno. Si no existe responde 404; si el id no es un entero positivo, 422."
      description="También puedes llegar aquí con el botón 'Detalle' de la tabla de alarmas."
      actions={
        <Button
          variant="secondary"
          onClick={() => {
            setId(String(DETALLE_EJEMPLO))
            setEsEjemplo(true)
            consultar(String(DETALLE_EJEMPLO))
          }}
        >
          Datos de ejemplo
        </Button>
      }
    >
      {esEjemplo && id === String(DETALLE_EJEMPLO) && <EjemploNota>el evento con id 1, el primero cargado por el ETL.</EjemploNota>}

      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault()
          if (id.trim()) consultar(id)
        }}
      >
        <div className="w-48">
          <Field label="Id del evento" htmlFor="det-id" info="Id interno de la base de datos (columna 'id'), no el id del SCADA (id_evento_origen). Prueba con 0 o con texto para ver la validación (422).">
            <input id="det-id" className={inputClass} value={id} onChange={(e) => { setId(e.target.value); setEsEjemplo(false) }} placeholder="1" />
          </Field>
        </div>
        <Button type="submit" disabled={loading || !id.trim()}>Consultar</Button>
      </form>

      <RequestPanel result={result} loading={loading} />

      {evento && (
        <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-3 rounded-lg border border-slate-200 p-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <Dato label="Tag" valor={`${evento.tag} — ${evento.descripcion}`} />
          <Dato label="Área" valor={evento.area} />
          <Dato label="Fecha (UTC)" valor={formatFechaUtc(evento.timestamp_utc)} />
          <Dato label="Tipo de alarma" valor={evento.tipo_alarma} />
          <Dato label="Criticidad" valor={<CriticidadBadge value={evento.criticidad} />} />
          <Dato label="Estado" valor={evento.estado} />
          <Dato label="Valor" valor={`${formatNumero(evento.valor, 2)} ${evento.valor !== null ? evento.unidad ?? '' : ''}`} />
          <Dato label="Límite vigente" valor={`${formatNumero(evento.limite, 2)} ${evento.unidad ?? ''}`} />
          <Dato label="Desviación (valor − límite)" valor={formatNumero(evento.desviacion_limite, 4)} />
          <Dato label="Calidad del valor" valor={evento.calidad_valor ?? 'sin dato'} />
          <Dato label="Id en el SCADA de origen" valor={String(evento.id_evento_origen)} />
          <Dato label="Id interno" valor={String(evento.id)} />
        </dl>
      )}
    </Card>
  )
}

function Dato({ label, valor }: { label: string; valor: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="font-medium text-slate-900">{valor}</dd>
    </div>
  )
}
