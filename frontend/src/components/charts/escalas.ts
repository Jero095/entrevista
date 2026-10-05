// Utilidades de escalas para gráficas SVG hechas a mano (sin librerías).

export type Escala = (valor: number) => number

/** Escala lineal: transforma el dominio [d0, d1] en el rango de píxeles [r0, r1]. */
export function escalaLineal([d0, d1]: [number, number], [r0, r1]: [number, number]): Escala {
  const span = d1 - d0 || 1 // evita dividir por cero si el dominio es un solo valor
  return (v) => r0 + ((v - d0) / span) * (r1 - r0)
}

/** Marcas "redondas" para un eje numérico (1, 2, 2.5, 5 × 10^n), al estilo de d3.ticks. */
export function marcasNumericas(min: number, max: number, cantidad = 5): number[] {
  if (min === max) return [min]
  const paso = pasoRedondo((max - min) / cantidad)
  const inicio = Math.ceil(min / paso) * paso
  const marcas: number[] = []
  for (let v = inicio; v <= max + paso * 1e-9; v += paso) marcas.push(Number(v.toFixed(10)))
  return marcas
}

function pasoRedondo(bruto: number): number {
  const potencia = 10 ** Math.floor(Math.log10(bruto))
  const fraccion = bruto / potencia
  const base = fraccion <= 1 ? 1 : fraccion <= 2 ? 2 : fraccion <= 2.5 ? 2.5 : fraccion <= 5 ? 5 : 10
  return base * potencia
}

/** Dominio con margen: incluye todos los valores y deja aire arriba y abajo. */
export function dominioConMargen(valores: number[], margen = 0.1): [number, number] {
  const min = Math.min(...valores)
  const max = Math.max(...valores)
  const aire = (max - min || Math.abs(max) || 1) * margen
  return [min - aire, max + aire]
}

/** Marcas de tiempo repartidas uniformemente en el rango (en milisegundos). */
export function marcasTiempo(desde: number, hasta: number, cantidad = 6): number[] {
  return Array.from({ length: cantidad }, (_, i) => desde + ((hasta - desde) * i) / (cantidad - 1))
}

const DIA_MS = 24 * 60 * 60 * 1000

/** Etiqueta del eje X en UTC: con hora si el rango es corto, solo fecha si es largo. */
export function etiquetaTiempo(ms: number, rangoMs: number): string {
  const d = new Date(ms)
  const dd = String(d.getUTCDate()).padStart(2, '0')
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0')
  if (rangoMs > 3 * DIA_MS) return `${dd}/${mm}`
  const hh = String(d.getUTCHours()).padStart(2, '0')
  const mi = String(d.getUTCMinutes()).padStart(2, '0')
  return `${dd}/${mm} ${hh}:${mi}`
}

export function mediana(valores: number[]): number {
  const orden = [...valores].sort((a, b) => a - b)
  const medio = Math.floor(orden.length / 2)
  return orden.length % 2 ? orden[medio] : (orden[medio - 1] + orden[medio]) / 2
}

export interface Tramo {
  desde: number
  hasta: number
  valor: number
}

/**
 * Convierte el límite de cada evento en tramos horizontales. Si el límite nunca
 * cambió hay un solo tramo; si se versionó (alarma_config), aparece un escalón
 * en la fecha del cambio.
 */
export function tramosDeLimite(puntos: { t: number; limite: number }[], desde: number, hasta: number): Tramo[] {
  const orden = [...puntos].sort((a, b) => a.t - b.t)
  const tramos: Tramo[] = []
  for (const p of orden) {
    const ultimo = tramos.at(-1)
    if (ultimo && ultimo.valor === p.limite) continue
    if (ultimo) ultimo.hasta = p.t
    tramos.push({ desde: tramos.length === 0 ? desde : p.t, hasta, valor: p.limite })
  }
  return tramos
}
