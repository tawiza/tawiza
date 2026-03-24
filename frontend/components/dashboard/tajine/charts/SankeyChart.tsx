'use client';

import { useEffect, useRef, useState, useMemo } from 'react';
import * as d3 from 'd3';
import { useTAJINE } from '@/contexts/TAJINEContext';
import { HiOutlineSparkles } from 'react-icons/hi2';

// Nord color palette for flow types
const FLOW_COLORS = {
  creation: 'var(--success)',    // nord14 - green (new enterprises)
  transfer: 'var(--chart-1)',    // nord8 - cyan (transfers)
  cessation: 'var(--error)',   // nord11 - red (closures)
  growth: 'var(--warning)',      // nord13 - yellow (growth)
  investment: 'var(--chart-4)',  // nord15 - purple (investment)
};

const COLORS = {
  text: 'hsl(var(--foreground))',
  node: 'var(--chart-2)',
  nodeDark: 'var(--chart-3)',
  link: 'rgba(136, 192, 208, 0.4)',
  border: 'hsl(var(--border))',
};

interface SankeyNode {
  id: string;
  name: string;
  category: 'source' | 'sector' | 'destination';
  value?: number;
}

interface SankeyLink {
  source: string;
  target: string;
  value: number;
  type?: keyof typeof FLOW_COLORS;
}

interface SankeyChartProps {
  nodes?: SankeyNode[];
  links?: SankeyLink[];
  isLoading?: boolean;
  /** Use live data from context analysis when available */
  useLiveData?: boolean;
}


// Simple Sankey layout calculation with proper link stacking
function computeSankeyLayout(
  nodes: SankeyNode[],
  links: SankeyLink[],
  width: number,
  height: number
) {
  const nodeWidth = 18;
  const nodePadding = 12;
  const marginX = 60; // space for labels
  const columnPositions = { source: marginX, sector: width / 2, destination: width - marginX };

  // Group nodes by category
  const nodesByCategory = {
    source: nodes.filter(n => n.category === 'source'),
    sector: nodes.filter(n => n.category === 'sector'),
    destination: nodes.filter(n => n.category === 'destination'),
  };

  // Calculate node values (sum of incoming/outgoing flows)
  const nodeValues = new Map<string, number>();
  nodes.forEach(n => {
    const incoming = links.filter(l => l.target === n.id).reduce((sum, l) => sum + l.value, 0);
    const outgoing = links.filter(l => l.source === n.id).reduce((sum, l) => sum + l.value, 0);
    nodeValues.set(n.id, Math.max(incoming, outgoing, 1));
  });

  // Position nodes
  const positionedNodes: (SankeyNode & { x: number; y: number; height: number })[] = [];

  Object.entries(nodesByCategory).forEach(([category, catNodes]) => {
    if (catNodes.length === 0) return;
    const x = columnPositions[category as keyof typeof columnPositions];
    const totalValue = catNodes.reduce((sum, n) => sum + (nodeValues.get(n.id) || 1), 0);
    const availableHeight = height - (catNodes.length - 1) * nodePadding;
    let currentY = 0;

    catNodes.forEach(node => {
      const value = nodeValues.get(node.id) || 1;
      const nodeHeight = Math.max(12, (value / totalValue) * availableHeight);

      positionedNodes.push({
        ...node,
        x: x - nodeWidth / 2,
        y: currentY,
        height: nodeHeight,
      });

      currentY += nodeHeight + nodePadding;
    });

    // Center the column vertically
    const totalUsed = currentY - nodePadding;
    const offsetY = Math.max(0, (height - totalUsed) / 2);
    const startIdx = positionedNodes.length - catNodes.length;
    for (let i = startIdx; i < positionedNodes.length; i++) {
      positionedNodes[i].y += offsetY;
    }
  });

  // Create node lookup
  const nodeMap = new Map(positionedNodes.map(n => [n.id, n]));

  // Track used positions on each side of each node for link stacking
  const sourceOffsets = new Map<string, number>(); // right side of source nodes
  const targetOffsets = new Map<string, number>(); // left side of target nodes
  positionedNodes.forEach(n => {
    sourceOffsets.set(n.id, 0);
    targetOffsets.set(n.id, 0);
  });

  // Sort links by value (larger first for better visual)
  const sortedLinks = [...links].sort((a, b) => b.value - a.value);

  // Calculate link paths with stacking
  const positionedLinks = sortedLinks.map(link => {
    const sourceNode = nodeMap.get(link.source);
    const targetNode = nodeMap.get(link.target);
    if (!sourceNode || !targetNode) return null;

    const sourceTotal = nodeValues.get(link.source) || 1;
    const targetTotal = nodeValues.get(link.target) || 1;
    const linkThickness = Math.max(2, Math.min(
      (link.value / sourceTotal) * sourceNode.height,
      (link.value / targetTotal) * targetNode.height
    ));

    const srcOff = sourceOffsets.get(link.source) || 0;
    const tgtOff = targetOffsets.get(link.target) || 0;

    const sourceY = sourceNode.y + srcOff + linkThickness / 2;
    const targetY = targetNode.y + tgtOff + linkThickness / 2;

    sourceOffsets.set(link.source, srcOff + linkThickness);
    targetOffsets.set(link.target, tgtOff + linkThickness);

    const sourceX = sourceNode.x + nodeWidth;
    const targetX = targetNode.x;
    const midX = sourceX + (targetX - sourceX) * 0.5;

    return {
      ...link,
      sourceNode,
      targetNode,
      thickness: linkThickness,
      path: `M ${sourceX},${sourceY} C ${midX},${sourceY} ${midX},${targetY} ${targetX},${targetY}`,
    };
  }).filter(Boolean);

  return { nodes: positionedNodes, links: positionedLinks };
}

