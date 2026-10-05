const numero = new Intl.NumberFormat('es')

export function formatNumero(value: number | null | undefined, decimales?: number): string {
  if (value === null || value === undefined) return '—'
  if (decimales === undefined) return numero.format(value)
  return value.toLocaleString('es', { minimumFractionDigits: decimales, maximumFractionDigits: decimales })
}

/** '2026-07-07T23:40:43.866Z' -> '2026-07-07 23:40:43 UTC' */
export function formatFechaUtc(iso: string | null | undefined): string {
  if (!iso) return '—'
  return iso.replace('T', ' ').replace(/(\.\d+)?Z$/, '') + ' UTC'
}

/** Valor de un <input type="datetime-local"> (sin zona) -> ISO que la API interpreta como UTC. */
export function aIsoUtc(local: string): string {
  if (!local) return ''
  return local.length === 16 ? `${local}:00Z` : `${local}Z`
}
