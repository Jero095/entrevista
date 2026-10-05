import type { ReactNode } from 'react'
import type { AlarmaEvento, Estado } from '../../api/types'
import { InfoTip } from '../InfoTip'
import {
  dominioConMargen,
  escalaLineal,
  etiquetaTiempo,
  marcasNumericas,
  marcasTiempo,
  mediana,
  tramosDeLimite,
  type Escala,
  type Tramo,
} from './escalas'

// Lienzo en unidades del viewBox; el SVG se escala al ancho disponible.
const W = 640
const H = 250
const M = { top: 14, right: 18, bottom: 30, left: 58 }
const X0 = M.left
const X1 = W - M.right
const Y0 = H - M.bottom // abajo
const Y1 = M.top // arriba

export interface InstrumentoGrafica {
  tag: string
  descripcion: string
  unidad: string | null
  tipo_alarma: string
}

type TipoGrafica = 'umbral' | 'banda' | 'tasa' | 'discreta'

const DESCRIPCION_GRAFICA: Record<TipoGrafica, { nombre: string; porque: string }> = {
  umbral: {
    nombre: 'Dispersión con umbral',
    porque:
      'Cada punto es un evento (un instante), no una medición continua; por eso no se unen con líneas. ' +
      'La línea punteada es el límite vigente y la zona sombreada es donde la variable está en alarma ' +
      '(por encima en HI/HIHI, por debajo en LO/LOLO).',
  },
  banda: {
    nombre: 'Dispersión con banda de tolerancia',
    porque:
      'Una alarma de desviación (DEV) no tiene un umbral fijo: salta cuando el valor se aleja de la referencia ' +
      'más que el límite (±). La referencia se estima como la mediana de los valores al volver a normal (RTN), ' +
      'porque el catálogo guarda la tolerancia pero no el setpoint.',
  },
  tasa: {
    nombre: 'Barras de tasa de cambio',
    porque:
      'Una alarma ROC mide cuánto cambió la variable, no su nivel. Cada barra es la tasa registrada al activarse ' +
      'o reconocerse la alarma, contra el límite de tasa. Los eventos RTN registran el caudal absoluto (otra ' +
      'magnitud), así que no se grafican en este eje.',
  },
  discreta: {
    nombre: 'Escalones (señal discreta)',
    porque:
      'Una señal discreta solo vale 0 o 1 y mantiene su estado hasta el siguiente cambio; por eso se dibuja en ' +
      'escalones. El estado de alarma es 0 (válvula cerrada) y 1 es la operación normal.',
  },
}

function tipoDeGrafica(tipoAlarma: string): TipoGrafica {
  if (tipoAlarma === 'DEV') return 'banda'
  if (tipoAlarma === 'ROC') return 'tasa'
  if (tipoAlarma === 'DISC') return 'discreta'
  return 'umbral'
}

const colorEstado: Record<Estado, string> = {
  ACTIVE: 'fill-red-500',
  ACK: 'fill-amber-500',
  RTN: 'fill-emerald-500',
}

interface Punto {
  t: number
  v: number
  limite: number
  evento: AlarmaEvento
}

const formato = (v: number) => v.toLocaleString('es', { maximumFractionDigits: 2 })

