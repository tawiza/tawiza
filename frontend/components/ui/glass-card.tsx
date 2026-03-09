import * as React from "react"
import { cn } from "../../lib/utils"

type GlowColor = "none" | "cyan" | "green" | "red" | "yellow"

/* Status accent: left border color for status indication */
const statusBorderStyles: Record<GlowColor, string> = {
  none: "",
  cyan: "border-l-[3px] border-l-primary",
  green: "border-l-[3px] border-l-success",
  red: "border-l-[3px] border-l-error",
  yellow: "border-l-[3px] border-l-warning",
}

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Color of the status accent */
  glow?: GlowColor
  /** Enable hover border highlight */
  hoverGlow?: boolean
  /** Remove padding */
  noPadding?: boolean
}

const GlassCard = React.forwardRef<HTMLDivElement, GlassCardProps>(
  ({ className, glow = "none", hoverGlow = true, noPadding = false, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "bg-card border border-border rounded-xl transition-colors duration-150",
          hoverGlow && "hover:border-zinc-700 dark:hover:border-zinc-600",
          !noPadding && "p-6",
          statusBorderStyles[glow],
          className
        )}
        {...props}
      />
    )
  }
)
GlassCard.displayName = "GlassCard"

const GlassCardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col space-y-1.5 pb-4", className)}
    {...props}
  />
))
GlassCardHeader.displayName = "GlassCardHeader"

const GlassCardTitle = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "text-xl font-semibold leading-none tracking-tight",
      className
    )}
    {...props}
  />
))
GlassCardTitle.displayName = "GlassCardTitle"

const GlassCardDescription = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
))
GlassCardDescription.displayName = "GlassCardDescription"

const GlassCardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("", className)} {...props} />
))
GlassCardContent.displayName = "GlassCardContent"

const GlassCardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex items-center pt-4", className)}
    {...props}
  />
))
GlassCardFooter.displayName = "GlassCardFooter"

export {
  GlassCard,
  GlassCardHeader,
  GlassCardFooter,
  GlassCardTitle,
  GlassCardDescription,
  GlassCardContent,
}
