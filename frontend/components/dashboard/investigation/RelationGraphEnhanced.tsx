'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import type { RelationGraphData, GraphNode, GraphLink, NetworkAnalytics, ActorType } from '@/types/relations';
import { ACTOR_COLORS, RELATION_STYLES } from '@/types/relations';
import type { ColorMode } from './GraphFilters';

interface RelationGraphEnhancedProps {
  data: RelationGraphData | null;
  isLoading?: boolean;
  onNodeClick?: (node: GraphNode) => void;
  enabledTypes?: Set<string>;
  enabledLevels?: Set<string>;
  searchQuery?: string;
  selectedCommunity?: number | null;
  colorMode?: ColorMode;
  analytics?: NetworkAnalytics | null;
  fullscreen?: boolean;
  onToggleFullscreen?: () => void;
}

interface SimNode extends GraphNode {
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

interface SimLink extends Omit<GraphLink, 'source' | 'target'> {
  source: SimNode | string;
  target: SimNode | string;
}

// Community palette (12 distinct colors)
const COMMUNITY_COLORS = [
  '#88C0D0', '#A3BE8C', '#EBCB8B', '#BF616A', '#B48EAD',
  '#D08770', '#5E81AC', '#81A1C1', '#8FBCBB', '#A3D9A5',
  '#F0B775', '#C97B84',
];

/** Interpolate green→yellow→red for risk scores */
function riskColor(score: number): string {
  if (score <= 0.5) {
    const t = score * 2; // 0→1 for green→yellow
    const r = Math.round(163 + (235 - 163) * t);
    const g = Math.round(190 + (203 - 190) * t);
    const b = Math.round(140 + (139 - 140) * t);
    return `rgb(${r},${g},${b})`;
  }
  const t = (score - 0.5) * 2; // 0→1 for yellow→red
  const r = Math.round(235 + (191 - 235) * t);
  const g = Math.round(203 + (97 - 203) * t);
  const b = Math.round(139 + (106 - 139) * t);
  return `rgb(${r},${g},${b})`;
}

/** Interpolate blue→purple for Shapley values */
function shapleyColor(value: number): string {
  const r = Math.round(94 + (180 - 94) * value);
  const g = Math.round(129 + (78 - 129) * value);
  const b = Math.round(172 + (173 - 172) * value);
  return `rgb(${r},${g},${b})`;
}

/**
 * Draw a node shape on a Canvas context based on the actor type.
 */
function drawNodeShape(
  ctx: CanvasRenderingContext2D,
  node: SimNode,
  x: number,
  y: number,
  r: number,
  color: string,
) {
  ctx.fillStyle = color;
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;

  switch (node.type) {
    case 'territory': {
      ctx.beginPath();
      for (let i = 0; i < 6; i++) {
        const angle = (Math.PI / 3) * i - Math.PI / 6;
        const px = x + r * Math.cos(angle);
        const py = y + r * Math.sin(angle);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      ctx.globalAlpha = 0.3;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.stroke();
      break;
    }
    case 'institution': {
      ctx.beginPath();
      ctx.moveTo(x, y - r);
      ctx.lineTo(x + r, y);
      ctx.lineTo(x, y + r);
      ctx.lineTo(x - r, y);
      ctx.closePath();
      ctx.globalAlpha = 0.3;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.stroke();
      break;
    }
    case 'sector': {
      const side = r * 0.7;
      ctx.globalAlpha = 0.3;
      ctx.fillRect(x - side, y - side, side * 2, side * 2);
      ctx.globalAlpha = 1;
      ctx.strokeRect(x - side, y - side, side * 2, side * 2);
      break;
    }
    case 'association': {
      ctx.beginPath();
      const triSize = r * 1.2;
      ctx.moveTo(x, y - triSize);
      ctx.lineTo(x - triSize, y + triSize * 0.7);
      ctx.lineTo(x + triSize, y + triSize * 0.7);
      ctx.closePath();
      ctx.globalAlpha = 0.3;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.stroke();
      break;
    }
    case 'formation': {
      ctx.beginPath();
      const pentSize = r;
      for (let i = 0; i < 5; i++) {
        const angle = (i * 2 * Math.PI / 5) - Math.PI / 2;
        const px = x + pentSize * Math.cos(angle);
        const py = y + pentSize * Math.sin(angle);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      ctx.globalAlpha = 0.3;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.stroke();
      break;
    }
    case 'financial': {
      ctx.beginPath();
      const outerR = r * 1.2;
      const innerR = r * 0.5;
      for (let i = 0; i < 10; i++) {
        const sr = i % 2 === 0 ? outerR : innerR;
        const angle = (i * Math.PI / 5) - Math.PI / 2;
        const px = x + sr * Math.cos(angle);
        const py = y + sr * Math.sin(angle);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      ctx.globalAlpha = 0.3;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.stroke();
      break;
    }
    default: {
      ctx.beginPath();
      ctx.arc(x, y, r, 0, 2 * Math.PI);
      ctx.globalAlpha = 0.3;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.stroke();
      break;
    }
  }
}

/**
 * RelationGraphEnhanced - Canvas-based D3.js force simulation graph.
 *
 * Supports zoom, pan, drag, hover tooltips, click, mini-map,
 * filtering by type/level/community/search, and dynamic coloration.
 */
export default function RelationGraphEnhanced({
  data,
  isLoading,
  onNodeClick,
  enabledTypes,
  enabledLevels,
  searchQuery,
  selectedCommunity,
  colorMode = 'type',
  analytics,
  fullscreen = false,
  onToggleFullscreen,
}: RelationGraphEnhancedProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    node: GraphNode;
  } | null>(null);

  // Store filter props in refs so the draw() closure always reads current values
  const filtersRef = useRef({
    enabledTypes: enabledTypes ?? new Set<string>(),
    enabledLevels: enabledLevels ?? new Set(['structural', 'inferred', 'hypothetical']),
    searchQuery: searchQuery ?? '',
    selectedCommunity: selectedCommunity ?? null as number | null,
    colorMode: colorMode,
    analytics: analytics ?? null as NetworkAnalytics | null,
  });
  filtersRef.current = {
    enabledTypes: enabledTypes ?? new Set<string>(),
    enabledLevels: enabledLevels ?? new Set(['structural', 'inferred', 'hypothetical']),
    searchQuery: searchQuery ?? '',
    selectedCommunity: selectedCommunity ?? null,
    colorMode: colorMode,
    analytics: analytics ?? null,
  };

  const onNodeClickRef = useRef(onNodeClick);
  onNodeClickRef.current = onNodeClick;

  // Reference to the draw function so we can trigger redraws from outside the effect
  const drawRef = useRef<(() => void) | null>(null);

  const clearTooltip = useCallback(() => setTooltip(null), []);

  // Trigger redraw when filters change (without resetting the simulation)
  useEffect(() => {
    if (drawRef.current) drawRef.current();
  }, [enabledTypes, enabledLevels, searchQuery, selectedCommunity, colorMode, analytics]);

  useEffect(() => {
    if (!canvasRef.current || !containerRef.current || !data || data.nodes.length === 0) return;

    const canvas = canvasRef.current;
    const container = containerRef.current;
    const width = container.clientWidth || 600;
    const height = container.clientHeight || 400;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const transform = { x: 0, y: 0, k: 1 };
    let isPanning = false;
    const panStart = { x: 0, y: 0 };
    const panTransformStart = { x: 0, y: 0 };

    function screenToGraph(sx: number, sy: number) {
      return {
        x: (sx - transform.x) / transform.k,
        y: (sy - transform.y) / transform.k,
      };
    }

    // Clone data — simulation runs on ALL data (filters apply during draw)
    const nodes: SimNode[] = data.nodes.map((n) => ({ ...n }));
    const links: SimLink[] = data.links.map((l) => ({ ...l }));

    const simulation = d3
      .forceSimulation(nodes)
      .force(
        'link',
        d3
          .forceLink<SimNode, SimLink>(links)
          .id((d) => d.id)
          .distance(80)
          .strength(0.1),
      )
      .force('charge', d3.forceManyBody().strength(-150))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide<SimNode>().radius((d) => d.size + 5));

    const MM_W = 150;
    const MM_H = 100;
    const MM_PAD = 10;

    /** Get the color for a node based on current colorMode */
    function getNodeColor(node: SimNode): string {
      const f = filtersRef.current;
      const nm = f.analytics?.node_metrics?.[node.external_id];

      switch (f.colorMode) {
        case 'risk': {
          const rs = nm && typeof (nm as Record<string, unknown>).risk_score === 'number'
            ? (nm as Record<string, unknown>).risk_score as number
            : 0.5;
          return riskColor(rs);
        }
        case 'community': {
          const cid = nm?.community_id ?? 0;
          return COMMUNITY_COLORS[cid % COMMUNITY_COLORS.length];
        }
        case 'shapley': {
          const sv = nm && typeof (nm as Record<string, unknown>).shapley === 'number'
            ? (nm as Record<string, unknown>).shapley as number
            : 0;
          return shapleyColor(sv);
        }
        default:
          return ACTOR_COLORS[node.type as ActorType] || '#88C0D0';
      }
    }

    /** Check if a node passes current filters */
    function isNodeVisible(node: SimNode): boolean {
      const f = filtersRef.current;
      if (f.enabledTypes.size > 0 && !f.enabledTypes.has(node.type)) return false;
      if (f.selectedCommunity !== null) {
        const nm = f.analytics?.node_metrics?.[node.external_id];
        if (nm?.community_id !== f.selectedCommunity) return false;
      }
      return true;
    }

    /** Check if a link passes current filters */
    function isLinkVisible(link: SimLink): boolean {
      const f = filtersRef.current;
      if (f.enabledLevels.size > 0 && !f.enabledLevels.has(link.relation_type)) return false;
      const s = link.source as SimNode;
      const t = link.target as SimNode;
      return isNodeVisible(s) && isNodeVisible(t);
    }

    /** Check if a node matches the search query */
    function isSearchMatch(node: SimNode): boolean {
      const q = filtersRef.current.searchQuery.toLowerCase();
      if (!q) return false;
      return node.label.toLowerCase().includes(q) || node.external_id.toLowerCase().includes(q);
    }

    function drawMiniMap() {
      if (!ctx) return;
      const mmX = (width - MM_W - MM_PAD) * dpr;
      const mmY = (height - MM_H - MM_PAD) * dpr;
      const mmWpx = MM_W * dpr;
      const mmHpx = MM_H * dpr;

      ctx.fillStyle = 'rgba(0, 0, 0, 0.45)';
      ctx.fillRect(mmX, mmY, mmWpx, mmHpx);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
      ctx.lineWidth = 1;
      ctx.strokeRect(mmX, mmY, mmWpx, mmHpx);

      let minGx = Infinity, maxGx = -Infinity, minGy = Infinity, maxGy = -Infinity;
      for (const node of nodes) {
        if (node.x == null || node.y == null || !isNodeVisible(node)) continue;
        if (node.x < minGx) minGx = node.x;
        if (node.x > maxGx) maxGx = node.x;
        if (node.y < minGy) minGy = node.y;
        if (node.y > maxGy) maxGy = node.y;
      }
      if (!isFinite(minGx)) return;

      const margin = 30;
      minGx -= margin; maxGx += margin;
      minGy -= margin; maxGy += margin;
      const gW = maxGx - minGx || 1;
      const gH = maxGy - minGy || 1;

      const innerPad = 4 * dpr;
      const fitW = (mmWpx - innerPad * 2) / gW;
      const fitH = (mmHpx - innerPad * 2) / gH;
      const fitScale = Math.min(fitW, fitH);
      const fitOffX = mmX + innerPad + (mmWpx - innerPad * 2 - gW * fitScale) / 2;
      const fitOffY = mmY + innerPad + (mmHpx - innerPad * 2 - gH * fitScale) / 2;

      function gToMm(gx: number, gy: number) {
        return {
          mx: fitOffX + (gx - minGx) * fitScale,
          my: fitOffY + (gy - minGy) * fitScale,
        };
      }

      ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
      ctx.lineWidth = 0.5;
      ctx.setLineDash([]);
      for (const link of links) {
        if (!isLinkVisible(link)) continue;
        const s = link.source as SimNode;
        const t = link.target as SimNode;
        if (s.x == null || s.y == null || t.x == null || t.y == null) continue;
        const p1 = gToMm(s.x, s.y);
        const p2 = gToMm(t.x, t.y);
        ctx.beginPath();
        ctx.moveTo(p1.mx, p1.my);
        ctx.lineTo(p2.mx, p2.my);
        ctx.stroke();
      }

      for (const node of nodes) {
        if (node.x == null || node.y == null || !isNodeVisible(node)) continue;
        const { mx, my } = gToMm(node.x, node.y);
        ctx.fillStyle = getNodeColor(node);
        ctx.globalAlpha = 0.7;
        ctx.beginPath();
        ctx.arc(mx, my, Math.max(1.2, node.size * fitScale * 0.5), 0, 2 * Math.PI);
        ctx.fill();
      }
      ctx.globalAlpha = 1;

      const vpTL = screenToGraph(0, 0);
      const vpBR = screenToGraph(width, height);
      const vpMmTL = gToMm(vpTL.x, vpTL.y);
      const vpMmBR = gToMm(vpBR.x, vpBR.y);
      const vpRx = Math.max(mmX, Math.min(mmX + mmWpx, vpMmTL.mx));
      const vpRy = Math.max(mmY, Math.min(mmY + mmHpx, vpMmTL.my));
      const vpRx2 = Math.max(mmX, Math.min(mmX + mmWpx, vpMmBR.mx));
      const vpRy2 = Math.max(mmY, Math.min(mmY + mmHpx, vpMmBR.my));
      const vpRw = vpRx2 - vpRx;
      const vpRh = vpRy2 - vpRy;

      if (vpRw > 0 && vpRh > 0) {
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(vpRx, vpRy, vpRw, vpRh);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.04)';
        ctx.fillRect(vpRx, vpRy, vpRw, vpRh);
      }
    }

    function draw() {
      if (!ctx) return;
      const { x: tx, y: ty, k } = transform;

      ctx.clearRect(0, 0, width * dpr, height * dpr);
      ctx.save();
      ctx.setTransform(dpr * k, 0, 0, dpr * k, dpr * tx, dpr * ty);

      // Draw visible links
      for (const link of links) {
        if (!isLinkVisible(link)) continue;
        const source = link.source as SimNode;
        const target = link.target as SimNode;
        if (source.x == null || source.y == null || target.x == null || target.y == null) continue;

        const style = RELATION_STYLES[link.relation_type] || RELATION_STYLES.structural;
        ctx.beginPath();
        ctx.moveTo(source.x, source.y);
        ctx.lineTo(target.x, target.y);
        ctx.strokeStyle = `rgba(255,255,255,${style.opacity * 0.4})`;
        ctx.lineWidth = Math.max(1, link.weight * 0.5) / k;

        if (style.dasharray !== '0') {
          ctx.setLineDash(style.dasharray.split(',').map((v: string) => Number(v) / k));
        } else {
          ctx.setLineDash([]);
        }
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // Draw visible nodes
      for (const node of nodes) {
        if (node.x == null || node.y == null || !isNodeVisible(node)) continue;

        const color = getNodeColor(node);
        drawNodeShape(ctx, node, node.x, node.y, node.size, color);

        // Search highlight: glowing ring
        if (isSearchMatch(node)) {
          ctx.save();
          ctx.strokeStyle = '#EBCB8B';
          ctx.lineWidth = 3 / k;
          ctx.shadowColor = '#EBCB8B';
          ctx.shadowBlur = 12 / k;
          ctx.beginPath();
          ctx.arc(node.x, node.y, node.size + 4 / k, 0, 2 * Math.PI);
          ctx.stroke();
          ctx.restore();
        }

        // Label
        ctx.fillStyle = 'rgba(255,255,255,0.7)';
        ctx.font = `${9 / k}px sans-serif`;
        ctx.textAlign = 'center';
        const label = node.label.length > 18 ? node.label.slice(0, 16) + '...' : node.label;
        ctx.fillText(label, node.x, node.y + node.size + 12 / k);
      }

      ctx.restore();
      drawMiniMap();
    }

    drawRef.current = draw;
    simulation.on('tick', draw);

    function findNode(screenX: number, screenY: number): SimNode | null {
      const { x: gx, y: gy } = screenToGraph(screenX, screenY);
      for (const node of nodes) {
        if (node.x == null || node.y == null || !isNodeVisible(node)) continue;
        const dx = gx - node.x;
        const dy = gy - node.y;
        if (dx * dx + dy * dy < (node.size + 5) ** 2) return node;
      }
      return null;
    }

    let dragNode: SimNode | null = null;
    let didDragOrPan = false;

    function handleMouseDown(e: MouseEvent) {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      didDragOrPan = false;

      const hit = findNode(mx, my);
      if (hit) {
        dragNode = hit;
        dragNode.fx = dragNode.x;
        dragNode.fy = dragNode.y;
        simulation.alphaTarget(0.3).restart();
      } else {
        isPanning = true;
        panStart.x = mx;
        panStart.y = my;
        panTransformStart.x = transform.x;
        panTransformStart.y = transform.y;
        canvas.style.cursor = 'grabbing';
      }
    }

    function handleMouseMove(e: MouseEvent) {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      if (dragNode) {
        const gp = screenToGraph(mx, my);
        dragNode.fx = gp.x;
        dragNode.fy = gp.y;
        didDragOrPan = true;
      } else if (isPanning) {
        transform.x = panTransformStart.x + (mx - panStart.x);
        transform.y = panTransformStart.y + (my - panStart.y);
        didDragOrPan = true;
        draw();
      } else {
        const hovered = findNode(mx, my);
        if (hovered) {
          setTooltip({ x: e.clientX, y: e.clientY, node: hovered });
          canvas.style.cursor = 'pointer';
        } else {
          setTooltip(null);
          canvas.style.cursor = 'grab';
        }
      }
    }

    function handleMouseUp() {
      if (dragNode) {
        dragNode.fx = null;
        dragNode.fy = null;
        simulation.alphaTarget(0);
        dragNode = null;
      }
      if (isPanning) {
        isPanning = false;
        canvas.style.cursor = 'grab';
      }
    }

    function handleClick(e: MouseEvent) {
      if (didDragOrPan) return;
      const rect = canvas.getBoundingClientRect();
      const clicked = findNode(e.clientX - rect.left, e.clientY - rect.top);
      if (clicked && onNodeClickRef.current) {
        onNodeClickRef.current(clicked);
      }
    }

    function handleWheel(e: WheelEvent) {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      const { x, y, k } = transform;
      const factor = e.deltaY < 0 ? 1.1 : 0.9;
      const newK = Math.max(0.1, Math.min(8, k * factor));

      transform.k = newK;
      transform.x = mouseX - (mouseX - x) * (newK / k);
      transform.y = mouseY - (mouseY - y) * (newK / k);
      draw();
    }

    canvas.style.cursor = 'grab';
    canvas.addEventListener('mousedown', handleMouseDown);
    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseup', handleMouseUp);
    canvas.addEventListener('click', handleClick);
    canvas.addEventListener('wheel', handleWheel, { passive: false });

    function handleMouseLeave() {
      if (dragNode) {
        dragNode.fx = null;
        dragNode.fy = null;
        simulation.alphaTarget(0);
        dragNode = null;
      }
      isPanning = false;
      canvas.style.cursor = 'grab';
    }
    canvas.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      simulation.stop();
      drawRef.current = null;
      canvas.removeEventListener('mousedown', handleMouseDown);
      canvas.removeEventListener('mousemove', handleMouseMove);
      canvas.removeEventListener('mouseup', handleMouseUp);
      canvas.removeEventListener('click', handleClick);
      canvas.removeEventListener('wheel', handleWheel);
      canvas.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, [data]);

  if (isLoading) {
    return (
      <div className={`glass-card p-4 flex items-center justify-center ${fullscreen ? 'h-screen' : 'h-[600px]'}`}>
        <div className="animate-spin h-6 w-6 border-2 border-white/30 border-t-white rounded-full" />
      </div>
    );
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div className={`glass-card p-4 flex items-center justify-center ${fullscreen ? 'h-screen' : 'h-[600px]'} text-white/40 text-sm`}>
        Aucune relation trouvee — lancez une decouverte
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`relative w-full glass-card overflow-hidden ${fullscreen ? 'h-screen' : 'h-[600px]'}`}
      onMouseLeave={clearTooltip}
    >
      <canvas ref={canvasRef} className="w-full h-full" />

      {/* Node type legend (bottom-left) — only show in 'type' colorMode */}
      {colorMode === 'type' && (
        <div className="absolute bottom-2 left-2 flex flex-wrap gap-2 text-[10px] text-white/60">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: ACTOR_COLORS.enterprise }} />
            Entreprise
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2" style={{ backgroundColor: ACTOR_COLORS.territory, clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }} />
            Territoire
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rotate-45" style={{ backgroundColor: ACTOR_COLORS.institution }} />
            Institution
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2" style={{ backgroundColor: ACTOR_COLORS.sector }} />
            Secteur
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2" style={{ backgroundColor: ACTOR_COLORS.association, clipPath: 'polygon(50% 0%, 0% 100%, 100% 100%)' }} />
            Association
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2" style={{ backgroundColor: ACTOR_COLORS.formation, clipPath: 'polygon(50% 0%, 100% 38%, 82% 100%, 18% 100%, 0% 38%)' }} />
            Formation
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2" style={{ backgroundColor: ACTOR_COLORS.financial, clipPath: 'polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%)' }} />
            Financier
          </span>
        </div>
      )}

      {/* Color mode legends for non-type modes */}
      {colorMode === 'risk' && (
        <div className="absolute bottom-2 left-2 flex items-center gap-2 text-[10px] text-white/60">
          <span style={{ color: riskColor(0) }}>Faible</span>
          <div className="w-24 h-2 rounded-full" style={{ background: 'linear-gradient(to right, #A3BE8C, #EBCB8B, #BF616A)' }} />
          <span style={{ color: riskColor(1) }}>Eleve</span>
        </div>
      )}
      {colorMode === 'shapley' && (
        <div className="absolute bottom-2 left-2 flex items-center gap-2 text-[10px] text-white/60">
          <span style={{ color: shapleyColor(0) }}>0</span>
          <div className="w-24 h-2 rounded-full" style={{ background: 'linear-gradient(to right, #5E81AC, #B44EAD)' }} />
          <span style={{ color: shapleyColor(1) }}>1</span>
        </div>
      )}
      {colorMode === 'community' && (
        <div className="absolute bottom-2 left-2 flex flex-wrap gap-1 text-[10px] text-white/60">
          {COMMUNITY_COLORS.slice(0, 8).map((c, i) => (
            <span key={i} className="flex items-center gap-0.5">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: c }} />
              {i}
            </span>
          ))}
        </div>
      )}

      {/* Link style legend */}
      <div className="absolute bottom-[120px] right-2 flex gap-3 text-[10px] text-white/60">
        <span>&mdash;&mdash; L1 verifie</span>
        <span>- - L2 infere</span>
        <span>&middot;&middot;&middot; L3 hypothetique</span>
      </div>

      {/* Fullscreen toggle + zoom hint */}
      <div className="absolute top-2 right-2 flex items-center gap-2">
        <span className="text-[10px] text-white/30 select-none pointer-events-none">
          Molette = zoom | Clic vide = deplacer{fullscreen ? ' | Echap = quitter' : ''}
        </span>
        {onToggleFullscreen && (
          <button
            onClick={onToggleFullscreen}
            className="p-1.5 rounded bg-white/10 hover:bg-white/20 text-white/60 hover:text-white transition-colors"
            title={fullscreen ? 'Quitter plein ecran' : 'Plein ecran'}
          >
            {fullscreen ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="4 14 10 14 10 20" /><polyline points="20 10 14 10 14 4" />
                <line x1="14" y1="10" x2="21" y2="3" /><line x1="3" y1="21" x2="10" y2="14" />
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="15 3 21 3 21 9" /><polyline points="9 21 3 21 3 15" />
                <line x1="21" y1="3" x2="14" y2="10" /><line x1="3" y1="21" x2="10" y2="14" />
              </svg>
            )}
          </button>
        )}
      </div>

      {/* Hover tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 glass-card p-2 text-xs pointer-events-none"
          style={{ left: tooltip.x + 12, top: tooltip.y - 10 }}
        >
          <p className="font-medium text-white/90">{tooltip.node.label}</p>
          <p className="text-white/50">
            {tooltip.node.type} &mdash; {tooltip.node.external_id}
          </p>
        </div>
      )}
    </div>
  );
}
