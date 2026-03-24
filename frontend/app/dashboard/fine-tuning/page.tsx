'use client';

import React, { useState, useRef, useEffect } from 'react';
import DashboardLayout from '@/components/layout';
import {
  GlassCard,
  GlassCardContent,
  GlassCardDescription,
  GlassCardHeader,
  GlassCardTitle
} from '@/components/ui/glass-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from '@/components/ui/dialog';
import { Progress } from '@/components/ui/progress';
import {
  HiOutlineAcademicCap,
  HiOutlineCircleStack,
  HiOutlinePlay,
  HiOutlineStop,
  HiOutlineTrash,
  HiOutlineArrowPath,
  HiOutlineCheckCircle,
  HiOutlineExclamationCircle,
  HiOutlineClock,
  HiOutlineCpuChip,
  HiOutlineDocumentText,
  HiOutlineBeaker,
  HiOutlineChartBar,
  HiOutlineArrowDownTray,
  HiOutlineTag,
  HiOutlineCloudArrowUp,
} from 'react-icons/hi2';
import { cn } from '@/lib/utils';
import { KpiCard } from '@/components/ui/kpi-card';
import { ChartWrapper, useChartTheme } from '@/components/ui/chart-wrapper';
import { Database, Play, Brain, CheckCircle } from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
} from 'recharts';
import {
  useFineTuningHealth,
  useFineTuningJobs,
  useFineTunedModels,
  useTrainingDataStats,
  useStartFineTuning,
  useCancelJob,
  useDeleteModel,
  useJobLogs,
  getJobStatusColor,
  getJobStatusLabel,
  formatModelSize,
  formatDuration,
  type FineTuningJob,
  type FineTunedModel,
} from '@/hooks/use-fine-tuning';

// ============================================================================
// Sub-components
// ============================================================================

