import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { Criticidad } from '../api/types'
import { InfoTip } from './InfoTip'

export function Card({ title, info, description, actions, children }: {
  title: string
  info?: string
  description?: ReactNode
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
            {title}
            {info && <InfoTip texto={info} />}
          </h2>
          {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
      {children}
    </section>
  )
}

/** Etiqueta + ícono de explicación + control del formulario. */
export function Field({ label, info, htmlFor, children }: {
  label: string
  info: string
  htmlFor?: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1.5">
        <label htmlFor={htmlFor} className="text-xs font-medium text-slate-600">{label}</label>
        <InfoTip texto={info} />
      </div>
      {children}
    </div>
  )
}

type Variant = 'primary' | 'secondary' | 'ghost'

const variantClass: Record<Variant, string> = {
  primary: 'bg-teal-700 text-white hover:bg-teal-800 disabled:bg-teal-700/50',
  secondary: 'border border-teal-700 text-teal-800 hover:bg-teal-50 disabled:opacity-50',
  ghost: 'text-slate-600 hover:bg-slate-100 disabled:opacity-50',
}

export function Button({ variant = 'primary', className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type="button"
      className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed ${variantClass[variant]} ${className}`}
      {...props}
    />
  )
}

const criticidadClass: Record<Criticidad, string> = {
  CRITICAL: 'bg-red-100 text-red-800',
  HIGH: 'bg-orange-100 text-orange-800',
  MEDIUM: 'bg-amber-100 text-amber-800',
  LOW: 'bg-sky-100 text-sky-800',
}

export function CriticidadBadge({ value }: { value: Criticidad }) {
  return <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${criticidadClass[value]}`}>{value}</span>
}

export function EjemploNota({ children }: { children: ReactNode }) {
  return (
    <p className="mb-4 rounded-md border border-teal-200 bg-teal-50 px-3 py-2 text-xs text-teal-900">
      <span className="font-semibold">Ejemplo: </span>{children}
    </p>
  )
}

export function Kpi({ label, value, info, sub }: { label: string; value: string; info: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
        {label}
        <InfoTip texto={info} />
      </div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-500">{sub}</div>}
    </div>
  )
}

/** Gráfico de barras horizontal hecho con CSS (sin librerías). */
export function BarList({ items }: { items: { label: ReactNode; value: number; color?: string; hint?: string }[] }) {
  const max = Math.max(1, ...items.map((i) => i.value))
  if (items.length === 0) return <p className="text-sm text-slate-500">Sin datos para estos filtros.</p>
  return (
    <ul className="flex flex-col gap-2">
      {items.map((item, index) => (
        <li key={index} className="grid grid-cols-[9rem_1fr_4.5rem] items-center gap-3 text-sm">
          <span className="truncate text-slate-700" title={item.hint}>{item.label}</span>
          <span className="h-3 overflow-hidden rounded bg-slate-100">
            <span
              className={`block h-full rounded ${item.color ?? 'bg-teal-600'}`}
              style={{ width: `${(item.value / max) * 100}%` }}
            />
          </span>
          <span className="text-right font-medium tabular-nums text-slate-800">{item.value.toLocaleString('es')}</span>
        </li>
      ))}
    </ul>
  )
}
