import { createContext } from 'react'
import type { ApiResult, Params } from './client'

export interface ApiContextValue {
  apiKey: string
  setApiKey: (key: string) => void
  /** Llama a la API con la clave actual. `sinClave` omite el header (para demostrar el 401). */
  call: <T>(path: string, params?: Params, opciones?: { sinClave?: boolean }) => Promise<ApiResult<T>>
}

export const ApiContext = createContext<ApiContextValue | null>(null)
