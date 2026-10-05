import { useEffect } from 'react'
import { useApi } from '../hooks/useApi'
import type { TagCatalogo } from '../api/types'
import { RequestPanel } from '../components/RequestPanel'
import { Button, Card, CriticidadBadge } from '../components/ui'
import { formatNumero } from '../format'
import { useRequest } from '../hooks/useRequest'

export function Catalogo() {
  const { call } = useApi()
  const { result, loading, run } = useRequest<TagCatalogo[]>()

  const consultar = () => run(() => call<TagCatalogo[]>('/api/v1/tags'))

  useEffect(() => {
    run(() => call<TagCatalogo[]>('/api/v1/tags'))
  }, [call, run])

  return (
    <Card
      title="Catálogo de instrumentos"
      info="GET /api/v1/tags — la configuración de la planta (Master Alarm Database de ISA-18.2): instrumentos, unidad y la versión vigente de cada alarma. Viene de config/alarm_catalog.csv."
      description="La unidad pertenece al instrumento; el límite y la criticidad, a la alarma (y se versionan)."
      actions={<Button variant="secondary" onClick={consultar} disabled={loading}>Actualizar</Button>}
    >
      <RequestPanel result={result} loading={loading} />

      {result?.data && (
        <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500">
              <tr>
                {['Tag', 'Descripción', 'Área', 'Unidad', 'Tipo', 'Límite', 'Criticidad', 'Vigente desde'].map((h) => (
                  <th key={h} className="whitespace-nowrap px-3 py-2 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {result.data.flatMap((t) =>
                t.alarmas.map((a) => (
                  <tr key={`${t.tag}-${a.tipo_alarma}`} className="hover:bg-slate-50">
                    <td className="px-3 py-2 font-medium">{t.tag}</td>
                    <td className="px-3 py-2">{t.descripcion}</td>
                    <td className="px-3 py-2">{t.area}</td>
                    <td className="px-3 py-2">{t.unidad ?? <span className="text-slate-400">— (discreta)</span>}</td>
                    <td className="px-3 py-2">{a.tipo_alarma}</td>
                    <td className="px-3 py-2 tabular-nums">{formatNumero(a.limite, 2)}</td>
                    <td className="px-3 py-2"><CriticidadBadge value={a.criticidad} /></td>
                    <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">{a.vigente_desde.slice(0, 10)}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
