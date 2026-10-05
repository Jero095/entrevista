import { useEffect, useState } from 'react'
import { useApi } from '../hooks/useApi'
import { CRITICIDADES, ESTADOS, type AlarmaEvento, type Criticidad, type Estado, type Pagina, type TagCatalogo } from '../api/types'
import { RequestPanel } from '../components/RequestPanel'
import { Button, Card, CriticidadBadge, EjemploNota, Field } from '../components/ui'
import { inputClass } from '../components/styles'
import { ALARMAS_EJEMPLO, ALARMAS_EJEMPLO_TEXTO, ALARMAS_VACIO, type FiltrosAlarmas } from '../ejemplos'
import { aIsoUtc, formatFechaUtc, formatNumero } from '../format'
import { useRequest } from '../hooks/useRequest'

export function Alarmas({ onVerDetalle }: { onVerDetalle: (id: number) => void }) {
  const { call } = useApi()
  const [filtros, setFiltros] = useState<FiltrosAlarmas>(ALARMAS_VACIO)
  const [tags, setTags] = useState<string[]>([])
  const { result, loading, run } = useRequest<Pagina<AlarmaEvento>>()

  useEffect(() => {
    // Sugerencias para el campo tag (no impide escribir variantes "sucias" como pt_101).
    call<TagCatalogo[]>('/api/v1/tags').then((r) => setTags(r.data?.map((t) => t.tag) ?? []))
  }, [call])

  const set = <K extends keyof FiltrosAlarmas>(campo: K, valor: FiltrosAlarmas[K]) =>
    setFiltros((f) => ({ ...f, [campo]: valor }))

  const toggleCriticidad = (c: Criticidad) =>
    set('criticidad', filtros.criticidad.includes(c) ? filtros.criticidad.filter((x) => x !== c) : [...filtros.criticidad, c])

  const consultar = (page: number, f: FiltrosAlarmas = filtros) =>
    run(() =>
      call<Pagina<AlarmaEvento>>('/api/v1/alarmas', {
        desde: aIsoUtc(f.desde),
        hasta: aIsoUtc(f.hasta),
        tag: f.tag.trim(),
        criticidad: f.criticidad,
        criticidad_min: f.criticidad_min,
        estado: f.estado,
        page,
        size: f.size,
      }),
    )

  const usarEjemplo = () => {
    setFiltros(ALARMAS_EJEMPLO)
    consultar(1, ALARMAS_EJEMPLO)
  }

  const pagina = result?.data

  return (
    <Card
      title="Consultar alarmas"
      info="GET /api/v1/alarmas — eventos de alarma con filtros opcionales y combinables, paginados y ordenados del más reciente al más antiguo."
      description="Todos los filtros son opcionales. Deja un campo vacío para no filtrar por él."
      actions={
        <>
          <Button variant="secondary" onClick={usarEjemplo}>Datos de ejemplo</Button>
          <Button variant="ghost" onClick={() => setFiltros(ALARMAS_VACIO)}>Limpiar</Button>
        </>
      }
    >
      {filtros === ALARMAS_EJEMPLO && <EjemploNota>{ALARMAS_EJEMPLO_TEXTO}</EjemploNota>}

      <form
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
        onSubmit={(e) => {
          e.preventDefault()
          consultar(1)
        }}
      >
        <Field label="Desde (UTC)" htmlFor="al-desde" info="Inicio del rango, incluido. Se interpreta en UTC. Los datos van del 2 de julio al 30 de septiembre de 2026.">
          <input id="al-desde" type="datetime-local" className={inputClass} value={filtros.desde} onChange={(e) => set('desde', e.target.value)} />
        </Field>
        <Field label="Hasta (UTC)" htmlFor="al-hasta" info="Fin del rango, NO incluido. Debe ser posterior a 'Desde'; si no, la API responde 422.">
          <input id="al-hasta" type="datetime-local" className={inputClass} value={filtros.hasta} onChange={(e) => set('hasta', e.target.value)} />
        </Field>
        <Field label="Tag" htmlFor="al-tag" info="Código del instrumento (nomenclatura ISA-5.1, p. ej. PT-101 = transmisor de presión 101). Acepta variantes como pt_101 o PT101, igual que el ETL. Un tag inexistente devuelve 404.">
          <input id="al-tag" list="al-tags" className={inputClass} placeholder="PT-101" value={filtros.tag} onChange={(e) => set('tag', e.target.value)} />
          <datalist id="al-tags">
            {tags.map((t) => <option key={t} value={t} />)}
          </datalist>
        </Field>
        <Field label="Criticidad exacta" info="Una o varias criticidades exactas (se envía ?criticidad=LOW&criticidad=CRITICAL). No se puede combinar con 'Criticidad mínima': la API responde 422.">
          <div className="flex flex-wrap gap-3 py-1.5">
            {CRITICIDADES.map((c) => (
              <label key={c} className="flex items-center gap-1.5 text-sm">
                <input type="checkbox" className="accent-teal-700" checked={filtros.criticidad.includes(c)} onChange={() => toggleCriticidad(c)} />
                {c}
              </label>
            ))}
          </div>
        </Field>
        <Field label="Criticidad mínima" htmlFor="al-cmin" info="Esta criticidad o superior. Ejemplo: HIGH devuelve HIGH y CRITICAL. Orden: LOW < MEDIUM < HIGH < CRITICAL.">
          <select id="al-cmin" className={inputClass} value={filtros.criticidad_min} onChange={(e) => set('criticidad_min', e.target.value as Criticidad | '')}>
            <option value="">— cualquiera —</option>
            {CRITICIDADES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </Field>
        <Field label="Estado" htmlFor="al-estado" info="Paso del ciclo de vida (ISA-18.2): ACTIVE = la alarma saltó, ACK = el operador la reconoció, RTN = la variable volvió a lo normal.">
          <select id="al-estado" className={inputClass} value={filtros.estado} onChange={(e) => set('estado', e.target.value as Estado | '')}>
            <option value="">— cualquiera —</option>
            {ESTADOS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Resultados por página" htmlFor="al-size" info="Entre 1 y 500. La API limita el tamaño de página para que nadie pueda pedir todo el histórico de una vez.">
          <input id="al-size" type="number" min={1} max={500} className={inputClass} value={filtros.size} onChange={(e) => set('size', Number(e.target.value))} />
        </Field>
        <div className="flex items-end">
          <Button type="submit" disabled={loading}>Consultar</Button>
        </div>
      </form>

      <RequestPanel result={result} loading={loading} />

      {pagina && (
        <div className="mt-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm">
            <span className="text-slate-600">
              <span className="font-semibold text-slate-900">{formatNumero(pagina.total)}</span> eventos · página {pagina.page} de {Math.max(pagina.pages, 1)}
            </span>
            <div className="flex gap-2">
              <Button variant="ghost" disabled={loading || pagina.page <= 1} onClick={() => consultar(pagina.page - 1)}>← Anterior</Button>
              <Button variant="ghost" disabled={loading || pagina.page >= pagina.pages} onClick={() => consultar(pagina.page + 1)}>Siguiente →</Button>
            </div>
          </div>
          <TablaEventos eventos={pagina.items} onVerDetalle={onVerDetalle} />
        </div>
      )}
    </Card>
  )
}

function TablaEventos({ eventos, onVerDetalle }: { eventos: AlarmaEvento[]; onVerDetalle: (id: number) => void }) {
  if (eventos.length === 0) return <p className="text-sm text-slate-500">No hay eventos para estos filtros.</p>
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs text-slate-500">
          <tr>
            {['Fecha (UTC)', 'Tag', 'Tipo', 'Criticidad', 'Estado', 'Valor', 'Límite', 'Desviación', 'Calidad', ''].map((h) => (
              <th key={h} className="whitespace-nowrap px-3 py-2 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {eventos.map((e) => (
            <tr key={e.id} className="hover:bg-slate-50">
              <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">{formatFechaUtc(e.timestamp_utc)}</td>
              <td className="whitespace-nowrap px-3 py-2 font-medium" title={e.descripcion}>{e.tag}</td>
              <td className="px-3 py-2">{e.tipo_alarma}</td>
              <td className="px-3 py-2"><CriticidadBadge value={e.criticidad} /></td>
              <td className="px-3 py-2">{e.estado}</td>
              <td className="whitespace-nowrap px-3 py-2 tabular-nums">{formatNumero(e.valor, 2)} {e.valor !== null && e.unidad}</td>
              <td className="whitespace-nowrap px-3 py-2 tabular-nums">{formatNumero(e.limite, 2)} {e.unidad}</td>
              <td className="px-3 py-2 tabular-nums">{formatNumero(e.desviacion_limite, 2)}</td>
              <td className="px-3 py-2 text-xs">{e.calidad_valor ?? 'sin dato'}</td>
              <td className="px-3 py-2">
                <button type="button" onClick={() => onVerDetalle(e.id)} className="text-xs font-medium text-teal-700 hover:underline">
                  Detalle
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
