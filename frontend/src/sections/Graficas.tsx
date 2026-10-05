import { useEffect, useState } from 'react'
import type { ApiContextValue } from '../api/apiContext'
import type { ApiResult } from '../api/client'
import type { AlarmaEvento, Pagina, TagCatalogo } from '../api/types'
import { GraficaInstrumento, LeyendaGraficas, type InstrumentoGrafica } from '../components/charts/GraficaInstrumento'
import { RequestPanel } from '../components/RequestPanel'
import { inputClass } from '../components/styles'
import { Button, Card, EjemploNota, Field } from '../components/ui'
import { GRAFICAS_EJEMPLO, GRAFICAS_EJEMPLO_TEXTO, type FiltrosGraficas } from '../ejemplos'
import { aIsoUtc, formatNumero } from '../format'
import { useApi } from '../hooks/useApi'

const POR_PAGINA = 500 // máximo que permite la API
const MAX_PAGINAS = 20 // tope de 10 000 eventos para no saturar el navegador

interface Serie {
  catalogo: TagCatalogo[]
  eventos: AlarmaEvento[]
  primera: ApiResult<unknown> // primera petición, para mostrarla en pantalla
  peticiones: number
  total: number
  truncado: boolean
}

/** Pide todas las páginas de eventos del rango (en paralelo tras la primera) y el catálogo. */
async function cargarSerie(call: ApiContextValue['call'], f: FiltrosGraficas): Promise<Serie> {
  const params = { desde: aIsoUtc(f.desde), hasta: aIsoUtc(f.hasta), tag: f.tag, size: POR_PAGINA }
  const [catalogo, primera] = await Promise.all([
    call<TagCatalogo[]>('/api/v1/tags'),
    call<Pagina<AlarmaEvento>>('/api/v1/alarmas', { ...params, page: 1 }),
  ])
  const vacia = { catalogo: catalogo.data ?? [], eventos: [], peticiones: 2, total: 0, truncado: false }
  if (!primera.data) return { ...vacia, primera }
  if (!catalogo.data) return { ...vacia, primera: catalogo }

  const paginas = Math.min(primera.data.pages, MAX_PAGINAS)
  const resto = await Promise.all(
    Array.from({ length: paginas - 1 }, (_, i) => call<Pagina<AlarmaEvento>>('/api/v1/alarmas', { ...params, page: i + 2 })),
  )
  const fallida = resto.find((r) => !r.ok)
  if (fallida) return { ...vacia, primera: fallida }

  return {
    catalogo: catalogo.data,
    eventos: [primera.data, ...resto.map((r) => r.data as Pagina<AlarmaEvento>)].flatMap((p) => p.items),
    primera,
    peticiones: paginas + 1,
    total: primera.data.total,
    truncado: primera.data.pages > MAX_PAGINAS,
  }
}