function StatCard({
  label,
  value,
  icon: Icon,
  color = 'cyan',
}: {
  label: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
  color?: 'cyan' | 'green' | 'yellow' | 'red';
}) {
  const colorClasses = {
    cyan: 'text-primary',
    green: 'text-[var(--success)]',
    yellow: 'text-[var(--warning)]',
    red: 'text-[var(--error)]',
  };

  return (
    <div className="flex items-center gap-3 p-4 rounded-lg bg-muted/30 border border-border">
      <div className={cn('p-2 rounded-lg bg-muted/50', colorClasses[color])}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-2xl font-bold">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}

function JobCard({
  job,
  onCancel,
  onViewLogs,
  isCancelling,
}: {
  job: FineTuningJob;
  onCancel: (jobId: string) => void;
  onViewLogs: (jobId: string) => void;
  isCancelling?: boolean;
}) {
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const isActive = job.status === 'running' || job.status === 'pending';

  const handleCancelClick = () => {
    setShowCancelConfirm(true);
  };

  const handleConfirmCancel = () => {
    onCancel(job.job_id);
    setShowCancelConfirm(false);
  };

  return (
    <div className="p-4 rounded-lg border border-border bg-card/50 space-y-3">
      <div className="flex items-start justify-between">
        <div>
          <h4 className="font-medium">{job.model_name}</h4>
          <p className="text-xs text-muted-foreground">
            Base: {job.base_model} | {job.training_examples} examples
          </p>
        </div>
        <Badge
          style={{ backgroundColor: getJobStatusColor(job.status) + '20', color: getJobStatusColor(job.status) }}
        >
          {getJobStatusLabel(job.status)}
        </Badge>
      </div>

      {job.status === 'running' && (
        <Progress value={50} className="h-1" />
      )}

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>ID: {job.job_id.slice(0, 8)}...</span>
        <span>{formatDuration(job.started_at, job.completed_at)}</span>
      </div>

      {job.error && (
        <p className="text-xs text-[var(--error)] bg-[var(--error)]/10 p-2 rounded">
          {job.error}
        </p>
      )}

      <div className="flex gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onViewLogs(job.job_id)}
          className="gap-1"
        >
          <HiOutlineDocumentText className="h-4 w-4" />
          Logs
        </Button>
        {isActive && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCancelClick}
            disabled={isCancelling}
            className="gap-1 text-[var(--error)]"
          >
            <HiOutlineStop className="h-4 w-4" />
            {isCancelling ? 'Annulation...' : 'Annuler'}
          </Button>
        )}
      </div>

      {/* Cancel Confirmation Dialog */}
      <Dialog open={showCancelConfirm} onOpenChange={setShowCancelConfirm}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-[var(--error)]">
              <HiOutlineExclamationCircle className="h-5 w-5" />
              Annuler le job ?
            </DialogTitle>
            <DialogDescription>
              Cette action va interrompre l&apos;entrainement en cours pour{' '}
              <strong>{job.model_name}</strong>. Les ressources seront liberees
              mais la progression sera perdue.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="ghost"
              onClick={() => setShowCancelConfirm(false)}
            >
              Non, continuer
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmCancel}
              className="bg-[var(--error)] hover:bg-[var(--error)]/80"
            >
              Oui, annuler
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ModelCard({
  model,
  onDelete,
  onExport,
}: {
  model: FineTunedModel;
  onDelete: (name: string) => void;
  onExport: (name: string) => void;
}) {
  return (
    <div className="p-4 rounded-lg border border-border bg-card/50 space-y-3">
      <div className="flex items-start justify-between">
        <div>
          <h4 className="font-medium">{model.name}</h4>
          <p className="text-xs text-muted-foreground">
            Base: {model.base_model}
          </p>
        </div>
        <Badge variant="secondary">
          {formatModelSize(model.size)}
        </Badge>
      </div>

      <p className="text-xs text-muted-foreground">
        Cree le: {new Date(model.created_at).toLocaleDateString('fr-FR')}
      </p>

      <div className="flex gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onExport(model.name)}
          className="gap-1"
        >
          <HiOutlineArrowDownTray className="h-4 w-4" />
          Exporter
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onDelete(model.name)}
          className="gap-1 text-[var(--error)]"
        >
          <HiOutlineTrash className="h-4 w-4" />
          Supprimer
        </Button>
      </div>
    </div>
  );
}

