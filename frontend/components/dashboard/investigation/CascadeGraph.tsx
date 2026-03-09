"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type {
  CascadeGraphData,
  CascadeGraphNode,
  CascadeGraphLink,
} from "@/types/relations";

interface CascadeGraphProps {
  data: CascadeGraphData;
  width?: number;
  height?: number;
}

const DEPTH_COLORS = ["#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#6366f1"];

export default function CascadeGraph({
  data,
  width = 600,
  height = 400,
}: CascadeGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || !data.nodes.length) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const g = svg.append("g");

    // Zoom
    svg.call(
      d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.3, 4])
        .on("zoom", (e) => g.attr("transform", e.transform))
    );

    // Arrow markers per depth color
    svg
      .append("defs")
      .selectAll("marker")
      .data(DEPTH_COLORS)
      .join("marker")
      .attr("id", (_, i) => `arrow-${i}`)
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 20)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-5L10,0L0,5")
      .attr("fill", (d) => d);

    // Simulation types
    type SimNode = CascadeGraphNode & d3.SimulationNodeDatum;
    type SimLink = CascadeGraphLink & d3.SimulationLinkDatum<SimNode>;

    const nodes: SimNode[] = data.nodes.map((d) => ({ ...d }));
    const links: SimLink[] = data.links.map((d) => ({ ...d }) as SimLink);

    const simulation = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3
          .forceLink<SimNode, SimLink>(links)
          .id((d) => d.id)
          .distance(80)
      )
      .force("charge", d3.forceManyBody().strength(-200))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collide", d3.forceCollide(25));

    // Links
    const link = g
      .append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", (d) => {
        const target =
          typeof d.target === "object"
            ? (d.target as SimNode)
            : nodes.find((n) => n.id === d.target);
        return DEPTH_COLORS[Math.min(target?.depth || 0, 4)];
      })
      .attr("stroke-width", (d) => Math.max(1, d.probability * 5))
      .attr("stroke-opacity", (d) => 0.3 + d.probability * 0.7)
      .attr("marker-end", (d) => {
        const target =
          typeof d.target === "object"
            ? (d.target as SimNode)
            : nodes.find((n) => n.id === d.target);
        return `url(#arrow-${Math.min(target?.depth || 0, 4)})`;
      });

    // Link probability labels
    const linkLabel = g
      .append("g")
      .selectAll("text")
      .data(links)
      .join("text")
      .attr("font-size", "8px")
      .attr("fill", "#94a3b8")
      .attr("text-anchor", "middle")
      .text((d) => `${(d.probability * 100).toFixed(0)}%`);

    // Node groups
    const node = g
      .append("g")
      .selectAll<SVGGElement, SimNode>("g")
      .data(nodes)
      .join("g")
      .call(
        d3
          .drag<SVGGElement, SimNode>()
          .on("start", (e, d) => {
            if (!e.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (e, d) => {
            d.fx = e.x;
            d.fy = e.y;
          })
          .on("end", (e, d) => {
            if (!e.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    // Node circles
    node
      .append("circle")
      .attr("r", (d) => (d.isSource ? 18 : 8 + d.impactScore * 20))
      .attr("fill", (d) =>
        d.isSource ? "#ef4444" : DEPTH_COLORS[Math.min(d.depth, 4)]
      )
      .attr("stroke", "#1e293b")
      .attr("stroke-width", (d) => (d.isSource ? 3 : 1.5))
      .attr("opacity", (d) => (d.isSource ? 1 : 0.5 + d.cascadeProbability));

    // Pulsing ring on source node
    node
      .filter((d) => d.isSource)
      .append("circle")
      .attr("r", 22)
      .attr("fill", "none")
      .attr("stroke", "#ef4444")
      .attr("stroke-width", 2)
      .attr("opacity", 0.6);

    // Node labels
    node
      .append("text")
      .attr("dy", (d) => (d.isSource ? -24 : -14))
      .attr("text-anchor", "middle")
      .attr("font-size", (d) => (d.isSource ? "11px" : "9px"))
      .attr("font-weight", (d) => (d.isSource ? "bold" : "normal"))
      .attr("fill", (d) => (d.isSource ? "#fca5a5" : "#cbd5e1"))
      .text((d) =>
        d.label.length > 25 ? d.label.slice(0, 22) + "..." : d.label
      );

    // Headcount badge inside node
    node
      .filter((d) => d.headcount > 0)
      .append("text")
      .attr("dy", (d) => (d.isSource ? 6 : 4))
      .attr("text-anchor", "middle")
      .attr("font-size", "7px")
      .attr("fill", "#fff")
      .text((d) => String(d.headcount));

    // Tick handler
    simulation.on("tick", () => {
      link
        .attr("x1", (d) => (d.source as SimNode).x!)
        .attr("y1", (d) => (d.source as SimNode).y!)
        .attr("x2", (d) => (d.target as SimNode).x!)
        .attr("y2", (d) => (d.target as SimNode).y!);

      linkLabel
        .attr(
          "x",
          (d) => ((d.source as SimNode).x! + (d.target as SimNode).x!) / 2
        )
        .attr(
          "y",
          (d) => ((d.source as SimNode).y! + (d.target as SimNode).y!) / 2
        );

      node.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    return () => {
      simulation.stop();
    };
  }, [data, width, height]);

  return (
    <div className="border border-white/10 rounded-lg bg-black/20 overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/10">
        <span className="text-xs font-medium text-slate-300">
          Cascade Graph
        </span>
        <div className="flex gap-2 ml-auto">
          {["Source", "D1", "D2", "D3"].map((label, i) => (
            <span
              key={label}
              className="flex items-center gap-1 text-[10px] text-slate-400"
            >
              <span
                className="w-2 h-2 rounded-full"
                style={{
                  backgroundColor: i === 0 ? "#ef4444" : DEPTH_COLORS[i],
                }}
              />
              {label}
            </span>
          ))}
        </div>
      </div>
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="w-full"
        viewBox={`0 0 ${width} ${height}`}
      />
    </div>
  );
}