export function GraficaInstrumento({ instrumento, eventos, rango }: {
  instrumento: InstrumentoGrafica
  eventos: AlarmaEvento[]
  rango: [number, number]
}) {
  const tipo = tipoDeGrafica(instrumento.tipo_alarma)
  const unidad = instrumento.unidad ?? ''
  const todos: Punto[] = eventos
    .filter((e) => e.valor !== null)
    .map((e) => ({ t: Date.parse(e.timestamp_utc), v: e.valor as number, limite: e.limite, evento: e }))
    .sort((a, b) => a.t - b.t)
  // En ROC solo ACTIVE/ACK registran la tasa; RTN guarda el caudal absoluto.
  const puntos = tipo === 'tasa' ? todos.filter((p) => p.evento.estado !== 'RTN') : todos
  const sinValor = eventos.length - todos.length
  const rtnExcluidos = todos.length - puntos.length

  const x = escalaLineal(rango, [X0, X1])
  const tramos = puntos.length ? tramosDeLimite(puntos, rango[0], rango[1]) : []

  let grafica: { dominio: [number, number]; marcas: number[]; etiquetaY?: (v: number) => string; fondo: ReactNode; frente: ReactNode } | null = null

  if (puntos.length > 0) {
    if (tipo === 'umbral') {
      const dominio = dominioConMargen([...puntos.map((p) => p.v), ...tramos.map((t) => t.valor)])
      const y = escalaLineal(dominio, [Y0, Y1])
      const arriba = instrumento.tipo_alarma === 'HI' || instrumento.tipo_alarma === 'HIHI'
      grafica = {
        dominio,
        marcas: marcasNumericas(dominio[0], dominio[1]),
        fondo: <ZonaAlarma tramos={tramos} x={x} desdeY={(t) => y(t.valor)} hastaY={() => (arriba ? Y1 : Y0)} />,
        frente: (
          <>
            <LineaLimite tramos={tramos} x={x} y={(t) => y(t.valor)} />
            <Puntos puntos={puntos} x={x} y={y} unidad={unidad} />
            <EtiquetaLimite texto={`Límite ${formato(tramos.at(-1)!.valor)} ${unidad}`} y={y(tramos.at(-1)!.valor)} />
          </>
        ),
      }
    } else if (tipo === 'banda') {
      const rtn = puntos.filter((p) => p.evento.estado === 'RTN').map((p) => p.v)
      const referencia = mediana(rtn.length ? rtn : puntos.map((p) => p.v))
      const dominio = dominioConMargen([
        ...puntos.map((p) => p.v),
        ...tramos.flatMap((t) => [referencia + t.valor, referencia - t.valor]),
      ])
      const y = escalaLineal(dominio, [Y0, Y1])
      const tol = tramos.at(-1)!.valor
      grafica = {
        dominio,
        marcas: marcasNumericas(dominio[0], dominio[1]),
        fondo: (
          <>
            <ZonaAlarma tramos={tramos} x={x} desdeY={(t) => y(referencia + t.valor)} hastaY={() => Y1} />
            <ZonaAlarma tramos={tramos} x={x} desdeY={(t) => y(referencia - t.valor)} hastaY={() => Y0} />
          </>
        ),
        frente: (
          <>
            <line x1={X0} x2={X1} y1={y(referencia)} y2={y(referencia)} className="stroke-slate-400" strokeWidth={1} />
            <LineaLimite tramos={tramos} x={x} y={(t) => y(referencia + t.valor)} />
            <LineaLimite tramos={tramos} x={x} y={(t) => y(referencia - t.valor)} />
            <Puntos puntos={puntos} x={x} y={y} unidad={unidad} />
            <EtiquetaLimite texto={`Referencia ${formato(referencia)} ± ${formato(tol)} ${unidad}`} y={y(referencia + tol)} />
          </>
        ),
      }
    } else if (tipo === 'tasa') {
      const dominio: [number, number] = [0, Math.max(...puntos.map((p) => p.v), ...tramos.map((t) => t.valor)) * 1.15]
      const y = escalaLineal(dominio, [Y0, Y1])
      grafica = {
        dominio,
        marcas: marcasNumericas(dominio[0], dominio[1]),
        fondo: <ZonaAlarma tramos={tramos} x={x} desdeY={(t) => y(t.valor)} hastaY={() => Y1} />,
        frente: (
          <>
            {puntos.map((p) => (
              <line key={`s${p.evento.id}`} x1={x(p.t)} x2={x(p.t)} y1={y(0)} y2={y(p.v)} className="stroke-slate-300" strokeWidth={1} />
            ))}
            <LineaLimite tramos={tramos} x={x} y={(t) => y(t.valor)} />
            <Puntos puntos={puntos} x={x} y={y} unidad={`${unidad} (tasa)`} />
            <EtiquetaLimite texto={`Límite de tasa ${formato(tramos.at(-1)!.valor)} ${unidad}`} y={y(tramos.at(-1)!.valor)} />
          </>
        ),
      }
    } else {
      const dominio: [number, number] = [-0.3, 1.3]
      const y = escalaLineal(dominio, [Y0, Y1])
      // Empieza en el primer evento: antes de él no se conoce el estado de la señal.
      let camino = `M ${x(puntos[0].t)} ${y(puntos[0].v)}`
      for (const p of puntos) camino += ` H ${x(p.t)} V ${y(p.v)}`
      camino += ` H ${x(rango[1])}`
      grafica = {
        dominio,
        marcas: [0, 1],
        etiquetaY: (v) => (v === 0 ? '0 alarma' : '1 normal'),
        fondo: <rect x={X0} width={X1 - X0} y={y(0.5)} height={Y0 - y(0.5)} className="fill-red-500/10" />,
        frente: (
          <>
            <path d={camino} fill="none" className="stroke-teal-700" strokeWidth={1.5} />
            <line x1={X0} x2={X1} y1={y(0)} y2={y(0)} className="stroke-red-500" strokeWidth={1} strokeDasharray="5 4" />
            <Puntos puntos={puntos} x={x} y={y} unidad="" />
            <EtiquetaLimite texto="Estado de alarma = 0" y={y(0)} />
          </>
        ),
      }
    }
  }

  const info = DESCRIPCION_GRAFICA[tipo]

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <header className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">
            {instrumento.tag} <span className="font-normal text-slate-500">· {instrumento.descripcion}</span>
          </h3>
          <p className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500">
            Alarma {instrumento.tipo_alarma} · {info.nombre}
            <InfoTip texto={info.porque} />
          </p>
        </div>
        <span className="text-xs text-slate-500">
          {puntos.length} {puntos.length === 1 ? 'evento' : 'eventos'}
          {sinValor > 0 && ` · ${sinValor} sin valor válido`}
          {rtnExcluidos > 0 && ` · ${rtnExcluidos} RTN no graficados (miden caudal, no tasa)`}
        </span>
      </header>

      {grafica ? (
        <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={`Valor de ${instrumento.tag} en el tiempo con su umbral de alarma`}>
          <Ejes rango={rango} dominio={grafica.dominio} marcas={grafica.marcas} unidad={unidad} etiquetaY={grafica.etiquetaY} />
          {grafica.fondo}
          {grafica.frente}
        </svg>
      ) : (
        <p className="py-10 text-center text-sm text-slate-500">Sin eventos con valor en este rango.</p>
      )}
    </article>
  )
}

