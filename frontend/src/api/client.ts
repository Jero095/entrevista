import type { ErrorRespuesta } from './types'

export type ParamValue = string | number | string[] | null | undefined
export type Params = Record<string, ParamValue>

/** Resultado de una petición: además de los datos, guarda lo necesario para mostrarla en pantalla. */
export interface ApiResult<T> {
  ok: boolean
  status: number // 0 = no hubo respuesta (red caída, API apagada)
  url: string
  ms: number
  data: T | null
  error: ErrorRespuesta['error'] | null
  body: unknown // respuesta tal cual llegó, para el visor JSON
}

/** Arma la query string omitiendo los campos vacíos; las listas se repiten (?a=1&a=2). */
export function buildQuery(params: Params = {}): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') continue
    if (Array.isArray(value)) value.forEach((v) => query.append(key, v))
    else query.append(key, String(value))
  }
  const text = query.toString()
  return text ? `?${text}` : ''
}

function esErrorRespuesta(body: unknown): body is ErrorRespuesta {
  return typeof body === 'object' && body !== null && 'error' in body
}

export async function request<T>(path: string, params?: Params, apiKey?: string | null): Promise<ApiResult<T>> {
  const url = path + buildQuery(params)
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (apiKey) headers['X-API-Key'] = apiKey

  const inicio = performance.now()
  try {
    const response = await fetch(url, { headers })
    const texto = await response.text()
    let body: unknown = texto
    try {
      body = texto ? JSON.parse(texto) : null
    } catch {
      // La respuesta no es JSON (p. ej. una página de error del proxy): se muestra como texto.
    }
    const ms = Math.round(performance.now() - inicio)
    return {
      ok: response.ok,
      status: response.status,
      url,
      ms,
      data: response.ok ? (body as T) : null,
      error: esErrorRespuesta(body) ? body.error : null,
      body,
    }
  } catch {
    return {
      ok: false,
      status: 0,
      url,
      ms: Math.round(performance.now() - inicio),
      data: null,
      error: { codigo: 'SIN_CONEXION', mensaje: 'No se pudo conectar con la API. ¿Está levantado Docker?', detalle: null },
      body: null,
    }
  }
}
