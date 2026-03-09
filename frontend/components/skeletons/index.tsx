'use client';

import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardHeader } from '@/components/ui/card';

/**
 * Skeleton for stat cards (KPI metrics)
 */
export function StatCardSkeleton() {
  return (
    <Card className="glass">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-8 rounded-full" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-8 w-20 mb-1" />
        <Skeleton className="h-3 w-32" />
      </CardContent>
    </Card>
  );
}

/**
 * Skeleton for a row of stat cards
 */
export function StatCardRowSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <StatCardSkeleton key={i} />
      ))}
    </div>
  );
}

// Deterministic heights for chart skeleton bars (avoid Math.random() hydration mismatch)
const CHART_SKELETON_HEIGHTS = [65, 45, 80, 55, 70, 40, 75];

/**
 * Skeleton for chart containers
 */
export function ChartSkeleton({ height = 300 }: { height?: number }) {
  return (
    <Card className="glass">
      <CardHeader>
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-3 w-48 mt-1" />
      </CardHeader>
      <CardContent>
        <div className="flex items-end justify-between gap-2" style={{ height }}>
          {/* Bar chart skeleton with deterministic heights */}
          {CHART_SKELETON_HEIGHTS.map((h, i) => (
            <Skeleton
              key={i}
              className="flex-1"
              style={{ height: `${h}%` }}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Skeleton for pie/donut charts
 */
export function PieChartSkeleton({ size = 200 }: { size?: number }) {
  return (
    <Card className="glass">
      <CardHeader>
        <Skeleton className="h-5 w-32" />
      </CardHeader>
      <CardContent className="flex items-center justify-center">
        <Skeleton
          className="rounded-full"
          style={{ width: size, height: size }}
        />
      </CardContent>
    </Card>
  );
}

/**
 * Skeleton for data tables
 */
export function TableSkeleton({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <Card className="glass">
      <CardHeader>
        <Skeleton className="h-5 w-40" />
      </CardHeader>
      <CardContent>
        {/* Header */}
        <div className="flex gap-4 pb-3 border-b border-border mb-3">
          {Array.from({ length: columns }).map((_, i) => (
            <Skeleton key={i} className="h-4 flex-1" />
          ))}
        </div>
        {/* Rows */}
        <div className="space-y-3">
          {Array.from({ length: rows }).map((_, rowIndex) => (
            <div key={rowIndex} className="flex gap-4">
              {Array.from({ length: columns }).map((_, colIndex) => (
                <Skeleton
                  key={colIndex}
                  className="h-4 flex-1"
                  style={{ opacity: 1 - rowIndex * 0.1 }}
                />
              ))}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Skeleton for chat messages
 */
export function ChatMessageSkeleton({ isUser = false }: { isUser?: boolean }) {
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <Skeleton className="h-8 w-8 rounded-full flex-shrink-0" />
      <div className={`space-y-2 max-w-[70%] ${isUser ? 'items-end' : ''}`}>
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-4 w-64" />
        <Skeleton className="h-4 w-32" />
      </div>
    </div>
  );
}

/**
 * Skeleton for chat conversation list
 */
export function ChatListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-2 p-2">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 p-3 rounded-lg">
          <Skeleton className="h-10 w-10 rounded-full flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-3 w-full" />
          </div>
          <Skeleton className="h-3 w-12" />
        </div>
      ))}
    </div>
  );
}

/**
 * Skeleton for France map
 */
export function MapSkeleton() {
  return (
    <Card className="glass">
      <CardHeader>
        <Skeleton className="h-5 w-32" />
      </CardHeader>
      <CardContent className="flex items-center justify-center p-8">
        <div className="relative w-full max-w-md aspect-[4/5]">
          {/* France map outline approximation */}
          <Skeleton className="absolute inset-0 rounded-[30%_70%_60%_40%/60%_40%_60%_40%]" />
          {/* Legend */}
          <div className="absolute bottom-0 left-0 right-0 flex justify-center gap-4 pt-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex items-center gap-2">
                <Skeleton className="h-3 w-3 rounded" />
                <Skeleton className="h-3 w-12" />
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Skeleton for notification items
 */
export function NotificationSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-start gap-3 p-3 rounded-lg">
          <Skeleton className="h-8 w-8 rounded-full flex-shrink-0" />
          <div className="flex-1 space-y-1">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Skeleton for department list
 */
export function DepartmentListSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
          <div className="flex items-center gap-3">
            <Skeleton className="h-8 w-12 rounded" />
            <div className="space-y-1">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-3 w-16" />
            </div>
          </div>
          <Skeleton className="h-6 w-16 rounded-full" />
        </div>
      ))}
    </div>
  );
}

/**
 * Full dashboard skeleton
 */
export function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <StatCardRowSkeleton count={4} />
      <div className="grid gap-4 md:grid-cols-2">
        <ChartSkeleton height={250} />
        <MapSkeleton />
      </div>
      <TableSkeleton rows={5} columns={5} />
    </div>
  );
}

/**
 * TAJINE page skeleton
 */
export function TajinePageSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="md:col-span-2">
          <MapSkeleton />
        </div>
        <DepartmentListSkeleton count={8} />
      </div>
      <StatCardRowSkeleton count={3} />
      <div className="grid gap-4 md:grid-cols-2">
        <ChartSkeleton height={200} />
        <TableSkeleton rows={4} columns={4} />
      </div>
    </div>
  );
}