function Ejes({ rango, dominio, marcas, unidad, etiquetaY }: {
  rango: [number, number]
  dominio: [number, number]
  marcas: number[]
  unidad: string
  etiquetaY?: (v: number) => string
}) {
  const x = escalaLineal(rango, [X0, X1])
  const y = escalaLineal(dominio, [Y0, Y1])
  const tiempos = marcasTiempo(rango[0], rango[1])
  return (
    <g className="text-[11px]">
      {marcas.map((m) => (
        <g key={m}>
          <line x1={X0} x2={X1} y1={y(m)} y2={y(m)} className="stroke-slate-100" />
          <text x={X0 - 6} y={y(m)} textAnchor="end" dominantBaseline="middle" className="fill-slate-500">
            {etiquetaY ? etiquetaY(m) : formato(m)}
          </text>
        </g>
      ))}
      <line x1={X0} x2={X1} y1={Y0} y2={Y0} className="stroke-slate-300" />
      {tiempos.map((t, i) => (
        <text key={t} x={x(t)} y={H - 10} className="fill-slate-500"
          textAnchor={i === 0 ? 'start' : i === tiempos.length - 1 ? 'end' : 'middle'}>
          {etiquetaTiempo(t, rango[1] - rango[0])}
        </text>
      ))}
      {unidad && (
        <text x={4} y={Y1} dominantBaseline="hanging" className="fill-slate-400">{unidad}</text>
      )}
    </g>
  )
}

function ZonaAlarma({ tramos, x, desdeY, hastaY }: {
  tramos: Tramo[]
  x: Escala
  desdeY: (t: Tramo) => number
  hastaY: (t: Tramo) => number
}) {
  return (
    <>
      {tramos.map((t) => {
        const a = Math.min(desdeY(t), hastaY(t))
        const b = Math.max(desdeY(t), hastaY(t))
        return <rect key={t.desde} x={x(t.desde)} width={Math.max(x(t.hasta) - x(t.desde), 0)} y={a} height={b - a} className="fill-red-500/10" />
      })}
    </>
  )
}

/** Límite como línea escalonada: horizontal mientras no cambia, con un salto si se versionó. */
function LineaLimite({ tramos, x, y }: { tramos: Tramo[]; x: Escala; y: (t: Tramo) => number }) {
  if (tramos.length === 0) return null
  let d = `M ${x(tramos[0].desde)} ${y(tramos[0])}`
  for (const t of tramos) d += ` V ${y(t)} H ${x(t.hasta)}`
  return <path d={d} fill="none" className="stroke-red-500" strokeWidth={1.25} strokeDasharray="5 4" />
}

function EtiquetaLimite({ texto, y }: { texto: string; y: number }) {
  return (
    // Contorno blanco (paint-order) para que se lea aunque haya puntos detrás.
    <text x={X1 - 4} y={y - 5} textAnchor="end" paintOrder="stroke" strokeWidth={4} strokeLinejoin="round"
      className="fill-red-600 stroke-white text-[11px] font-medium">
      {texto}
    </text>
  )
}

function Puntos({ puntos, x, y, unidad }: { puntos: Punto[]; x: Escala; y: Escala; unidad: string }) {
  return (
    <>
      {puntos.map((p) => (
        <circle key={p.evento.id} cx={x(p.t)} cy={y(p.v)} r={2.6} className={`${colorEstado[p.evento.estado]} opacity-80`}>
          <title>
            {`${p.evento.timestamp_utc.replace('T', ' ').replace(/(\.\d+)?Z$/, ' UTC')} · ${p.evento.estado} · ${formato(p.v)} ${unidad}`.trim()}
          </title>
        </circle>
      ))}
    </>
  )
}

export function LeyendaGraficas() {
  return (
    <ul className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-600">
      <li className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-red-500" /> ACTIVE (saltó)</li>
      <li className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-amber-500" /> ACK (reconocida)</li>
      <li className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-emerald-500" /> RTN (volvió a normal)</li>
      <li className="flex items-center gap-1.5"><span className="w-5 border-t-2 border-dashed border-red-500" /> Umbral / límite</li>
      <li className="flex items-center gap-1.5"><span className="h-3 w-5 bg-red-500/10" /> Zona de alarma</li>
    </ul>
  )
}
