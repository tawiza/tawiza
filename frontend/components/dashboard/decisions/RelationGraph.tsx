'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import type { Stakeholder, StakeholderRelation } from '@/lib/api-decisions';
import { Badge } from '@/components/ui/badge';
import { Share2 } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';

// Theme-aligned colors (visible on both light & dark backgrounds)
const TYPE_COLORS: Record<string, string> = {
  collectivite: 'hsl(210, 70%, 58%)',   // blue
  entreprise: 'hsl(35, 80%, 55%)',      // amber
  institution: 'hsl(152, 55%, 50%)',    // green
  association: 'hsl(280, 55%, 65%)',    // purple
};

const RELATION_COLORS: Record<string, string> = {
  collaboration: 'hsl(152, 55%, 50%)',  // green
  hierarchie: 'hsl(210, 70%, 58%)',     // blue
  financement: 'hsl(35, 80%, 55%)',     // amber
  opposition: 'hsl(0, 60%, 55%)',       // red
  consultation: 'hsl(245, 58%, 64%)',   // primary/indigo
};

interface Props {
  stakeholders: Stakeholder[];
  relations: StakeholderRelation[];
  isLoading: boolean;
}

export function RelationGraph({ stakeholders, relations, isLoading }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; content: string } | null>(null);
  const [dimensions, setDimensions] = useState<{ width: number; height: number }>({ width: 0, height: 0 });

  // ResizeObserver to always get correct container dimensions
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          setDimensions({ width, height });
        }
      }
    });

    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  // D3 rendering
  useEffect(() => {
    if (!svgRef.current || stakeholders.length === 0) return;
    if (dimensions.width === 0 || dimensions.height === 0) return;

    const { width, height } = dimensions;

    // Resolve CSS custom properties for foreground/background
    const computedStyle = getComputedStyle(document.documentElement);
    const fgRaw = computedStyle.getPropertyValue('--foreground').trim();
    const bgRaw = computedStyle.getPropertyValue('--background').trim();
    const fgColor = fgRaw ? `hsl(${fgRaw})` : '#e4e4e7';
    const bgColor = bgRaw ? `hsl(${bgRaw})` : '#09090b';

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg.attr('width', width).attr('height', height);
    svg.attr('viewBox', `0 0 ${width} ${height}`);

    const container = containerRef.current!;

    // Prepare data
    const nodes = stakeholders.map(s => ({
      id: s.id,
      name: s.name,
      role: s.role,
      org: s.organization,
      type: s.type,
      influence: s.influence_level,
    }));

    const nodeIds = new Set(nodes.map(n => n.id));
    const links = relations
      .filter(r => nodeIds.has(r.from_id) && nodeIds.has(r.to_id))
      .map(r => ({
        source: r.from_id,
        target: r.to_id,
        type: r.type,
        strength: r.strength,
        description: r.description,
      }));

    // Force simulation
    const simulation = d3.forceSimulation(nodes as any)
      .force('link', d3.forceLink(links as any).id((d: any) => d.id).distance(120))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius((d: any) => d.influence * 8 + 10));

    const g = svg.append('g');

    // Zoom
    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.3, 3])
        .on('zoom', (event) => g.attr('transform', event.transform))
    );

    // Links
    const link = g.selectAll('.link')
      .data(links)
      .enter()
      .append('line')
      .attr('class', 'link')
      .attr('stroke', (d: any) => RELATION_COLORS[d.type] || 'hsl(225, 10%, 40%)')
      .attr('stroke-width', (d: any) => d.strength * 1.5)
      .attr('stroke-opacity', 0.5)
      .style('cursor', 'pointer')
      .on('mouseenter', function (event, d: any) {
        d3.select(this).attr('stroke-opacity', 1).attr('stroke-width', (d: any) => d.strength * 2.5);
        const rect = container.getBoundingClientRect();
        setTooltip({
          x: event.clientX - rect.left,
          y: event.clientY - rect.top,
          content: `${d.type}${d.description ? ': ' + d.description : ''}`,
        });
      })
      .on('mouseleave', function (event, d: any) {
        d3.select(this).attr('stroke-opacity', 0.5).attr('stroke-width', (d: any) => d.strength * 1.5);
        setTooltip(null);
      });

    // Node groups
    const node = g.selectAll('.node')
      .data(nodes)
      .enter()
      .append('g')
      .attr('class', 'node')
      .style('cursor', 'grab')
      .call(
        d3.drag<SVGGElement, any>()
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
          })
      );

    // Node circles
    node.append('circle')
      .attr('r', (d: any) => d.influence * 6 + 8)
      .attr('fill', (d: any) => TYPE_COLORS[d.type] || 'hsl(225, 10%, 40%)')
      .attr('fill-opacity', 0.85)
      .attr('stroke', (d: any) => TYPE_COLORS[d.type] || 'hsl(225, 10%, 40%)')
      .attr('stroke-width', 2)
      .attr('stroke-opacity', 0.4)
      .on('mouseenter', function (event, d: any) {
        d3.select(this).attr('fill-opacity', 1).attr('stroke-width', 3).attr('stroke-opacity', 0.8);
        const rect = container.getBoundingClientRect();
        setTooltip({
          x: event.clientX - rect.left,
          y: event.clientY - rect.top,
          content: `${d.name}\n${d.role} — ${d.org}\nInfluence: ${'★'.repeat(d.influence)}`,
        });
      })
      .on('mouseleave', function () {
        d3.select(this).attr('fill-opacity', 0.85).attr('stroke-width', 2).attr('stroke-opacity', 0.4);
        setTooltip(null);
      });

    // Node labels (last name, below the node)
    node.append('text')
      .text((d: any) => d.name.split(' ').pop())
      .attr('text-anchor', 'middle')
      .attr('dy', (d: any) => d.influence * 6 + 20)
      .attr('fill', fgColor)
      .attr('font-size', '10px')
      .attr('opacity', 0.8)
      .attr('pointer-events', 'none');

    // Initials (inside the node)
    node.append('text')
      .text((d: any) => d.name.split(' ').map((w: string) => w[0]).join('').slice(0, 2))
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('fill', bgColor)
      .attr('font-size', '11px')
      .attr('font-weight', '700')
      .attr('pointer-events', 'none');

    // Update positions
    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);
      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    return () => { simulation.stop(); };
  }, [stakeholders, relations, dimensions]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <Skeleton className="w-full h-full rounded-xl" />
      </div>
    );
  }

  if (stakeholders.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-muted-foreground">
        <Share2 className="w-12 h-12 mb-4 opacity-20" />
        <p className="text-sm font-medium">Aucun acteur a visualiser</p>
        <p className="text-xs text-muted-foreground/70 mt-2 max-w-xs text-center">
          Ajoutez des acteurs dans l&apos;onglet Acteurs et creez des relations entre eux pour visualiser le reseau territorial.
        </p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full min-h-[500px] bg-card rounded-xl border border-border"
      style={{ contain: 'size layout' }}
    >
      <svg
        ref={svgRef}
        className="absolute inset-0 w-full h-full"
        style={{ display: 'block' }}
      />

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute pointer-events-none z-50 px-3 py-2 text-xs bg-popover text-popover-foreground border border-border rounded-lg shadow-lg whitespace-pre-line"
          style={{ left: tooltip.x, top: tooltip.y - 10, transform: 'translate(-50%, -100%)' }}
        >
          {tooltip.content}
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-3 left-3 bg-card/90 backdrop-blur-sm border border-border rounded-lg px-3 py-2 text-xs space-y-1">
        <p className="text-section-label mb-1">Acteurs</p>
        {Object.entries(TYPE_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
            <span className="capitalize text-muted-foreground">{type}</span>
          </div>
        ))}
        <p className="text-section-label mt-2 mb-1">Relations</p>
        {Object.entries(RELATION_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1.5">
            <div className="w-4 h-0.5 rounded" style={{ backgroundColor: color }} />
            <span className="capitalize text-muted-foreground">{type}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
