"use client"

import DashboardLayout from "@/components/layout"
import { PageTabs } from "@/components/ui/page-tabs"
import { PageLoader } from "@/components/ui/page-loader"
import { History, TrendingUp } from "lucide-react"
import { Suspense, lazy } from "react"

const HistoryTab = lazy(() => import("./tabs/history-tab"))
const ForecastTab = lazy(() => import("./tabs/forecast-tab"))

export default function AnalyticsPage() {
  return (
    <DashboardLayout title="Analytics" description="Historique des analyses et previsions">
      <PageTabs
        tabs={[
          {
            id: "historique",
            label: "Historique",
            icon: <History className="h-4 w-4" />,
            content: <Suspense fallback={<PageLoader text="Chargement..." />}><HistoryTab /></Suspense>,
          },
          {
            id: "forecast",
            label: "Forecast",
            icon: <TrendingUp className="h-4 w-4" />,
            content: <Suspense fallback={<PageLoader text="Chargement..." />}><ForecastTab /></Suspense>,
          },
        ]}
        defaultTab="historique"
      />
    </DashboardLayout>
  )
}
