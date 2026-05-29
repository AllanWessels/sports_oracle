import { useEffect, useRef, useState } from 'react'
import mermaid from 'mermaid'
import type { RouteStats } from '../../api/metrics'
import { buildGraphMermaid } from './graph'

mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'loose' })

let _seq = 0

/** Renders the LangGraph agent graph (Mermaid), annotated with live route %. */
export function GraphPanel({ routes }: { routes: Record<string, RouteStats> | undefined }) {
  const [svg, setSvg] = useState('')
  const [err, setErr] = useState(false)
  // Unique id per render — Mermaid errors if the id collides across renders.
  const idRef = useRef(`langgraph-${(_seq += 1)}`)

  useEffect(() => {
    let cancelled = false
    const def = buildGraphMermaid(routes)
    mermaid
      .render(idRef.current, def)
      .then(({ svg }) => {
        if (!cancelled) {
          setSvg(svg)
          setErr(false)
        }
      })
      .catch(() => {
        if (!cancelled) setErr(true)
      })
    return () => {
      cancelled = true
    }
  }, [routes])

  return (
    <section className="rounded-xl bg-surface-800 border border-surface-700 p-4" data-testid="graph-panel">
      <h2 className="text-sm font-semibold text-white mb-1">Agent graph (LangGraph)</h2>
      <p className="text-xs text-slate-400 mb-3">
        Dashed edges are the router decision; labels show live traffic share.
      </p>
      {err ? (
        <p className="text-xs text-rose-400">Could not render graph.</p>
      ) : (
        <div
          className="overflow-x-auto [&_svg]:max-w-full [&_svg]:h-auto"
          data-testid="graph-svg"
          // mermaid output is sanitized SVG markup
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      )}
    </section>
  )
}
