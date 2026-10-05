import { useEffect, useState } from 'react'
import { useApi } from '../hooks/useApi'
import type { LoteCarga, RechazosLote } from '../api/types'
import { RequestPanel } from '../components/RequestPanel'
import { BarList, Button, Card, Field } from '../components/ui'
import { inputClass } from '../components/styles'
import { formatFechaUtc, formatNumero } from '../format'
import { useRequest } from '../hooks/useRequest'

export function CalidadDatos() {
  const { call } = useApi()
  const lotes = useRequest<LoteCarga[]>()
  const rechazos = useRequest<RechazosLote>()
  const [loteId, setLoteId] = useState('')
  const [limit, setLimit] = useState(20)

  const cargarLotes = lotes.run
  const cargarRechazos = rechazos.run

  useEffect(() => {
    cargarLotes(() => call<LoteCarga[]>('/api/v1/etl/lotes', { limit: 20 }))
    cargarRechazos(() => call<RechazosLote>('/api/v1/etl/rechazados', { limit: 20 }))
  }, [call, cargarLotes, cargarRechazos])

  const consultarRechazos = (lote: string, cantidad: number) =>
    cargarRechazos(() => call<RechazosLote>('/api/v1/etl/rechazados', { lote_id: lote, limit: cantidad }))

  // La primera carga sobre una base vacía es la que muestra la limpieza completa;
  // las siguientes reportan "ya existían" (la carga es idempotente).
  const primeraCarga = lotes.result?.data?.filter((l) => l.estado === 'OK').at(-1)

  return (
    <div className="flex flex-col gap-6">
      <Card
        title="Cargas del ETL"
        info="GET /api/v1/etl/lotes — cada ejecución del ETL queda registrada con su resultado. Si se ejecuta dos veces sobre el mismo archivo, la segunda carga 0 eventos nuevos: la carga es idempotente."
        description="Qué pasó con las filas del CSV en cada ejecución."
        actions={<Button variant="secondary" disabled={lotes.loading} onClick={() => cargarLotes(() => call<LoteCarga[]>('/api/v1/etl/lotes', { limit: 20 }))}>Actualizar</Button>}
      >
        {primeraCarga && (
          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Cifra label="Filas leídas del CSV" valor={primeraCarga.filas_leidas} />
            <Cifra label="Duplicadas descartadas" valor={primeraCarga.filas_duplicadas} />
            <Cifra label="Rechazadas (con motivo)" valor={primeraCarga.filas_rechazadas} tono="text-amber-700" />
            <Cifra label="Cargadas limpias" valor={(primeraCarga.filas_cargadas ?? 0) + (primeraCarga.filas_ya_cargadas ?? 0)} tono="text-teal-700" />
          </div>
        )}

        <RequestPanel result={lotes.result} loading={lotes.loading} />

        {lotes.result?.data && (
          <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500">
                <tr>
                  {['Lote', 'Inicio (UTC)', 'Estado', 'Leídas', 'Duplicadas', 'Ya existían', 'Cargadas', 'Rechazadas'].map((h) => (
                    <th key={h} className="whitespace-nowrap px-3 py-2 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 tabular-nums">
                {lotes.result.data.map((l) => (
                  <tr key={l.id} className="hover:bg-slate-50">
                    <td className="px-3 py-2 font-medium">{l.id}</td>
                    <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">{formatFechaUtc(l.inicio)}</td>
                    <td className="px-3 py-2" title={l.mensaje_error ?? undefined}>{l.estado}</td>
                    <td className="px-3 py-2">{formatNumero(l.filas_leidas)}</td>
                    <td className="px-3 py-2">{formatNumero(l.filas_duplicadas)}</td>
                    <td className="px-3 py-2">{formatNumero(l.filas_ya_cargadas)}</td>
                    <td className="px-3 py-2">{formatNumero(l.filas_cargadas)}</td>
                    <td className="px-3 py-2">{formatNumero(l.filas_rechazadas)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card
        title="Filas rechazadas"
        info="GET /api/v1/etl/rechazados — las filas que el ETL no pudo limpiar no se pierden: se guardan tal como venían en el CSV, con el motivo. Solo se rechaza lo que obligaría a inventar datos (fecha N/A, tag vacío)."
        description="Motivos de rechazo y una muestra de las filas originales del CSV."
        actions={<Button variant="secondary" onClick={() => { setLoteId(''); setLimit(20); consultarRechazos('', 20) }}>Datos de ejemplo</Button>}
      >
        <form
          className="flex flex-wrap items-end gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            consultarRechazos(loteId.trim(), limit)
          }}
        >
          <div className="w-48">
            <Field label="Lote" htmlFor="re-lote" info="Número de lote (ver la tabla de cargas). Vacío = la última carga exitosa.">
              <input id="re-lote" className={inputClass} placeholder="última" value={loteId} onChange={(e) => setLoteId(e.target.value)} />
            </Field>
          </div>
          <div className="w-48">
            <Field label="Filas de muestra" htmlFor="re-limit" info="Cuántas filas rechazadas mostrar, entre 1 y 100.">
              <input id="re-limit" type="number" min={1} max={100} className={inputClass} value={limit} onChange={(e) => setLimit(Number(e.target.value))} />
            </Field>
          </div>
          <Button type="submit" disabled={rechazos.loading}>Consultar</Button>
        </form>

        <RequestPanel result={rechazos.result} loading={rechazos.loading} />

        {rechazos.result?.data && (
          <div className="mt-4 flex flex-col gap-4">
            <div>
              <h3 className="mb-2 text-sm font-medium text-slate-700">
                Lote {rechazos.result.data.lote_id}: {formatNumero(rechazos.result.data.total)} filas rechazadas por motivo
              </h3>
              <BarList items={rechazos.result.data.motivos.map((m) => ({ label: m.motivo, value: m.total, color: 'bg-amber-500', hint: m.motivo }))} />
            </div>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500">
                  <tr>
                    <th className="px-3 py-2 font-medium">Motivo</th>
                    <th className="px-3 py-2 font-medium">Fila original del CSV</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {rechazos.result.data.items.map((r) => (
                    <tr key={r.id} className="align-top">
                      <td className="px-3 py-2 text-amber-800">{r.motivo}</td>
                      <td className="px-3 py-2 font-mono text-xs">
                        <FilaOriginal fila={r.fila_original} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}

function Cifra({ label, valor, tono = 'text-slate-900' }: { label: string; valor: number | null; tono?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`text-xl font-semibold tabular-nums ${tono}`}>{formatNumero(valor)}</div>
    </div>
  )
}

/** Muestra los campos de la fila; los vacíos se marcan para que se vea qué faltaba. */
function FilaOriginal({ fila }: { fila: Record<string, string> | string }) {
  if (typeof fila === 'string') return <span>{fila}</span>
  return (
    <span className="flex flex-wrap gap-x-3 gap-y-1">
      {Object.entries(fila).map(([campo, valor]) => (
        <span key={campo}>
          <span className="text-slate-400">{campo}=</span>
          {valor === '' ? <span className="rounded bg-amber-100 px-1 text-amber-800">vacío</span> : <span>{valor}</span>}
        </span>
      ))}
    </span>
  )
}
