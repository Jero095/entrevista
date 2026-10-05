import { useContext } from 'react'
import { ApiContext, type ApiContextValue } from '../api/apiContext'

export function useApi(): ApiContextValue {
  const context = useContext(ApiContext)
  if (!context) throw new Error('useApi debe usarse dentro de <ApiProvider>')
  return context
}
