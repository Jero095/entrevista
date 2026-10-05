import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import type { ApiResult, Params } from '../api/client'
import { RequestPanel } from '../components/RequestPanel'
import { Button, Card } from '../components/ui'

interface Caso {
  nombre: string
  explicacion: string
  path: string
  params?: Params
  sinClave?: boolean
  esperado: number
}

// Casos fijos que demuestran la validación de entrada y el manejo de errores.
const CASOS: Caso[] = [
  { nombre: 'Rango de fechas invertido', explicacion: "'desde' es posterior a 'hasta'.", path: '/api/v1/alarmas', params: { desde: '2026-07-08T00:00:00Z', hasta: '2026-07-01T00:00:00Z' }, esperado: 422 },
  { nombre: 'Fecha con formato inválido', explicacion: "'ayer' no es una fecha ISO 8601.", path: '/api/v1/alarmas', params: { desde: 'ayer' }, esperado: 422 },
  { nombre: 'Criticidad inexistente', explicacion: 'SUPER no es LOW, MEDIUM, HIGH ni CRITICAL.', path: '/api/v1/alarmas', params: { criticidad: 'SUPER' }, esperado: 422 },
  { nombre: 'Filtros contradictorios', explicacion: "No se puede usar 'criticidad' y 'criticidad_min' a la vez.", path: '/api/v1/alarmas', params: { criticidad: 'HIGH', criticidad_min: 'LOW' }, esperado: 422 },
  { nombre: 'Parámetro mal escrito', explicacion: "'criticiad' no existe: se rechaza en vez de ignorarse y devolver todo sin filtrar.", path: '/api/v1/alarmas', params: { criticiad: 'HIGH' }, esperado: 422 },
  { nombre: 'Intento de inyección SQL', explicacion: 'El tag no cumple el formato XX-NNN; además, las consultas van parametrizadas.', path: '/api/v1/alarmas', params: { tag: "PT-101' OR '1'='1" }, esperado: 422 },
  { nombre: 'Página demasiado grande', explicacion: 'El máximo es 500 resultados por página.', path: '/api/v1/alarmas', params: { size: 10000 }, esperado: 422 },
  { nombre: 'Tag inexistente', explicacion: 'XX-999 tiene formato válido pero no existe en el catálogo.', path: '/api/v1/alarmas', params: { tag: 'XX-999' }, esperado: 404 },
  { nombre: 'Evento inexistente', explicacion: 'No hay ningún evento con ese id.', path: '/api/v1/alarmas/999999999', esperado: 404 },
  { nombre: 'Sin API key', explicacion: 'La petición se envía sin el header X-API-Key.', path: '/api/v1/alarmas', sinClave: true, esperado: 401 },
  { nombre: 'Ruta inexistente', explicacion: 'Incluso este error usa el formato uniforme {error: {...}}.', path: '/api/v1/no-existe', esperado: 404 },
]

export function Errores() {
  const { call } = useApi()
  const [resultados, setResultados] = useState<Record<number, ApiResult<unknown>>>({})
  const [ejecutando, setEjecutando] = useState<number | 'todos' | null>(null)

  const ejecutar = async (indice: number) => {
    const caso = CASOS[indice]
    const resultado = await call<unknown>(caso.path, caso.params, { sinClave: caso.sinClave })
    setResultados((r) => ({ ...r, [indice]: resultado }))
  }

  const ejecutarUno = async (indice: number) => {
    setEjecutando(indice)
    await ejecutar(indice)
    setEjecutando(null)
  }

  const ejecutarTodos = async () => {
    setEjecutando('todos')
    for (let i = 0; i < CASOS.length; i++) await ejecutar(i)
    setEjecutando(null)
  }

  const ejecutados = Object.keys(resultados).length
  const correctos = CASOS.filter((c, i) => resultados[i]?.status === c.esperado).length

  return (
    <Card
      title="Validación y manejo de errores"
      info="Casos fijos que envían datos inválidos a propósito. Todos los errores de la API tienen el mismo formato: {error: {codigo, mensaje, detalle}}."
      description="Cada caso muestra el código HTTP esperado y el que respondió la API."
      actions={<Button onClick={ejecutarTodos} disabled={ejecutando !== null}>Ejecutar todos</Button>}
    >
      {ejecutados > 0 && (
        <p className={`mb-4 text-sm font-medium ${correctos === ejecutados ? 'text-emerald-700' : 'text-red-700'}`}>
          {correctos} de {ejecutados} casos respondieron el código esperado.
        </p>
      )}
      <ul className="flex flex-col gap-3">
        {CASOS.map((caso, i) => {
          const resultado = resultados[i]
          const ok = resultado?.status === caso.esperado
          return (
            <li key={caso.nombre} className="rounded-lg border border-slate-200 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-medium text-slate-900">{caso.nombre}</p>
                  <p className="text-xs text-slate-500">{caso.explicacion}</p>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-700">Esperado: HTTP {caso.esperado}</span>
                  {resultado && (
                    <span className={`rounded px-1.5 py-0.5 font-semibold ${ok ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}>
                      {ok ? '✓' : '✗'} Obtenido: {resultado.status === 0 ? 'sin respuesta' : `HTTP ${resultado.status}`}
                    </span>
                  )}
                  <Button variant="secondary" disabled={ejecutando !== null} onClick={() => ejecutarUno(i)}>Probar</Button>
                </div>
              </div>
              {resultado && <RequestPanel result={resultado} loading={false} />}
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
