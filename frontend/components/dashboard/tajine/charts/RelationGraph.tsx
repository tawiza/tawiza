'use client';

import { useEffect, useRef, useState, useMemo } from 'react';
import * as d3 from 'd3';
import { useTAJINE } from '@/contexts/TAJINEContext';
import { HiOutlineSparkles } from 'react-icons/hi2';

// Nord colors by node type
const NODE_COLORS: Record<string, string> = {
  enterprise: 'var(--chart-1)',  // nord8 - cyan
  sector: 'var(--success)',      // nord14 - green
  territory: 'var(--chart-4)',   // nord15 - purple
};

const LINK_COLOR = 'hsl(var(--border))';
const TEXT_COLOR = 'hsl(var(--foreground))';

interface GraphNode {
  id: string;
  label: string;
  type: 'enterprise' | 'sector' | 'territory';
  size?: number;
}

interface GraphLink {
  source: string;
  target: string;
  weight: number;
}

interface RelationGraphProps {
  nodes?: GraphNode[];
  links?: GraphLink[];
  isLoading?: boolean;
}

export default function RelationGraph({ nodes, links, isLoading }: RelationGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; content: string } | null>(null);
  const { selectedDepartment } = useTAJINE();

  const graphNodes = useMemo(() => {
    if (nodes && nodes.length > 0) return nodes;
    return [];
  }, [nodes]);

  const graphLinks = useMemo(() => {
    if (links && links.length > 0) return links;
    return [];
  }, [links]);

  const hasData = graphNodes.length > 0 && graphLinks.length > 0;

  useEffect(() => {
    if (!svgRef.current || !containerRef.current || !hasData) return;

    const container = containerRef.current;
    const width = container.clientWidth || 500;
    const height = container.clientHeight || 300;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg.attr('viewBox', `0 0 ${width} ${height}`);

    // Create simulation
    const simulation = d3.forceSimulation(graphNodes as d3.SimulationNodeDatum[])
      .force('link', d3.forceLink(graphLinks)
        .id((d: any) => d.id)
        .distance(80)
        .strength((d: any) => d.weight * 0.1))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius((d: any) => (d.size || 10) + 5));

    // Main group for zoom
    const g = svg.append('g');

    // Draw links
    const link = g.selectAll('.link')
      .data(graphLinks)
      .enter()
      .append('line')
      .attr('class', 'link')
      .attr('stroke', LINK_COLOR)
      .attr('stroke-width', (d: any) => Math.sqrt(d.weight))
      .attr('stroke-opacity', 0.6);

    // Draw nodes
    const node = g.selectAll('.node')
      .data(graphNodes)
      .enter()
      .append('g')
      .attr('class', 'node')
      .style('cursor', 'pointer')
      .call(d3.drag<any, any>()
        .on('start', (event, d: any) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d: any) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event, d: any) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        }));

    // Node circles
    node.append('circle')
      .attr('r', (d: any) => d.size || 10)
      .attr('fill', (d: any) => NODE_COLORS[d.type] || NODE_COLORS.enterprise)
      .attr('stroke', 'hsl(var(--background))')
      .attr('stroke-width', 2)
      .on('mouseenter', function(event, d: any) {
        d3.select(this).attr('stroke-width', 3).attr('stroke', TEXT_COLOR);
        const rect = container.getBoundingClientRect();
        setTooltip({
          x: event.clientX - rect.left,
          y: event.clientY - rect.top - 10,
          content: `${d.label}\nType: ${d.type}`
        });
      })
      .on('mouseleave', function() {
        d3.select(this).attr('stroke-width', 2).attr('stroke', 'hsl(var(--background))');
        setTooltip(null);
      });

    // Node labels
    node.append('text')
      .attr('dy', (d: any) => (d.size || 10) + 12)
      .attr('text-anchor', 'middle')
      .attr('fill', TEXT_COLOR)
      .attr('font-size', '10px')
      .text((d: any) => d.label);

    // Tick function
    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    // Zoom
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);

    return () => {
      simulation.stop();
    };
  }, [graphNodes, graphLinks, hasData]);

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
        <p className="text-xs sm:text-sm">Aucune donnee disponible</p>
        <p className="text-[10px] sm:text-xs mt-1">Lancez une analyse pour visualiser les relations</p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative w-full h-[220px] sm:h-[280px] md:h-[350px]">
      <svg ref={svgRef} className="w-full h-full" />

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute pointer-events-none z-50 px-2 sm:px-3 py-1.5 sm:py-2 text-[10px] sm:text-xs glass rounded-lg whitespace-pre-line"
          style={{
            left: tooltip.x,
            top: tooltip.y,
            transform: 'translate(-50%, -100%)',
          }}
        >
          {tooltip.content}
        </div>
      )}

      {/* Legend - responsive */}
      <div className="absolute bottom-2 left-2 flex flex-wrap gap-2 sm:gap-4 text-[10px] sm:text-xs glass px-2 sm:px-3 py-1.5 sm:py-2 rounded-lg">
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <span key={type} className="flex items-center gap-1">
            <div className="w-2.5 sm:w-3 h-2.5 sm:h-3 rounded-full" style={{ backgroundColor: color }} />
            {type.charAt(0).toUpperCase() + type.slice(1)}
          </span>
        ))}
      </div>

      {selectedDepartment && (
        <p className="absolute top-2 right-2 text-[10px] sm:text-xs glass px-2 py-1 rounded">
          Dept. {selectedDepartment}
        </p>
      )}
    </div>
  );
}
