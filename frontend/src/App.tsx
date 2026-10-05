import { useCallback, useEffect, useState } from 'react'
import { ApiProvider } from './api/ApiKeyContext'
import type { ApiResult } from './api/client'
import type { Health } from './api/types'
import { InfoTip } from './components/InfoTip'
import { inputClass } from './components/styles'
import { useApi } from './hooks/useApi'
import { SECCIONES, type Seccion } from './secciones'
import { Alarmas } from './sections/Alarmas'
import { CalidadDatos } from './sections/CalidadDatos'
import { Catalogo } from './sections/Catalogo'
import { Detalle } from './sections/Detalle'
import { Errores } from './sections/Errores'
import { PorCriticidad } from './sections/PorCriticidad'
import { Resumen } from './sections/Resumen'
import { TopTags } from './sections/TopTags'

export default function App() {
  return (
    <ApiProvider>
      <Layout />
    </ApiProvider>
  )
}

function Layout() {
  const [seccion, setSeccion] = useState<Seccion>('resumen')
  const [detalleId, setDetalleId] = useState<number | null>(null)

  const verDetalle = (id: number) => {
    setDetalleId(id)
    setSeccion('detalle')
  }

  return (
    <div className="min-h-screen">
      <Header />
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 md:flex-row">
        <nav aria-label="Secciones" className="md:w-56 md:shrink-0">
          <ul className="flex gap-1 overflow-x-auto md:sticky md:top-6 md:flex-col">
            {SECCIONES.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => setSeccion(s.id)}
                  aria-current={seccion === s.id ? 'page' : undefined}
                  className={`w-full whitespace-nowrap rounded-lg px-3 py-2 text-left transition ${
                    seccion === s.id ? 'bg-teal-700 text-white' : 'text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  <span className="block text-sm font-medium">{s.titulo}</span>
                  <span className={`block font-mono text-[11px] ${seccion === s.id ? 'text-teal-100' : 'text-slate-400'}`}>{s.endpoint}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <main className="min-w-0 flex-1">
          {seccion === 'resumen' && <Resumen irA={setSeccion} />}
          {seccion === 'alarmas' && <Alarmas onVerDetalle={verDetalle} />}
          {seccion === 'detalle' && <Detalle key={detalleId ?? 'nuevo'} idInicial={detalleId} />}
          {seccion === 'top' && <TopTags />}
          {seccion === 'criticidad' && <PorCriticidad />}
          {seccion === 'catalogo' && <Catalogo />}
          {seccion === 'calidad' && <CalidadDatos />}
          {seccion === 'errores' && <Errores />}
        </main>
      </div>
    </div>
  )
}

function Header() {
  const { apiKey, setApiKey, call } = useApi()
  const [health, setHealth] = useState<ApiResult<Health> | null>(null)

  const comprobar = useCallback(() => {
    call<Health>('/health').then(setHealth)
  }, [call])

  useEffect(() => {
    comprobar()
    const intervalo = setInterval(comprobar, 30_000)
    return () => clearInterval(intervalo)
  }, [comprobar])

  const enLinea = health?.ok && health.data?.base_de_datos === 'ok'

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-3">
        <div className="flex items-center gap-3">
          <img src="/favicon.svg" alt="" className="size-8" />
          <div>
            <h1 className="text-base font-semibold text-slate-900">SCADA Alarm Gateway</h1>
            <p className="text-xs text-slate-500">Consulta del histórico de alarmas normalizado</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          <button
            type="button"
            onClick={comprobar}
            title="Comprobar de nuevo (GET /health)"
            className="flex items-center gap-2 rounded-md px-2 py-1 text-xs hover:bg-slate-100"
          >
            <span className={`size-2.5 rounded-full ${health === null ? 'bg-slate-300' : enLinea ? 'bg-emerald-500' : 'bg-red-500'}`} />
            <span className="text-slate-600">
              {health === null ? 'Comprobando…' : enLinea ? 'API y base de datos en línea' : 'API no disponible'}
            </span>
          </button>
          <div className="flex items-center gap-2">
            <label htmlFor="api-key" className="text-xs font-medium text-slate-600">API key</label>
            <InfoTip texto="Clave que se envía en el header X-API-Key. Es la variable API_KEY del archivo .env (por defecto dev-api-key-cambiar). Bórrala para ver el error 401." />
            <input
              id="api-key"
              className={`${inputClass} w-52 font-mono text-xs`}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              spellCheck={false}
              autoComplete="off"
            />
          </div>
        </div>
      </div>
    </header>
  )
}
