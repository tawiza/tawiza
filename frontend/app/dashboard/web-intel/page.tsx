"use client"

import DashboardLayout from "@/components/layout"
import { PageTabs } from "@/components/ui/page-tabs"
import { Search, Database, Settings } from "lucide-react"
import { Suspense, lazy } from "react"

const AnalysisTab = lazy(() => import("./tabs/analysis-tab"))
const SourcesTab = lazy(() => import("./tabs/sources-tab"))
const ConfigTab = lazy(() => import("./tabs/config-tab"))

function Loading() {
  return <div className="flex h-96 items-center justify-center text-muted-foreground">Chargement...</div>
}

export default function WebIntelligencePage() {
  return (
    <DashboardLayout title="Web Intelligence" description="Analyse web, sources de donnees et configuration du crawler">
      <PageTabs
        tabs={[
          {
            id: "analyse",
            label: "Analyse",
            icon: <Search className="h-4 w-4" />,
            content: <Suspense fallback={<Loading />}><AnalysisTab /></Suspense>,
          },
          {
            id: "sources",
            label: "Sources",
            icon: <Database className="h-4 w-4" />,
            content: <Suspense fallback={<Loading />}><SourcesTab /></Suspense>,
          },
          {
            id: "config",
            label: "Config",
            icon: <Settings className="h-4 w-4" />,
            content: <Suspense fallback={<Loading />}><ConfigTab /></Suspense>,
          },
        ]}
        defaultTab="analyse"
      />
    </DashboardLayout>
  )
}
