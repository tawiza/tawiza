import * as React from "react"
import { cn } from "../../lib/utils"

interface SparklineProps extends React.SVGAttributes<SVGSVGElement> {
  /** Array of numeric values to plot */
  data: number[]
  /** Width of the sparkline in pixels */
  width?: number
  /** Height of the sparkline in pixels */
  height?: number
  /** Stroke color (CSS color value) */
  color?: string
  /** Whether to show area fill under the line */
  showArea?: boolean
  /** Whether to animate the line drawing */
  animated?: boolean
}

const Sparkline = React.forwardRef<SVGSVGElement, SparklineProps>(
  (
    {
      data,
      width = 80,
      height = 20,
      color = "hsl(var(--primary))",
      showArea = false,
      animated = false,
      className,
      ...props
    },
    ref
  ) => {
    if (!data || data.length === 0) {
      return (
        <svg
          ref={ref}
          width={width}
          height={height}
          className={cn("inline-block", className)}
          {...props}
        />
      )
    }

    const min = Math.min(...data)
    const max = Math.max(...data)
    const range = max - min || 1

    // Padding to prevent line from touching edges
    const padding = 2
    const innerWidth = width - padding * 2
    const innerHeight = height - padding * 2

    // Generate path points
    const points = data.map((value, index) => {
      const x = padding + (index / (data.length - 1)) * innerWidth
      const y = padding + innerHeight - ((value - min) / range) * innerHeight
      return { x, y }
    })

    // Create line path
    const linePath = points
      .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
      .join(" ")

    // Create area path (closed polygon for fill)
    const areaPath = showArea
      ? `${linePath} L ${points[points.length - 1].x} ${height - padding} L ${padding} ${height - padding} Z`
      : ""

    const lineLength = points.reduce((acc, point, index) => {
      if (index === 0) return 0
      const prev = points[index - 1]
      return acc + Math.sqrt(Math.pow(point.x - prev.x, 2) + Math.pow(point.y - prev.y, 2))
    }, 0)

    return (
      <svg
        ref={ref}
        width={width}
        height={height}
        className={cn("inline-block", className)}
        {...props}
      >
        {/* Area fill */}
        {showArea && (
          <path
            d={areaPath}
            fill={color}
            fillOpacity={0.1}
          />
        )}

        {/* Line */}
        <path
          d={linePath}
          fill="none"
          stroke={color}
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          style={
            animated
              ? {
                  strokeDasharray: lineLength,
                  strokeDashoffset: lineLength,
                  animation: "sparkline-draw 1s ease-in-out forwards",
                }
              : undefined
          }
        />

        {/* End dot */}
        {points.length > 0 && (
          <circle
            cx={points[points.length - 1].x}
            cy={points[points.length - 1].y}
            r={2}
            fill={color}
          />
        )}

        {animated && (
          <style>{`
            @keyframes sparkline-draw {
              to {
                stroke-dashoffset: 0;
              }
            }
          `}</style>
        )}
      </svg>
    )
  }
)
Sparkline.displayName = "Sparkline"

export { Sparkline }
