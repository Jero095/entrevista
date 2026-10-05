import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import type { ResumenCriticidad } from '../api/types'
import { RequestPanel } from '../components/RequestPanel'
import { BarList, Button, Card, EjemploNota, Field } from '../components/ui'
import { criticidadBarClass, inputClass } from '../components/styles'
import { POR_CRITICIDAD_EJEMPLO, POR_CRITICIDAD_EJEMPLO_TEXTO, RANGO_VACIO, type FiltrosRango } from '../ejemplos'
import { aIsoUtc, formatNumero } from '../format'
import { useRequest } from '../hooks/useRequest'

export function PorCriticidad() {
  const { call } = useApi()
  const [filtros, setFiltros] = useState<FiltrosRango>(RANGO_VACIO)
  const { result, loading, run } = useRequest<ResumenCriticidad>()

  const consultar = (f: FiltrosRango = filtros) =>
    run(() => call<ResumenCriticidad>('/api/v1/metricas/por-criticidad', { desde: aIsoUtc(f.desde), hasta: aIsoUtc(f.hasta) }))

  return (
    <Card
      title="Alarmas por criticidad"
      info="GET /api/v1/metricas/por-criticidad — cuántas alarmas (eventos ACTIVE) hubo de cada criticidad. Incluye las criticidades sin alarmas con total 0."
      description="Distribución de alarmas por nivel de urgencia."
      actions={
        <>
          <Button variant="secondary" onClick={() => { setFiltros(POR_CRITICIDAD_EJEMPLO); consultar(POR_CRITICIDAD_EJEMPLO) }}>Datos de ejemplo</Button>
          <Button variant="ghost" onClick={() => setFiltros(RANGO_VACIO)}>Limpiar</Button>
        </>
      }
    >
      {filtros === POR_CRITICIDAD_EJEMPLO && <EjemploNota>{POR_CRITICIDAD_EJEMPLO_TEXTO}</EjemploNota>}

      <form
        className="grid grid-cols-1 gap-4 sm:grid-cols-3"
        onSubmit={(e) => {
          e.preventDefault()
          consultar()
        }}
      >
        <Field label="Desde (UTC)" htmlFor="pc-desde" info="Inicio del rango, incluido. Vacío = desde el primer dato.">
          <input id="pc-desde" type="datetime-local" className={inputClass} value={filtros.desde} onChange={(e) => setFiltros((f) => ({ ...f, desde: e.target.value }))} />
        </Field>
        <Field label="Hasta (UTC)" htmlFor="pc-hasta" info="Fin del rango, no incluido. Vacío = hasta el último dato.">
          <input id="pc-hasta" type="datetime-local" className={inputClass} value={filtros.hasta} onChange={(e) => setFiltros((f) => ({ ...f, hasta: e.target.value }))} />
        </Field>
        <div className="flex items-end">
          <Button type="submit" disabled={loading}>Consultar</Button>
        </div>
      </form>

      <RequestPanel result={result} loading={loading} />

      {result?.data && (
        <div className="mt-4">
          <p className="mb-3 text-sm text-slate-600">
            <span className="font-semibold text-slate-900">{formatNumero(result.data.total)}</span> alarmas en total
          </p>
          <BarList items={result.data.items.map((i) => ({ label: i.criticidad, value: i.total, color: criticidadBarClass[i.criticidad] }))} />
        </div>
      )}
    </Card>
  )
}