export function Graficas() {
  const { call } = useApi()
  const [filtros, setFiltros] = useState<FiltrosGraficas>(GRAFICAS_EJEMPLO)
  const [consultados, setConsultados] = useState<FiltrosGraficas>(GRAFICAS_EJEMPLO)
  const [serie, setSerie] = useState<Serie | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Al abrir la sección se muestran los datos de ejemplo, así nunca aparece vacía.
    let activo = true
    cargarSerie(call, GRAFICAS_EJEMPLO).then((s) => {
      if (activo) {
        setSerie(s)
        setLoading(false)
      }
    })
    return () => {
      activo = false
    }
  }, [call])

  const consultar = (f: FiltrosGraficas) => {
    setLoading(true)
    setConsultados(f)
    cargarSerie(call, f).then((s) => {
      setSerie(s)
      setLoading(false)
    })
  }

  const set = <K extends keyof FiltrosGraficas>(campo: K, valor: FiltrosGraficas[K]) =>
    setFiltros((f) => ({ ...f, [campo]: valor }))

  // Eje X: el rango pedido; si algún extremo quedó vacío, se completa con los datos.
  const tiempos = serie?.eventos.map((e) => Date.parse(e.timestamp_utc)) ?? []
  const rango: [number, number] = [
    consultados.desde ? Date.parse(aIsoUtc(consultados.desde)) : Math.min(...tiempos),
    consultados.hasta ? Date.parse(aIsoUtc(consultados.hasta)) : Math.max(...tiempos),
  ]

  const instrumentos: InstrumentoGrafica[] = (serie?.catalogo ?? [])
    .filter((t) => !consultados.tag || t.tag === consultados.tag)
    .flatMap((t) => t.alarmas.map((a) => ({ tag: t.tag, descripcion: t.descripcion, unidad: t.unidad, tipo_alarma: a.tipo_alarma })))

  return (
    <div className="flex flex-col gap-6">
      <Card
        title="Gráficas por instrumento"
        info="Valor registrado en cada evento (eje Y) a lo largo del tiempo (eje X), con el umbral de alarma vigente. Cada tipo de alarma usa la gráfica que mejor la representa: ver el ícono de cada gráfica."
        description="Eventos de alarma en el tiempo frente a su umbral. Los datos van del 2 de julio al 30 de septiembre de 2026."
        actions={
          <Button variant="secondary" onClick={() => { setFiltros(GRAFICAS_EJEMPLO); consultar(GRAFICAS_EJEMPLO) }}>
            Datos de ejemplo
          </Button>
        }
      >
        {filtros === GRAFICAS_EJEMPLO && <EjemploNota>{GRAFICAS_EJEMPLO_TEXTO}</EjemploNota>}

        <form
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
          onSubmit={(e) => {
            e.preventDefault()
            consultar(filtros)
          }}
        >
          <Field label="Desde (UTC)" htmlFor="gr-desde" info="Inicio del rango, incluido. Rangos cortos (una semana) se leen mejor: cada punto es un evento.">
            <input id="gr-desde" type="datetime-local" className={inputClass} value={filtros.desde} onChange={(e) => set('desde', e.target.value)} />
          </Field>
          <Field label="Hasta (UTC)" htmlFor="gr-hasta" info="Fin del rango, no incluido. Se cargan como máximo 10 000 eventos; si el rango tiene más, se avisa.">
            <input id="gr-hasta" type="datetime-local" className={inputClass} value={filtros.hasta} onChange={(e) => set('hasta', e.target.value)} />
          </Field>
          <Field label="Instrumento" htmlFor="gr-tag" info="Un instrumento o todos. La gráfica de cada uno depende de su tipo de alarma (HI/LO, DEV, ROC o DISC).">
            <select id="gr-tag" className={inputClass} value={filtros.tag} onChange={(e) => set('tag', e.target.value)}>
              <option value="">Todos</option>
              {(serie?.catalogo ?? []).map((t) => <option key={t.tag} value={t.tag}>{t.tag} · {t.descripcion}</option>)}
            </select>
          </Field>
          <div className="flex items-end">
            <Button type="submit" disabled={loading}>Graficar</Button>
          </div>
        </form>

        {loading ? (
          <p className="mt-4 animate-pulse text-sm text-slate-500">Cargando eventos…</p>
        ) : (
          serie && (
            <>
              <RequestPanel result={serie.primera} loading={false} />
              {serie.primera.ok && (
                <p className="mt-2 text-xs text-slate-500">
                  {formatNumero(serie.eventos.length)} eventos cargados en {serie.peticiones} peticiones
                  (páginas de {POR_PAGINA} + catálogo).
                  {serie.truncado && (
                    <span className="font-medium text-amber-700">
                      {' '}El rango tiene {formatNumero(serie.total)} eventos: se muestran los {formatNumero(serie.eventos.length)} más recientes. Acota el rango para verlos todos.
                    </span>
                  )}
                </p>
              )}
            </>
          )
        )}
        <div className="mt-4">
          <LeyendaGraficas />
        </div>
      </Card>

      {!loading && serie?.primera.ok && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {instrumentos.map((i) => (
            <GraficaInstrumento
              key={`${i.tag}-${i.tipo_alarma}`}
              instrumento={i}
              eventos={serie.eventos.filter((e) => e.tag === i.tag && e.tipo_alarma === i.tipo_alarma)}
              rango={rango}
            />
          ))}
        </div>
      )}
    </div>
  )
}
