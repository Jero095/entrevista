import { useId, useRef, useState, type CSSProperties } from 'react'

const ANCHO = 256 // px
const MARGEN = 8 // distancia mínima a los bordes de la ventana

/**
 * Ícono "i" que muestra una explicación al pasar el mouse o al enfocarlo con el teclado.
 *
 * El tooltip se posiciona con `position: fixed` calculado al abrirse: queda dentro de
 * la ventana aunque el ícono esté junto a un borde, y mientras está cerrado no se
 * renderiza (no ocupa espacio ni genera barras de desplazamiento).
 */
export function InfoTip({ texto }: { texto: string }) {
  const id = useId()
  const boton = useRef<HTMLButtonElement>(null)
  const [estilo, setEstilo] = useState<CSSProperties | null>(null)

  const abrir = () => {
    const rect = boton.current?.getBoundingClientRect()
    if (!rect) return
    const centro = rect.left + rect.width / 2
    const left = Math.min(Math.max(centro - ANCHO / 2, MARGEN), window.innerWidth - ANCHO - MARGEN)
    // Arriba del ícono si hay espacio; si no (p. ej. en la cabecera), debajo.
    const arriba = rect.top > 140
    setEstilo(
      arriba
        ? { left, top: rect.top - MARGEN, transform: 'translateY(-100%)', width: ANCHO }
        : { left, top: rect.bottom + MARGEN, width: ANCHO },
    )
  }
  const cerrar = () => setEstilo(null)

  return (
    <span className="inline-flex align-middle">
      <button
        ref={boton}
        type="button"
        aria-describedby={estilo ? id : undefined}
        aria-label="Más información"
        onMouseEnter={abrir}
        onMouseLeave={cerrar}
        onFocus={abrir}
        onBlur={cerrar}
        onKeyDown={(e) => e.key === 'Escape' && cerrar()}
        className="flex size-4 cursor-help items-center justify-center rounded-full border border-slate-400 text-[10px] font-semibold leading-none text-slate-500 hover:border-teal-600 hover:text-teal-700 focus:border-teal-600 focus:text-teal-700 focus:outline-none"
      >
        i
      </button>
      {estilo && (
        <span
          id={id}
          role="tooltip"
          style={estilo}
          className="pointer-events-none fixed z-50 rounded-md bg-slate-800 px-3 py-2 text-xs font-normal leading-relaxed text-white shadow-lg"
        >
          {texto}
        </span>
      )}
    </span>
  )
}
