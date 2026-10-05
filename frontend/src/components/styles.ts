import type { Criticidad } from '../api/types'

export const inputClass =
  'w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-800 shadow-sm focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20'

export const criticidadBarClass: Record<Criticidad, string> = {
  CRITICAL: 'bg-red-500',
  HIGH: 'bg-orange-500',
  MEDIUM: 'bg-amber-400',
  LOW: 'bg-sky-500',
}
