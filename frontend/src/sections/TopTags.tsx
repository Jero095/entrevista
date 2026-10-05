import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import { CRITICIDADES, type Criticidad, type TopTagsRespuesta } from '../api/types'
import { RequestPanel } from '../components/RequestPanel'
import { BarList, Button, Card, EjemploNota, Field } from '../components/ui'
import { inputClass } from '../components/styles'
import { TOP_TAGS_EJEMPLO, TOP_TAGS_EJEMPLO_TEXTO, TOP_TAGS_VACIO, type FiltrosTopTags } from '../ejemplos'
import { aIsoUtc } from '../format'
import { useRequest } from '../hooks/useRequest'

export function TopTags() {
  const { call } = useApi()
  const [filtros, setFiltros] = useState<FiltrosTopTags>(TOP_TAGS_VACIO)
  const { result, loading, run } = useRequest<TopTagsRespuesta>()

  const set = <K extends keyof FiltrosTopTags>(campo: K, valor: FiltrosTopTags[K]) =>
    setFiltros((f) => ({ ...f, [campo]: valor }))

  const consultar = (f: FiltrosTopTags = filtros) =>
    run(() =>
      call<TopTagsRespuesta>('/api/v1/metricas/top-tags', {
        desde: aIsoUtc(f.desde),
        hasta: aIsoUtc(f.hasta),
        limit: f.limit,
        contar: f.contar,
        criticidad_min: f.criticidad_min,
      }),
    )

  return (
    <Card
      title="Top tags"
      info="GET /api/v1/metricas/top-tags — endpoint de agregación: ranking de instrumentos por número de alarmas. Los primeros son los 'bad actors' de ISA-18.2, candidatos a revisión."
      description="Qué instrumentos generan más alarmas."
      actions={
        <>
          <Button variant="secondary" onClick={() => { setFiltros(TOP_TAGS_EJEMPLO); consultar(TOP_TAGS_EJEMPLO) }}>Datos de ejemplo</Button>
          <Button variant="ghost" onClick={() => setFiltros(TOP_TAGS_VACIO)}>Limpiar</Button>
        </>
      }
    >
      {filtros === TOP_TAGS_EJEMPLO && <EjemploNota>{TOP_TAGS_EJEMPLO_TEXTO}</EjemploNota>}

      <form
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5"
        onSubmit={(e) => {
          e.preventDefault()
          consultar()
        }}
      >
        <Field label="Desde (UTC)" htmlFor="tt-desde" info="Inicio del rango, incluido. Vacío = desde el primer dato.">
          <input id="tt-desde" type="datetime-local" className={inputClass} value={filtros.desde} onChange={(e) => set('desde', e.target.value)} />
        </Field>
        <Field label="Hasta (UTC)" htmlFor="tt-hasta" info="Fin del rango, no incluido. Vacío = hasta el último dato.">
          <input id="tt-hasta" type="datetime-local" className={inputClass} value={filtros.hasta} onChange={(e) => set('hasta', e.target.value)} />
        </Field>
        <Field label="Cantidad de tags" htmlFor="tt-limit" info="Cuántos tags devolver, entre 1 y 50.">
          <input id="tt-limit" type="number" min={1} max={50} className={inputClass} value={filtros.limit} onChange={(e) => set('limit', Number(e.target.value))} />
        </Field>
        <Field label="Contar" htmlFor="tt-contar" info="'alarmas' cuenta solo los eventos ACTIVE (veces que saltó la alarma). 'eventos' cuenta todas las transiciones (ACTIVE, ACK y RTN): cada alarma puede sumar hasta 3.">
          <select id="tt-contar" className={inputClass} value={filtros.contar} onChange={(e) => set('contar', e.target.value as FiltrosTopTags['contar'])}>
            <option value="alarmas">alarmas</option>
            <option value="eventos">eventos</option>
          </select>
        </Field>
        <Field label="Criticidad mínima" htmlFor="tt-cmin" info="Contar solo alarmas de esta criticidad o superior.">
          <select id="tt-cmin" className={inputClass} value={filtros.criticidad_min} onChange={(e) => set('criticidad_min', e.target.value as Criticidad | '')}>
            <option value="">— cualquiera —</option>
            {CRITICIDADES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </Field>
        <div>
          <Button type="submit" disabled={loading}>Consultar</Button>
        </div>
      </form>

      <RequestPanel result={result} loading={loading} />

      {result?.data && (
        <div className="mt-4">
          <BarList
            items={result.data.items.map((t) => ({
              label: <><span className="font-medium">{t.tag}</span> <span className="text-xs text-slate-500">{t.area}</span></>,
              value: t.total,
              hint: t.descripcion,
            }))}
          />
        </div>
      )}
    </Card>
  )
}
