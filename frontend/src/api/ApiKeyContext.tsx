import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { ApiContext } from './apiContext'
import { request, type Params } from './client'

const STORAGE_KEY = 'alarmas.apiKey'
// Clave de desarrollo (la misma de .env.example). Se puede cambiar desde la cabecera.
const DEFAULT_KEY = import.meta.env.VITE_API_KEY ?? 'dev-api-key-cambiar'

function leerClaveGuardada(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? DEFAULT_KEY
  } catch {
    return DEFAULT_KEY // almacenamiento bloqueado (modo privado): se usa la clave por defecto
  }
}

export function ApiProvider({ children }: { children: ReactNode }) {
  const [apiKey, setApiKeyState] = useState(leerClaveGuardada)

  const setApiKey = useCallback((key: string) => {
    setApiKeyState(key)
    try {
      localStorage.setItem(STORAGE_KEY, key)
    } catch {
      // Sin almacenamiento la clave vale solo para esta sesión.
    }
  }, [])

  const call = useCallback(
    <T,>(path: string, params?: Params, opciones?: { sinClave?: boolean }) =>
      request<T>(path, params, opciones?.sinClave ? null : apiKey),
    [apiKey],
  )

  const value = useMemo(() => ({ apiKey, setApiKey, call }), [apiKey, setApiKey, call])
  return <ApiContext.Provider value={value}>{children}</ApiContext.Provider>
}
