"use client"

import dynamic from "next/dynamic"

export interface GraphNode {
  id: string
  label: string
  type: string
  size?: number
  x?: number
  y?: number
  [key: string]: any
}

export interface GraphEdge {
  source: string
  target: string
  label?: string
  weight?: number
  type?: string
}

export interface SigmaGraphProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  onNodeClick?: (nodeId: string, attrs: Record<string, any>) => void
  height?: string
  className?: string
}

const SigmaGraphInner = dynamic(() => import("./sigma-graph-inner"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-96 text-muted-foreground">
      Chargement du graphe...
    </div>
  ),
})

export function SigmaGraph(props: SigmaGraphProps) {
  return <SigmaGraphInner {...props} />
}
