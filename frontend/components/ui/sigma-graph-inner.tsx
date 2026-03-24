// @ts-nocheck - graphology 0.26 type defs don't match runtime API
"use client"

import { useEffect, useRef, useMemo } from "react"
import { useTheme } from "next-themes"
import Graph from "graphology"
import Sigma from "sigma"
import { circular } from "graphology-layout"
import louvain from "graphology-communities-louvain"
import type { SigmaGraphProps } from "./sigma-graph"

const NODE_COLORS: Record<string, string> = {
  enterprise: "#3b82f6",
  dirigeant: "#a855f7",
  sector: "#22c55e",
  territory: "#f59e0b",
  institution: "#06b6d4",
  association: "#f97316",
  financial: "#ec4899",
  default: "#94a3b8",
}

export default function SigmaGraphInner({
  nodes,
  edges,
  onNodeClick,
  height = "500px",
  className,
}: SigmaGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const sigmaRef = useRef<Sigma | null>(null)
  const { resolvedTheme } = useTheme()

  const graph = useMemo(() => {
    const g = new Graph()
    const added = new Set<string>()
    nodes.forEach((node) => {
      if (!added.has(node.id)) {
        added.add(node.id)
        g.addNode(node.id, {
          label: node.label,
          size: node.size || 5,
          color: NODE_COLORS[node.type] || NODE_COLORS.default,
          type: node.type,
        })
      }
    })
    edges.forEach((edge) => {
      if (g.hasNode(edge.source) && g.hasNode(edge.target) && !g.hasEdge(edge.source, edge.target)) {
        g.addEdge(edge.source, edge.target, {
          label: edge.label,
          weight: edge.weight || 1,
          size: Math.min((edge.weight || 1) * 0.5, 3),
        })
      }
    })
    if (g.order > 0) {
      circular.assign(g)
      try {
        louvain.assign(g)
      } catch {
        // Louvain may fail on disconnected or trivial graphs
      }
    }
    return g
  }, [nodes, edges])

  useEffect(() => {
    if (!containerRef.current || graph.order === 0) return
    const isDark = resolvedTheme === "dark"

    // Kill previous instance
    if (sigmaRef.current) {
      sigmaRef.current.kill()
      sigmaRef.current = null
    }

    const renderer = new Sigma(graph, containerRef.current, {
      renderLabels: true,
      labelColor: { color: isDark ? "#f1f5f9" : "#0f172a" },
      labelRenderedSizeThreshold: 8,
      defaultEdgeColor: isDark ? "#334155" : "#cbd5e1",
      defaultEdgeType: "line",
      stagePadding: 30,
    })

    sigmaRef.current = renderer

    if (onNodeClick) {
      renderer.on("clickNode", ({ node }) => {
        onNodeClick(node, graph.getNodeAttributes(node))
      })
    }

    return () => {
      renderer.kill()
      sigmaRef.current = null
    }
  }, [graph, resolvedTheme, onNodeClick])

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ height, width: "100%", background: "transparent" }}
    />
  )
}
