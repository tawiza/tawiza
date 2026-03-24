'use client';

import { useMemo } from 'react';
import DashboardLayout from '@/components/layout';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { useDecisions, useStakeholders, useRelations, useDecisionStats } from '@/lib/api-decisions';
import { DecisionBoard } from '@/components/dashboard/decisions/DecisionBoard';
import { StakeholderRegistry } from '@/components/dashboard/decisions/StakeholderRegistry';
import { RelationGraph } from '@/components/dashboard/decisions/RelationGraph';
import { ImpactMatrix } from '@/components/dashboard/decisions/ImpactMatrix';
import { useTAJINE } from '@/contexts/TAJINEContext';
import { ClipboardList, Users, Share2, LayoutGrid } from 'lucide-react';

export default function DecisionsPage() {
  const { selectedDepartment } = useTAJINE();
  const dept = selectedDepartment || '59';

  const { data: decisions, isLoading: decisionsLoading, mutate: mutateDecisions } = useDecisions(dept);
  const { data: stakeholders, isLoading: stakeholdersLoading, mutate: mutateStakeholders } = useStakeholders(dept);
  const { data: relations, isLoading: relationsLoading, mutate: mutateRelations } = useRelations(dept);
  const { data: stats } = useDecisionStats(dept);

  const headerActions = useMemo(() => {
    if (!stats) return null;
    return (
      <div className="flex gap-2 text-xs">
        <div className="bg-muted px-2.5 py-1 rounded-md">
          <span className="text-muted-foreground">Total: </span>
          <span className="font-medium">{stats.total}</span>
        </div>
        {stats.by_status?.draft > 0 && (
          <div className="bg-muted px-2.5 py-1 rounded-md">
            <span className="text-muted-foreground">Brouillons: </span>
            <span className="font-medium text-warning">{stats.by_status.draft}</span>
          </div>
        )}
        {stats.by_status?.en_cours > 0 && (
          <div className="bg-muted px-2.5 py-1 rounded-md">
            <span className="text-muted-foreground">En cours: </span>
            <span className="font-medium text-success">{stats.by_status.en_cours}</span>
          </div>
        )}
      </div>
    );
  }, [stats]);

  return (
    <DashboardLayout
      title="Tawiza Decisions"
      description={`Aide a la decision territoriale — Dept. ${dept}`}
      headerActions={headerActions}
      fullHeight
    >
      <div className="flex flex-col h-full p-4 gap-4">
        <Tabs defaultValue="decisions" className="flex flex-col h-full">
          <TabsList className="w-fit shrink-0">
            <TabsTrigger value="decisions" className="gap-2">
              <ClipboardList className="w-4 h-4" />
              <span className="hidden sm:inline">Decisions</span>
            </TabsTrigger>
            <TabsTrigger value="stakeholders" className="gap-2">
              <Users className="w-4 h-4" />
              <span className="hidden sm:inline">Acteurs</span>
            </TabsTrigger>
            <TabsTrigger value="graph" className="gap-2">
              <Share2 className="w-4 h-4" />
              <span className="hidden sm:inline">Graphe</span>
            </TabsTrigger>
            <TabsTrigger value="impact" className="gap-2">
              <LayoutGrid className="w-4 h-4" />
              <span className="hidden sm:inline">Impact</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="decisions" className="flex-1 min-h-0 overflow-y-auto">
            <DecisionBoard
              decisions={decisions || []}
              stakeholders={stakeholders || []}
              isLoading={decisionsLoading}
              onMutate={mutateDecisions}
              dept={dept}
            />
          </TabsContent>
          <TabsContent value="stakeholders" className="flex-1 min-h-0 overflow-y-auto">
            <StakeholderRegistry
              stakeholders={stakeholders || []}
              isLoading={stakeholdersLoading}
              onMutate={mutateStakeholders}
              dept={dept}
            />
          </TabsContent>
          <TabsContent value="graph" className="flex-1 min-h-0 overflow-hidden">
            <RelationGraph
              stakeholders={stakeholders || []}
              relations={relations || []}
              isLoading={stakeholdersLoading || relationsLoading}
            />
          </TabsContent>
          <TabsContent value="impact" className="flex-1 min-h-0 overflow-y-auto">
            <ImpactMatrix
              decisions={decisions || []}
              stakeholders={stakeholders || []}
              isLoading={decisionsLoading || stakeholdersLoading}
            />
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
}