function LogsDialog({
  jobId,
  open,
  onOpenChange,
}: {
  jobId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: logs, isLoading, mutate: refreshLogs } = useJobLogs(open ? jobId : null);
  const logsEndRef = React.useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Auto-scroll to bottom when logs update
  React.useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs?.content, autoScroll]);

  // Parse log lines for coloring
  const formatLogLine = (line: string, index: number) => {
    let className = 'text-muted-foreground';
    if (line.includes('ERROR') || line.includes('error')) {
      className = 'text-[var(--error)]';
    } else if (line.includes('WARNING') || line.includes('warn')) {
      className = 'text-[var(--warning)]';
    } else if (line.includes('SUCCESS') || line.includes('completed') || line.includes('✓')) {
      className = 'text-[var(--success)]';
    } else if (line.includes('epoch') || line.includes('step') || line.includes('loss')) {
      className = 'text-primary';
    }
    return (
      <div key={index} className={cn('py-0.5', className)}>
        {line}
      </div>
    );
  };

  const logLines = logs?.content?.split('\n') || [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <div>
              <DialogTitle className="flex items-center gap-2">
                <HiOutlineDocumentText className="h-5 w-5 text-primary" />
                Logs du job {jobId?.slice(0, 8)}...
              </DialogTitle>
              <DialogDescription>
                Logs d&apos;entrainement en temps reel ({logLines.length} lignes)
              </DialogDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => refreshLogs()}
                className="gap-1"
              >
                <HiOutlineArrowPath className="h-4 w-4" />
              </Button>
              <div className="flex items-center gap-2">
                <Switch
                  id="auto-scroll"
                  checked={autoScroll}
                  onCheckedChange={setAutoScroll}
                />
                <Label htmlFor="auto-scroll" className="text-xs">Auto-scroll</Label>
              </div>
            </div>
          </div>
        </DialogHeader>
        <div 
          className="bg-muted rounded-lg p-4 max-h-[500px] overflow-y-auto font-mono text-xs border border-border"
          onScroll={(e) => {
            const target = e.target as HTMLDivElement;
            const isAtBottom = target.scrollHeight - target.scrollTop <= target.clientHeight + 50;
            if (!isAtBottom && autoScroll) {
              setAutoScroll(false);
            }
          }}
        >
          {isLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <HiOutlineArrowPath className="h-4 w-4 animate-spin" />
              Chargement des logs...
            </div>
          ) : logLines.length === 0 ? (
            <p className="text-muted-foreground">Aucun log disponible</p>
          ) : (
            <>
              {logLines.map((line, i) => formatLogLine(line, i))}
              <div ref={logsEndRef} />
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================================
// Dataset Generation Section
// ============================================================================

function DatasetSection() {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [genStatus, setGenStatus] = useState<any>(null);
  const [generating, setGenerating] = useState(false);
  const [count, setCount] = useState(200);

  const API = process.env.NEXT_PUBLIC_API_URL || '';

  const fetchDatasets = async () => {
    try {
      const [dsRes, statusRes] = await Promise.all([
        fetch(`${API}/api/v1/training/datasets`),
        fetch(`${API}/api/v1/training/generate/status`),
      ]);
      if (dsRes.ok) {
        const d = await dsRes.json();
        setDatasets(d.datasets || []);
      }
      if (statusRes.ok) {
        const s = await statusRes.json();
        setGenStatus(s);
        setGenerating(s.is_running);
      }
    } catch {}
  };

  useEffect(() => {
    fetchDatasets();
    const interval = setInterval(fetchDatasets, 5000);
    return () => clearInterval(interval);
  }, []);

  const startGeneration = async () => {
    setGenerating(true);
    try {
      await fetch(`${API}/api/v1/training/generate?count=${count}`, { method: 'POST' });
    } catch {}
  };

  return (
    <GlassCard glow="cyan">
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineCircleStack className="h-5 w-5 text-primary" />
          Generation de Datasets Synthetiques
        </GlassCardTitle>
        <GlassCardDescription>
          Genere des paires question/reponse a partir des 223K+ signaux reels via qwen3:32b
        </GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent className="space-y-4">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Label className="text-sm">Nombre de samples:</Label>
            <Input
              type="number"
              value={count}
              onChange={(e) => setCount(parseInt(e.target.value) || 200)}
              className="w-24"
              min={10}
              max={2000}
            />
          </div>
          <Button
            onClick={startGeneration}
            disabled={generating}
            className="gap-2"
          >
            {generating ? (
              <>
                <HiOutlineArrowPath className="h-4 w-4 animate-spin" />
                Generation en cours...
              </>
            ) : (
              <>
                <HiOutlineBeaker className="h-4 w-4" />
                Generer
              </>
            )}
          </Button>
          <Button variant="ghost" size="icon" onClick={fetchDatasets}>
            <HiOutlineArrowPath className="h-4 w-4" />
          </Button>
        </div>

        {genStatus?.error && (
          <p className="text-xs text-[var(--error)] bg-[var(--error)]/10 p-2 rounded">
            {genStatus.error}
          </p>
        )}

        {datasets.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4">
            Aucun dataset genere. Lancez une generation pour creer des donnees d&apos;entrainement.
          </p>
        ) : (
          <div className="space-y-2">
            {datasets.map((ds) => (
              <div key={ds.name} className="flex items-center justify-between p-3 rounded-lg bg-muted/30 border border-border">
                <div>
                  <p className="text-sm font-medium">{ds.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {ds.samples} samples | {(ds.size_bytes / 1024).toFixed(1)} KB | {new Date(ds.created_at).toLocaleDateString('fr-FR')}
                  </p>
                </div>
                <Badge variant="secondary" className="gap-1">
                  <HiOutlineCheckCircle className="h-3 w-3" />
                  {ds.samples >= 50 ? 'Pret pour SFT' : `${ds.samples}/50 min`}
                </Badge>
              </div>
            ))}
          </div>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}

// ============================================================================
// Main Page
// ============================================================================

export default function FineTuningPage() {
  // State
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [showLogsDialog, setShowLogsDialog] = useState(false);
  const [showNewJobDialog, setShowNewJobDialog] = useState(false);
  // New job form state
  const [baseModel, setBaseModel] = useState('qwen3:14b');
  const [modelName, setModelName] = useState('');
  const [useLora, setUseLora] = useState(true);
  const [loraRank, setLoraRank] = useState(16);
  const [useCoalm, setUseCoalm] = useState(true);
  const [territoryCode, setTerritoryCode] = useState('');
  const [quantization, setQuantization] = useState<'4bit' | '8bit' | 'none'>('4bit');

  // Data hooks
  const { data: health } = useFineTuningHealth();
  const { data: jobs, mutate: refreshJobs } = useFineTuningJobs();
  const { data: modelsData, mutate: refreshModels } = useFineTunedModels();
  const { data: stats } = useTrainingDataStats();
  // KPI data derived from real API responses
  const totalJobs = jobs?.length ?? 0;
  const lastCompletedJob = jobs
    ?.filter((j) => j.status === 'completed')
    .sort((a, b) => (b.completed_at ?? '').localeCompare(a.completed_at ?? ''))[0];
  const activeModelName =
    modelsData?.models?.[0]?.name ?? lastCompletedJob?.model_name ?? 'Aucun';
  const lastEvalDate = lastCompletedJob?.completed_at
    ? new Date(lastCompletedJob.completed_at).toLocaleDateString('fr-FR', {
        day: '2-digit',
        month: 'short',
      })
    : 'N/A';
  const datasetCount = stats?.total_interactions ?? 0;

  // Loss & eval charts -- placeholder data (no per-epoch metrics endpoint yet)
  const lossData = [
    { epoch: 1, train: 2.5, val: 2.8 },
    { epoch: 2, train: 1.8, val: 2.1 },
    { epoch: 3, train: 1.2, val: 1.6 },
    { epoch: 4, train: 0.8, val: 1.3 },
    { epoch: 5, train: 0.5, val: 1.1 },
  ];
  const evalData = [
    { metric: 'BLEU', before: 0.25, after: 0.42 },
    { metric: 'ROUGE', before: 0.30, after: 0.55 },
    { metric: 'Accuracy', before: 0.60, after: 0.78 },
  ];
  const theme = useChartTheme();

  // Mutation hooks
  const { startFineTuning, isLoading: isStarting, error: startError } = useStartFineTuning();
  const { cancelJob, isLoading: isCancelling } = useCancelJob();
  const { deleteModel, isLoading: isDeleting } = useDeleteModel();
  // Handlers
  const handleStartJob = async () => {
    try {
      await startFineTuning({
        project_id: 'tajine-default',
        base_model: baseModel,
        model_name: modelName || `tajine-${Date.now()}`,
        task_type: 'territorial-analysis',
        annotations: [], // Default to empty array to satisfy API validation
      });
      setShowNewJobDialog(false);
      refreshJobs();
    } catch (err) {
      // Error is handled by the hook
    }
  };

  const handleCancelJob = async (jobId: string) => {
    await cancelJob(jobId);
    refreshJobs();
  };

  const handleDeleteModel = async (name: string) => {
    if (confirm(`Supprimer le modele ${name} ?`)) {
      await deleteModel(name);
      refreshModels();
    }
  };

  const handleExportModel = (name: string) => {
    window.open(`/api/v1/fine-tuning/models/${encodeURIComponent(name)}/export`, '_blank');
  };

  const handleViewLogs = (jobId: string) => {
    setSelectedJobId(jobId);
    setShowLogsDialog(true);
  };

  // Derived data
  const activeJobs = jobs?.filter(j => j.status === 'running' || j.status === 'pending') || [];
  const completedJobs = jobs?.filter(j => j.status === 'completed') || [];
  const failedJobs = jobs?.filter(j => j.status === 'failed') || [];
  const models = modelsData?.models || [];

  const isHealthy = health?.status === 'healthy';

  return (
    <DashboardLayout title="Fine-Tuning" description="Entrainement de modeles specialises">
      <div className="h-full w-full space-y-6">
        {/* Header */}
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <HiOutlineAcademicCap className="h-6 w-6 text-primary" />
              Fine-Tuning TAJINE
            </h1>
            <p className="text-sm text-muted-foreground">
              Entrainement de modeles specialises pour l&apos;analyse territoriale
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Health Status */}
            <Badge
              variant={isHealthy ? 'default' : 'destructive'}
              className={cn(
                'gap-1',
                isHealthy
                  ? 'bg-[var(--success)]/20 text-[var(--success)] border-[var(--success)]/30'
                  : 'bg-[var(--error)]/20 text-[var(--error)] border-[var(--error)]/30'
              )}
            >
              {isHealthy ? (
                <HiOutlineCheckCircle className="h-3 w-3" />
              ) : (
                <HiOutlineExclamationCircle className="h-3 w-3" />
              )}
              {isHealthy ? 'Ollama connecte' : 'Ollama deconnecte'}
            </Badge>

            <Button
              variant="ghost"
              size="icon"
              onClick={() => { refreshJobs(); refreshModels(); }}
            >
              <HiOutlineArrowPath className="h-4 w-4" />
            </Button>

            <Dialog open={showNewJobDialog} onOpenChange={setShowNewJobDialog}>
              <DialogTrigger asChild>
                <Button className="gap-2" disabled={!isHealthy}>
                  <HiOutlinePlay className="h-4 w-4" />
                  Nouveau Job
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Demarrer un Fine-Tuning</DialogTitle>
                  <DialogDescription>
                    Configurez les parametres d&apos;entrainement
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label>Modele de base</Label>
                    <Select value={baseModel} onValueChange={setBaseModel}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="qwen3:14b">Qwen3 14B</SelectItem>
                        <SelectItem value="qwen3:30b">Qwen3 30B</SelectItem>
                        <SelectItem value="llama3.1:8b">Llama 3.1 8B</SelectItem>
                        <SelectItem value="mistral:7b">Mistral 7B</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>Nom du modele</Label>
                    <Input
                      value={modelName}
                      onChange={(e) => setModelName(e.target.value)}
                      placeholder="tajine-territorial-v1"
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <Label>LoRA</Label>
                      <p className="text-xs text-muted-foreground">
                        Entrainement efficace avec adaptateurs
                      </p>
                    </div>
                    <Switch checked={useLora} onCheckedChange={setUseLora} />
                  </div>

                  {useLora && (
                    <div className="space-y-2">
                      <Label>Rang LoRA</Label>
                      <Select value={String(loraRank)} onValueChange={(v) => setLoraRank(parseInt(v))}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="8">8 (leger)</SelectItem>
                          <SelectItem value="16">16 (standard)</SelectItem>
                          <SelectItem value="32">32 (expressif)</SelectItem>
                          <SelectItem value="64">64 (maximum)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  )}

                  <div className="flex items-center justify-between">
                    <div>
                      <Label>CoALM Multi-Agent</Label>
                      <p className="text-xs text-muted-foreground">
                        Entrainement collaboratif (Oumi)
                      </p>
                    </div>
                    <Switch checked={useCoalm} onCheckedChange={setUseCoalm} />
                  </div>

                  <div className="space-y-2">
                    <Label>Quantification</Label>
                    <Select value={quantization} onValueChange={(v) => setQuantization(v as typeof quantization)}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="4bit">4-bit (QLoRA)</SelectItem>
                        <SelectItem value="8bit">8-bit</SelectItem>
                        <SelectItem value="none">Aucune (FP16)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>Departement (optionnel)</Label>
                    <Input
                      value={territoryCode}
                      onChange={(e) => setTerritoryCode(e.target.value)}
                      placeholder="ex: 34 pour Herault"
                      maxLength={3}
                    />
                    <p className="text-xs text-muted-foreground">
                      Specialisation territoriale pour un departement
                    </p>
                  </div>
                </div>

                {startError && (
                  <p className="text-sm text-[var(--error)] bg-[var(--error)]/10 p-2 rounded">
                    {startError}
                  </p>
                )}

                <DialogFooter>
                  <Button variant="ghost" onClick={() => setShowNewJobDialog(false)}>
                    Annuler
                  </Button>
                  <Button onClick={handleStartJob} disabled={isStarting}>
                    {isStarting ? 'Demarrage...' : 'Demarrer'}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard title="Datasets" value={datasetCount} icon={Database} />
          <KpiCard title="Jobs lances" value={totalJobs} icon={Play} />
          <KpiCard title="Modele actif" value={activeModelName} icon={Brain} />
          <KpiCard title="Derniere eval" value={lastEvalDate} icon={CheckCircle} />
        </div>

        {/* Training Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <ChartWrapper title="Courbe de loss" subtitle="Training vs Validation (donnees de demonstration)">
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={lossData}>
                <CartesianGrid stroke={theme.grid} strokeDasharray="3 3" />
                <XAxis dataKey="epoch" stroke={theme.text} fontSize={12} />
                <YAxis stroke={theme.text} fontSize={12} />
                <Tooltip
                  contentStyle={{
                    background: theme.tooltip.bg,
                    border: `1px solid ${theme.tooltip.border}`,
                    color: theme.tooltip.text,
                  }}
                />
                <Line type="monotone" dataKey="train" stroke={theme.series[0]} strokeWidth={2} dot={false} name="Training" />
                <Line type="monotone" dataKey="val" stroke={theme.series[1]} strokeWidth={2} dot={false} name="Validation" />
              </LineChart>
            </ResponsiveContainer>
          </ChartWrapper>

          <ChartWrapper title="Scores d'evaluation" subtitle="Avant / Apres fine-tuning (donnees de demonstration)">
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={evalData}>
                <CartesianGrid stroke={theme.grid} strokeDasharray="3 3" />
                <XAxis dataKey="metric" stroke={theme.text} fontSize={12} />
                <YAxis stroke={theme.text} fontSize={12} />
                <Tooltip
                  contentStyle={{
                    background: theme.tooltip.bg,
                    border: `1px solid ${theme.tooltip.border}`,
                    color: theme.tooltip.text,
                  }}
                />
                <Bar dataKey="before" fill={theme.series[4]} name="Avant" />
                <Bar dataKey="after" fill={theme.series[0]} name="Apres" />
                <Legend />
              </BarChart>
            </ResponsiveContainer>
          </ChartWrapper>
        </div>

        {/* Training Data Stats */}
        <GlassCard glow="cyan">
          <GlassCardHeader>
            <GlassCardTitle className="flex items-center gap-2">
              <HiOutlineCircleStack className="h-5 w-5 text-primary" />
              Donnees d&apos;Entrainement
            </GlassCardTitle>
            <GlassCardDescription>
              Donnees collectees depuis les interactions TAJINE
            </GlassCardDescription>
          </GlassCardHeader>
          <GlassCardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                label="Interactions totales"
                value={stats?.total_interactions || 0}
                icon={HiOutlineChartBar}
                color="cyan"
              />
              <StatCard
                label="Success Traces (SFT)"
                value={stats?.success_traces || 0}
                icon={HiOutlineCheckCircle}
                color="green"
              />
              <StatCard
                label="Preference Pairs (DPO)"
                value={stats?.preference_pairs || 0}
                icon={HiOutlineBeaker}
                color="yellow"
              />
              <StatCard
                label="Score qualite moyen"
                value={stats?.avg_quality_score ? `${(stats.avg_quality_score * 100).toFixed(0)}%` : 'N/A'}
                icon={HiOutlineCpuChip}
                color={stats?.avg_quality_score && stats.avg_quality_score > 0.7 ? 'green' : 'yellow'}
              />
            </div>

            {stats?.last_collected && (
              <p className="text-xs text-muted-foreground mt-4">
                Derniere collecte: {new Date(stats.last_collected).toLocaleString('fr-FR')}
              </p>
            )}

            {stats?.total_interactions === 0 && (
              <div className="mt-4 p-4 rounded-lg bg-[var(--warning)]/10 border border-[var(--warning)]/30">
                <p className="text-sm text-[var(--warning)]">
                  Aucune donnee collectee. Utilisez TAJINE pour generer des traces d&apos;entrainement.
                </p>
              </div>
            )}
          </GlassCardContent>
        </GlassCard>

        {/* Dataset Generation */}
        <DatasetSection />

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Active Jobs */}
          <GlassCard glow="cyan" hoverGlow>
            <GlassCardHeader>
              <GlassCardTitle className="flex items-center gap-2">
                <HiOutlineClock className="h-5 w-5 text-primary" />
                Jobs en cours
                {activeJobs.length > 0 && (
                  <Badge variant="secondary">{activeJobs.length}</Badge>
                )}
              </GlassCardTitle>
              <GlassCardDescription>
                Entrainements actifs
              </GlassCardDescription>
            </GlassCardHeader>
            <GlassCardContent>
              {activeJobs.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  Aucun job en cours
                </p>
              ) : (
                <div className="space-y-4">
                  {activeJobs.map((job) => (
                    <JobCard
                      key={job.job_id}
                      job={job}
                      onCancel={handleCancelJob}
                      onViewLogs={handleViewLogs}
                      isCancelling={isCancelling}
                    />
                  ))}
                </div>
              )}
            </GlassCardContent>
          </GlassCard>

          {/* Recent Jobs */}
          <GlassCard glow="cyan" hoverGlow>
            <GlassCardHeader>
              <GlassCardTitle className="flex items-center gap-2">
                <HiOutlineChartBar className="h-5 w-5 text-primary" />
                Historique
              </GlassCardTitle>
              <GlassCardDescription>
                Jobs termines et echoues
              </GlassCardDescription>
            </GlassCardHeader>
            <GlassCardContent>
              {completedJobs.length === 0 && failedJobs.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  Aucun historique
                </p>
              ) : (
                <div className="space-y-4 max-h-96 overflow-y-auto">
                  {[...completedJobs, ...failedJobs].slice(0, 10).map((job) => (
                    <JobCard
                      key={job.job_id}
                      job={job}
                      onCancel={handleCancelJob}
                      onViewLogs={handleViewLogs}
                      isCancelling={isCancelling}
                    />
                  ))}
                </div>
              )}
            </GlassCardContent>
          </GlassCard>
        </div>

        {/* Fine-tuned Models */}
        <GlassCard glow="cyan">
          <GlassCardHeader>
            <GlassCardTitle className="flex items-center gap-2">
              <HiOutlineCpuChip className="h-5 w-5 text-primary" />
              Modeles Fine-Tunes
              {models.length > 0 && (
                <Badge variant="secondary">{models.length}</Badge>
              )}
            </GlassCardTitle>
            <GlassCardDescription>
              Modeles entraines disponibles dans Ollama
            </GlassCardDescription>
          </GlassCardHeader>
          <GlassCardContent>
            {models.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                Aucun modele fine-tune disponible
              </p>
            ) : (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {models.map((model) => (
                  <ModelCard
                    key={model.name}
                    model={model}
                    onDelete={handleDeleteModel}
                    onExport={handleExportModel}
                  />
                ))}
              </div>
            )}
          </GlassCardContent>
        </GlassCard>

        {/* Logs Dialog */}
        <LogsDialog
          jobId={selectedJobId}
          open={showLogsDialog}
          onOpenChange={setShowLogsDialog}
        />
      </div>
    </DashboardLayout>
  );
}