export default function SankeyChart({ nodes, links, isLoading, useLiveData = true }: SankeyChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; content: string } | null>(null);
  const { selectedDepartment, latestAnalysis } = useTAJINE();

  // Check if we have live analysis data
  const liveData = useMemo(() => {
    if (!useLiveData || !latestAnalysis?.sankeyData) return null;
    if (selectedDepartment && latestAnalysis.department !== selectedDepartment) return null;
    return latestAnalysis.sankeyData;
  }, [useLiveData, latestAnalysis, selectedDepartment]);

  const isUsingLiveData = !!liveData;

  const chartNodes = useMemo(() => {
    if (liveData?.nodes) return liveData.nodes;
    if (nodes) return nodes;
    return [];
  }, [liveData, nodes]);

  const chartLinks = useMemo(() => {
    if (liveData?.links) return liveData.links;
    if (links) return links;
    return [];
  }, [liveData, links]);

  const hasData = chartNodes.length > 0 && chartLinks.length > 0;

  useEffect(() => {
    if (!svgRef.current || !containerRef.current || !hasData) return;

    const container = containerRef.current;
    const width = container.clientWidth || 600;
    const height = container.clientHeight || 300;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg.attr('viewBox', `0 0 ${width} ${height}`);

    // Compute layout
    const { nodes: positionedNodes, links: positionedLinks } = computeSankeyLayout(
      chartNodes,
      chartLinks,
      width,
      height - 40
    );

    const g = svg.append('g').attr('transform', 'translate(0, 20)');

    // Draw links
    g.selectAll('.sankey-link')
      .data(positionedLinks)
      .enter()
      .append('path')
      .attr('class', 'sankey-link')
      .attr('d', (d: any) => d.path)
      .attr('fill', 'none')
      .attr('stroke', (d: any) => FLOW_COLORS[d.type as keyof typeof FLOW_COLORS] || COLORS.link)
      .attr('stroke-width', (d: any) => d.thickness || Math.max(3, Math.sqrt(d.value) * 1.5))
      .attr('stroke-opacity', 0.5)
      .style('cursor', 'pointer')
      .on('mouseenter', function(event, d: any) {
        d3.select(this).attr('stroke-opacity', 0.8);
        const rect = container.getBoundingClientRect();
        setTooltip({
          x: event.clientX - rect.left,
          y: event.clientY - rect.top,
          content: `${d.sourceNode.name} → ${d.targetNode.name}\nFlux: ${d.value.toLocaleString()}`,
        });
      })
      .on('mouseleave', function() {
        d3.select(this).attr('stroke-opacity', 0.5);
        setTooltip(null);
      });

    // Draw nodes
    const nodeGroups = g.selectAll('.sankey-node')
      .data(positionedNodes)
      .enter()
      .append('g')
      .attr('class', 'sankey-node')
      .attr('transform', (d: any) => `translate(${d.x}, ${d.y})`);

    // Node rectangles
    nodeGroups.append('rect')
      .attr('width', 20)
      .attr('height', (d: any) => d.height)
      .attr('fill', (d: any) => {
        if (d.category === 'source') return 'var(--success)';
        if (d.category === 'sector') return 'var(--chart-1)';
        return 'var(--warning)';
      })
      .attr('rx', 4)
      .attr('stroke', COLORS.border)
      .attr('stroke-width', 1)
      .style('cursor', 'pointer')
      .on('mouseenter', function(event, d: any) {
        d3.select(this).attr('stroke-width', 2).attr('stroke', COLORS.text);
        const rect = container.getBoundingClientRect();
        setTooltip({
          x: event.clientX - rect.left,
          y: event.clientY - rect.top,
          content: d.name,
        });
      })
      .on('mouseleave', function() {
        d3.select(this).attr('stroke-width', 1).attr('stroke', COLORS.border);
        setTooltip(null);
      });

    // Node labels
    nodeGroups.append('text')
      .attr('x', (d: any) => {
        if (d.category === 'source') return -5;
        if (d.category === 'destination') return 25;
        return 10; // sector: centered on node
      })
      .attr('y', (d: any) => {
        if (d.category === 'sector') return -5; // above the node
        return d.height / 2;
      })
      .attr('dy', (d: any) => d.category === 'sector' ? '0' : '0.35em')
      .attr('text-anchor', (d: any) => {
        if (d.category === 'source') return 'end';
        if (d.category === 'destination') return 'start';
        return 'middle';
      })
      .attr('fill', COLORS.text)
      .attr('font-size', '10px')
      .text((d: any) => d.name);

  }, [chartNodes, chartLinks, hasData]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[220px] sm:h-[280px] md:h-[350px]">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!hasData) {
    return (
      <div className="flex flex-col items-center justify-center h-[220px] sm:h-[280px] md:h-[350px] text-muted-foreground">
        <HiOutlineSparkles className="w-10 h-10 sm:w-12 sm:h-12 mb-3 opacity-30" />
        <p className="text-xs sm:text-sm text-center px-4">Aucune donnee disponible</p>
        <p className="text-[10px] sm:text-xs mt-1 text-center px-4">Lancez une analyse pour visualiser les flux</p>
      </div>
    );
  }

  return (
    <div className="relative w-full h-[220px] sm:h-[280px] md:h-[350px] flex flex-col">
      {/* Live data indicator */}
      {isUsingLiveData && (
        <div className="absolute top-2 left-2 flex items-center gap-1 px-2 py-1 glass rounded-lg text-xs z-10">
          <HiOutlineSparkles className="w-3 h-3 text-[var(--success)] animate-pulse" />
          <span className="text-[var(--success)]">Live</span>
        </div>
      )}
      {/* Chart area with reserved space for legend */}
      <div ref={containerRef} className="flex-1 min-h-0">
        <svg ref={svgRef} className="w-full h-full" />
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute pointer-events-none z-50 px-3 py-2 text-xs glass rounded-lg whitespace-pre-line"
          style={{
            left: tooltip.x,
            top: tooltip.y - 10,
            transform: 'translate(-50%, -100%)',
          }}
        >
          {tooltip.content}
        </div>
      )}

      {/* Legend - positioned in flex flow, not overlapping */}
      <div className="flex items-center justify-between mt-3 px-1">
        <div className="flex gap-3 sm:gap-4 text-xs glass px-3 py-2 rounded-lg">
          <span className="flex items-center gap-1">
            <div className="w-3 h-3 rounded" style={{ backgroundColor: 'var(--success)' }} />
            Sources
          </span>
          <span className="flex items-center gap-1">
            <div className="w-3 h-3 rounded" style={{ backgroundColor: 'var(--chart-1)' }} />
            Secteurs
          </span>
          <span className="flex items-center gap-1">
            <div className="w-3 h-3 rounded" style={{ backgroundColor: 'var(--warning)' }} />
            Resultats
          </span>
        </div>
        {selectedDepartment && (
          <span className="text-xs glass px-2 py-1 rounded">
            Dept. {selectedDepartment}
          </span>
        )}
      </div>
    </div>
  );
}
