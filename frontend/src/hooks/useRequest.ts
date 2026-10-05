import { useCallback, useRef, useState } from 'react'
import type { ApiResult } from '../api/client'

/**
 * Estado de una consulta a la API. Si se lanzan dos consultas seguidas, solo se
 * guarda el resultado de la última (evita que una respuesta lenta pise a una nueva).
 */
export function useRequest<T>() {
  const [result, setResult] = useState<ApiResult<T> | null>(null)
  const [loading, setLoading] = useState(false)
  const ultima = useRef(0)

  const run = useCallback(async (fn: () => Promise<ApiResult<T>>) => {
    const id = ++ultima.current
    setLoading(true)
    const respuesta = await fn()
    if (id === ultima.current) {
      setResult(respuesta)
      setLoading(false)
    }
    return respuesta
  }, [])

  return { result, loading, run }
}
