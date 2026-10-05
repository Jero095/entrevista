import { useState } from 'react'
import type { ApiResult } from '../api/client'

function statusClass(status: number): string {
  if (status >= 200 && status < 300) return 'bg-emerald-100 text-emerald-800'
  if (status >= 400 && status < 500) return 'bg-amber-100 text-amber-800'
  return 'bg-red-100 text-red-800'
}

/**
 * Muestra la petición HTTP realizada (método, URL, código, tiempo), el error
 * con el formato uniforme de la API, y la respuesta JSON completa a pedido.
 */
export function RequestPanel({ result, loading }: { result: ApiResult<unknown> | null; loading: boolean }) {
  const [verJson, setVerJson] = useState(false)

  if (loading) {
    return <p className="mt-4 animate-pulse text-sm text-slate-500">Consultando la API…</p>
  }
  if (!result) return null

  return (
    <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded bg-slate-700 px-1.5 py-0.5 font-mono font-semibold text-white">GET</span>
        <code className="min-w-0 flex-1 break-all font-mono text-slate-700">{decodeURIComponent(result.url)}</code>
        <span className={`rounded px-1.5 py-0.5 font-semibold ${statusClass(result.status)}`}>
          {result.status === 0 ? 'Sin respuesta' : `HTTP ${result.status}`}
        </span>
        <span className="text-slate-500">{result.ms} ms</span>
        <button
          type="button"
          onClick={() => setVerJson((v) => !v)}
          className="rounded px-1.5 py-0.5 font-medium text-teal-800 hover:bg-teal-100"
        >
          {verJson ? 'Ocultar JSON' : 'Ver JSON'}
        </button>
      </div>

      {result.error && (
        <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <p>
            <span className="font-mono font-semibold">{result.error.codigo}</span> · {result.error.mensaje}
          </p>
          {result.error.detalle && (
            <ul className="mt-1 list-disc pl-5 text-xs">
              {result.error.detalle.map((d, i) => (
                <li key={i}>
                  <span className="font-mono font-semibold">{d.campo}</span>: {d.mensaje}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {verJson && (
        <pre className="mt-3 max-h-96 overflow-auto rounded-md bg-slate-900 p-3 text-xs leading-relaxed text-slate-100">
          {typeof result.body === 'string' ? result.body : JSON.stringify(result.body, null, 2)}
        </pre>
      )}
    </div>
  )
}
