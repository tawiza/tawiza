'use client';

import { useState, useEffect } from 'react';
import DashboardLayout from '../../../components/layout';
import {
  GlassCard,
  GlassCardContent,
  GlassCardDescription,
  GlassCardHeader,
  GlassCardTitle
} from '../../../components/ui/glass-card';
import { Button } from '../../../components/ui/button';
import { Label } from '../../../components/ui/label';
import { Switch } from '../../../components/ui/switch';
import { Input } from '../../../components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '../../../components/ui/select';
import { Badge } from '../../../components/ui/badge';
import {
  HiOutlinePaintBrush,
  HiOutlineCpuChip,
  HiOutlineMapPin,
  HiOutlineCircleStack,
  HiOutlineTrash,
  HiOutlineArrowDownTray,
  HiOutlineXMark,
  HiOutlinePlus,
  HiOutlineCheckCircle,
  HiOutlineServerStack,
  HiOutlineKey,
  HiOutlineArrowPath,
  HiOutlineGlobeAlt,
  HiOutlineShieldCheck,
  HiOutlineBugAnt,
  HiOutlineBeaker,
  HiOutlineAdjustmentsHorizontal,
} from 'react-icons/hi2';
import { cn } from '../../../lib/utils';
import { useOllamaModels } from '../../../hooks/use-system-health';

// Note: Types OllamaModel and ServiceStatus are imported from use-system-health hook

// French departments for favorites
const DEPARTMENT_OPTIONS = [
  { code: '75', name: 'Paris' },
  { code: '69', name: 'Rhône' },
  { code: '13', name: 'Bouches-du-Rhône' },
  { code: '33', name: 'Gironde' },
  { code: '31', name: 'Haute-Garonne' },
  { code: '59', name: 'Nord' },
  { code: '44', name: 'Loire-Atlantique' },
  { code: '67', name: 'Bas-Rhin' },
  { code: '06', name: 'Alpes-Maritimes' },
  { code: '34', name: 'Hérault' }
];

// Setting section component
function SettingSection({
  title,
  description,
  icon: Icon,
  children
}: {
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <GlassCard glow="cyan" hoverGlow>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <Icon className="h-5 w-5 text-primary" />
          {title}
        </GlassCardTitle>
        <GlassCardDescription>{description}</GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>{children}</GlassCardContent>
    </GlassCard>
  );
}

// Setting row component
function SettingRow({
  label,
  description,
  children
}: {
  label: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-border/50 last:border-0">
      <div className="space-y-0.5">
        <Label className="text-sm font-medium">{label}</Label>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      {children}
    </div>
  );
}


export default function SettingsPage() {
  // Appearance settings
  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('dark');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // TAJINE settings
  const [defaultCognitiveLevel, setDefaultCognitiveLevel] = useState('analytique');
  const [exportFormat, setExportFormat] = useState('pdf');
  const [streamingEnabled, setStreamingEnabled] = useState(true);

  // LLM Configuration - using the useOllamaModels hook for real-time data
  const {
    models: ollamaModels,
    defaultModel,
    isLoading: loadingModels,
    setDefaultModel: handleSetDefaultModel,
    refresh: refreshModels
  } = useOllamaModels();
  const [ollamaUrl, setOllamaUrl] = useState('http://localhost:11434');
  const [openaiKey, setOpenaiKey] = useState('');
  const [anthropicKey, setAnthropicKey] = useState('');

  // Favorite departments
  const [favorites, setFavorites] = useState<string[]>(['75', '69', '13']);
  const [showDeptSelect, setShowDeptSelect] = useState(false);

  // Notification state
  const [saved, setSaved] = useState(false);

  // Data Sources settings
  const [sireneEnabled, setSireneEnabled] = useState(true);
  const [bodaccEnabled, setBodaccEnabled] = useState(true);
  const [boampEnabled, setBoampEnabled] = useState(true);
  const [banEnabled, setBanEnabled] = useState(true);
  const [inseeToken, setInseeToken] = useState('');

  // Knowledge Graph settings
  const [neo4jUrl, setNeo4jUrl] = useState('bolt://localhost:7687');
  const [neo4jUser, setNeo4jUser] = useState('neo4j');
  const [neo4jPassword, setNeo4jPassword] = useState('');
  const [neo4jEnabled, setNeo4jEnabled] = useState(false);

  // Crawler settings
  const [crawlerRateLimit, setCrawlerRateLimit] = useState(5);
  const [crawlerStealthMode, setCrawlerStealthMode] = useState(true);
  const [crawlerUserAgent, setCrawlerUserAgent] = useState('Mozilla/5.0');
  const [crawlerMaxRetries, setCrawlerMaxRetries] = useState(3);

  // Monitoring settings
  const [sentryDsn, setSentryDsn] = useState('');
  const [loggingLevel, setLoggingLevel] = useState('INFO');
  const [telemetryEnabled, setTelemetryEnabled] = useState(true);

  // Agent settings
  const [agentAutonomy, setAgentAutonomy] = useState<'low' | 'medium' | 'high'>('medium');
  const [maxDelegationDepth, setMaxDelegationDepth] = useState(3);
  const [confirmCriticalActions, setConfirmCriticalActions] = useState(true);
  const [browserActionsEnabled, setBrowserActionsEnabled] = useState(true);

  // Note: Ollama fetching and health checks are now handled by the useOllamaModels() and
  // useSystemHealth() hooks respectively, which provide real-time data with automatic refresh

  // Load settings from localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem('tawiza-theme');
    const savedSidebar = localStorage.getItem('tawiza-sidebar-collapsed');
    const savedCognitive = localStorage.getItem('tawiza-cognitive-level');
    const savedFormat = localStorage.getItem('tawiza-export-format');
    const savedStreaming = localStorage.getItem('tawiza-streaming');
    const savedFavorites = localStorage.getItem('tawiza-favorites');
    const savedOllamaUrl = localStorage.getItem('tawiza-ollama-url');
    // Note: defaultModel is now managed by the backend via useOllamaModels hook
    const savedOpenaiKey = localStorage.getItem('tawiza-openai-key');
    const savedAnthropicKey = localStorage.getItem('tawiza-anthropic-key');

    // Data Sources
    const savedSireneEnabled = localStorage.getItem('tawiza-sirene-enabled');
    const savedBodaccEnabled = localStorage.getItem('tawiza-bodacc-enabled');
    const savedBoampEnabled = localStorage.getItem('tawiza-boamp-enabled');
    const savedBanEnabled = localStorage.getItem('tawiza-ban-enabled');
    const savedInseeToken = localStorage.getItem('tawiza-insee-token');

    // Knowledge Graph
    const savedNeo4jUrl = localStorage.getItem('tawiza-neo4j-url');
    const savedNeo4jUser = localStorage.getItem('tawiza-neo4j-user');
    const savedNeo4jPassword = localStorage.getItem('tawiza-neo4j-password');
    const savedNeo4jEnabled = localStorage.getItem('tawiza-neo4j-enabled');

    // Crawler
    const savedCrawlerRateLimit = localStorage.getItem('tawiza-crawler-rate-limit');
    const savedCrawlerStealthMode = localStorage.getItem('tawiza-crawler-stealth');
    const savedCrawlerUserAgent = localStorage.getItem('tawiza-crawler-user-agent');
    const savedCrawlerMaxRetries = localStorage.getItem('tawiza-crawler-max-retries');

    // Monitoring
    const savedSentryDsn = localStorage.getItem('tawiza-sentry-dsn');
    const savedLoggingLevel = localStorage.getItem('tawiza-logging-level');
    const savedTelemetryEnabled = localStorage.getItem('tawiza-telemetry-enabled');

    // Agent
    const savedAgentAutonomy = localStorage.getItem('tawiza-agent-autonomy');
    const savedMaxDelegationDepth = localStorage.getItem('tawiza-max-delegation-depth');
    const savedConfirmCritical = localStorage.getItem('tawiza-confirm-critical');
    const savedBrowserActions = localStorage.getItem('tawiza-browser-actions');

    if (savedTheme) setTheme(savedTheme as 'light' | 'dark' | 'system');
    if (savedSidebar) setSidebarCollapsed(savedSidebar === 'true');
    if (savedCognitive) setDefaultCognitiveLevel(savedCognitive);
    if (savedFormat) setExportFormat(savedFormat);
    if (savedStreaming !== null) setStreamingEnabled(savedStreaming === 'true');
    if (savedFavorites) setFavorites(JSON.parse(savedFavorites));
    if (savedOllamaUrl) setOllamaUrl(savedOllamaUrl);
    // Note: defaultModel is managed by the backend API, not localStorage
    if (savedOpenaiKey) setOpenaiKey(savedOpenaiKey);
    if (savedAnthropicKey) setAnthropicKey(savedAnthropicKey);

    // Data Sources
    if (savedSireneEnabled !== null) setSireneEnabled(savedSireneEnabled === 'true');
    if (savedBodaccEnabled !== null) setBodaccEnabled(savedBodaccEnabled === 'true');
    if (savedBoampEnabled !== null) setBoampEnabled(savedBoampEnabled === 'true');
    if (savedBanEnabled !== null) setBanEnabled(savedBanEnabled === 'true');
    if (savedInseeToken) setInseeToken(savedInseeToken);

    // Knowledge Graph
    if (savedNeo4jUrl) setNeo4jUrl(savedNeo4jUrl);
    if (savedNeo4jUser) setNeo4jUser(savedNeo4jUser);
    if (savedNeo4jPassword) setNeo4jPassword(savedNeo4jPassword);
    if (savedNeo4jEnabled !== null) setNeo4jEnabled(savedNeo4jEnabled === 'true');

    // Crawler
    if (savedCrawlerRateLimit) setCrawlerRateLimit(parseInt(savedCrawlerRateLimit));
    if (savedCrawlerStealthMode !== null) setCrawlerStealthMode(savedCrawlerStealthMode === 'true');
    if (savedCrawlerUserAgent) setCrawlerUserAgent(savedCrawlerUserAgent);
    if (savedCrawlerMaxRetries) setCrawlerMaxRetries(parseInt(savedCrawlerMaxRetries));

    // Monitoring
    if (savedSentryDsn) setSentryDsn(savedSentryDsn);
    if (savedLoggingLevel) setLoggingLevel(savedLoggingLevel);
    if (savedTelemetryEnabled !== null) setTelemetryEnabled(savedTelemetryEnabled === 'true');

    // Agent
    if (savedAgentAutonomy) setAgentAutonomy(savedAgentAutonomy as 'low' | 'medium' | 'high');
    if (savedMaxDelegationDepth) setMaxDelegationDepth(parseInt(savedMaxDelegationDepth));
    if (savedConfirmCritical !== null) setConfirmCriticalActions(savedConfirmCritical === 'true');
    if (savedBrowserActions !== null) setBrowserActionsEnabled(savedBrowserActions === 'true');
  }, []);

  // Note: Connection checks are now automatic via the hooks

  // Save settings
  const handleSave = () => {
    // Basic settings
    localStorage.setItem('tawiza-theme', theme);
    localStorage.setItem('tawiza-sidebar-collapsed', String(sidebarCollapsed));
    localStorage.setItem('tawiza-cognitive-level', defaultCognitiveLevel);
    localStorage.setItem('tawiza-export-format', exportFormat);
    localStorage.setItem('tawiza-streaming', String(streamingEnabled));
    localStorage.setItem('tawiza-favorites', JSON.stringify(favorites));
    localStorage.setItem('tawiza-ollama-url', ollamaUrl);
    // Note: defaultModel is saved via the backend API, not localStorage
    localStorage.setItem('tawiza-openai-key', openaiKey);
    localStorage.setItem('tawiza-anthropic-key', anthropicKey);

    // Data Sources
    localStorage.setItem('tawiza-sirene-enabled', String(sireneEnabled));
    localStorage.setItem('tawiza-bodacc-enabled', String(bodaccEnabled));
    localStorage.setItem('tawiza-boamp-enabled', String(boampEnabled));
    localStorage.setItem('tawiza-ban-enabled', String(banEnabled));
    localStorage.setItem('tawiza-insee-token', inseeToken);

    // Knowledge Graph
    localStorage.setItem('tawiza-neo4j-url', neo4jUrl);
    localStorage.setItem('tawiza-neo4j-user', neo4jUser);
    localStorage.setItem('tawiza-neo4j-password', neo4jPassword);
    localStorage.setItem('tawiza-neo4j-enabled', String(neo4jEnabled));

    // Crawler
    localStorage.setItem('tawiza-crawler-rate-limit', String(crawlerRateLimit));
    localStorage.setItem('tawiza-crawler-stealth', String(crawlerStealthMode));
    localStorage.setItem('tawiza-crawler-user-agent', crawlerUserAgent);
    localStorage.setItem('tawiza-crawler-max-retries', String(crawlerMaxRetries));

    // Monitoring
    localStorage.setItem('tawiza-sentry-dsn', sentryDsn);
    localStorage.setItem('tawiza-logging-level', loggingLevel);
    localStorage.setItem('tawiza-telemetry-enabled', String(telemetryEnabled));

    // Agent
    localStorage.setItem('tawiza-agent-autonomy', agentAutonomy);
    localStorage.setItem('tawiza-max-delegation-depth', String(maxDelegationDepth));
    localStorage.setItem('tawiza-confirm-critical', String(confirmCriticalActions));
    localStorage.setItem('tawiza-browser-actions', String(browserActionsEnabled));

    // Apply theme
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else if (theme === 'light') {
      document.documentElement.classList.remove('dark');
    }

    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  // Format model size
  const formatSize = (bytes: number) => {
    if (!bytes) return '0 GB';
    const gb = bytes / (1024 * 1024 * 1024);
    return `${gb.toFixed(1)} GB`;
  };

  // Note: StatusBadge is now replaced by SystemHealthBar component

  // Add favorite department
  const addFavorite = (code: string) => {
    if (!favorites.includes(code)) {
      setFavorites([...favorites, code]);
    }
    setShowDeptSelect(false);
  };

  // Remove favorite department
  const removeFavorite = (code: string) => {
    setFavorites(favorites.filter((f) => f !== code));
  };

  // Clear cache
  const handleClearCache = () => {
    localStorage.clear();
    window.location.reload();
  };

  // Export data
  const handleExportData = () => {
    const data = {
      theme,
      sidebarCollapsed,
      defaultCognitiveLevel,
      exportFormat,
      streamingEnabled,
      favorites,
      exportedAt: new Date().toISOString()
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: 'application/json'
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'tawiza-settings.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <DashboardLayout title="Configuration" description="Preferences utilisateur">
      <div className="h-full w-full space-y-6">
        {/* Header */}
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-bold">Configuration</h1>
            <p className="text-sm text-muted-foreground">
              Personnalisez votre experience Tawiza
            </p>
          </div>

          <Button
            onClick={handleSave}
            className={cn(
              'gap-2 transition-normal',
              saved ? 'bg-[var(--success)] hover:bg-[var(--success)]' : 'hover:glow-cyan'
            )}
          >
            {saved ? (
              <>
                <HiOutlineCheckCircle className="h-4 w-4" />
                Enregistre!
              </>
            ) : (
              'Enregistrer'
            )}
          </Button>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* LLM Configuration */}
          <SettingSection
            title="Modeles LLM"
            description="Configuration Ollama et API externes"
            icon={HiOutlineServerStack}
          >
            <SettingRow
              label="Endpoint Ollama"
              description="URL du serveur Ollama local"
            >
              <div className="flex items-center gap-2">
                <Input
                  value={ollamaUrl}
                  onChange={(e) => setOllamaUrl(e.target.value)}
                  placeholder="http://localhost:11434"
                  className="w-48"
                />
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={refreshModels}
                  disabled={loadingModels}
                >
                  <HiOutlineArrowPath className={cn("h-4 w-4", loadingModels && "animate-spin")} />
                </Button>
              </div>
            </SettingRow>

            <SettingRow
              label="Modele par defaut"
              description="Modele utilise pour TAJINE"
            >
              <Select value={defaultModel || ''} onValueChange={handleSetDefaultModel} disabled={ollamaModels.length === 0}>
                <SelectTrigger className="w-48">
                  <SelectValue placeholder="Aucun modele" />
                </SelectTrigger>
                <SelectContent>
                  {ollamaModels.map((model) => (
                    <SelectItem key={model.name} value={model.name}>
                      <div className="flex items-center justify-between w-full">
                        <span>{model.name}</span>
                        <span className="text-xs text-muted-foreground ml-2">
                          {formatSize(model.size)}
                        </span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </SettingRow>

            {ollamaModels.length > 0 && (
              <div className="pt-2">
                <Label className="text-xs text-muted-foreground mb-2 block">
                  Modeles disponibles ({ollamaModels.length})
                </Label>
                <div className="flex flex-wrap gap-1">
                  {ollamaModels.slice(0, 5).map((model) => (
                    <Badge
                      key={model.name}
                      variant="secondary"
                      className="text-xs cursor-pointer hover:bg-primary/20"
                      onClick={() => handleSetDefaultModel(model.name)}
                    >
                      {model.name}
                    </Badge>
                  ))}
                  {ollamaModels.length > 5 && (
                    <Badge variant="outline" className="text-xs">
                      +{ollamaModels.length - 5}
                    </Badge>
                  )}
                </div>
              </div>
            )}
          </SettingSection>

          {/* API Keys */}
          <SettingSection
            title="Cles API"
            description="APIs externes (optionnel)"
            icon={HiOutlineKey}
          >
            <SettingRow
              label="OpenAI API Key"
              description="Pour GPT-4, embeddings, etc."
            >
              <Input
                type="password"
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
                placeholder="sk-..."
                className="w-48"
              />
            </SettingRow>

            <SettingRow
              label="Anthropic API Key"
              description="Pour Claude (fallback)"
            >
              <Input
                type="password"
                value={anthropicKey}
                onChange={(e) => setAnthropicKey(e.target.value)}
                placeholder="sk-ant-..."
                className="w-48"
              />
            </SettingRow>

            <div className="pt-2 text-xs text-muted-foreground">
              Les cles sont stockees localement et ne sont jamais envoyees au serveur.
            </div>
          </SettingSection>

          {/* Appearance */}
          <SettingSection
            title="Apparence"
            description="Theme et affichage"
            icon={HiOutlinePaintBrush}
          >
            <SettingRow label="Theme" description="Choisissez le theme de l&apos;interface">
              <Select value={theme} onValueChange={(v) => setTheme(v as typeof theme)}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="light">Clair</SelectItem>
                  <SelectItem value="dark">Sombre</SelectItem>
                  <SelectItem value="system">Systeme</SelectItem>
                </SelectContent>
              </Select>
            </SettingRow>

            <SettingRow
              label="Sidebar repliee"
              description="Demarrer avec la sidebar fermee"
            >
              <Switch
                checked={sidebarCollapsed}
                onCheckedChange={setSidebarCollapsed}
              />
            </SettingRow>
          </SettingSection>

          {/* TAJINE */}
          <SettingSection
            title="TAJINE"
            description="Parametres de l'agent"
            icon={HiOutlineCpuChip}
          >
            <SettingRow
              label="Niveau cognitif par defaut"
              description="Niveau de depart des analyses"
            >
              <Select
                value={defaultCognitiveLevel}
                onValueChange={setDefaultCognitiveLevel}
              >
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="reactif">Reactif</SelectItem>
                  <SelectItem value="analytique">Analytique</SelectItem>
                  <SelectItem value="strategique">Strategique</SelectItem>
                  <SelectItem value="prospectif">Prospectif</SelectItem>
                  <SelectItem value="theorique">Theorique</SelectItem>
                </SelectContent>
              </Select>
            </SettingRow>

            <SettingRow
              label="Format d'export"
              description="Format par defaut des rapports"
            >
              <Select value={exportFormat} onValueChange={setExportFormat}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pdf">PDF</SelectItem>
                  <SelectItem value="csv">CSV</SelectItem>
                  <SelectItem value="json">JSON</SelectItem>
                </SelectContent>
              </Select>
            </SettingRow>

            <SettingRow
              label="Streaming"
              description="Afficher les reponses en temps reel"
            >
              <Switch
                checked={streamingEnabled}
                onCheckedChange={setStreamingEnabled}
              />
            </SettingRow>
          </SettingSection>

          {/* Favorite departments */}
          <SettingSection
            title="Departements favoris"
            description="Acces rapide aux departements"
            icon={HiOutlineMapPin}
          >
            <div className="space-y-4">
              {/* Current favorites */}
              <div className="flex flex-wrap gap-2">
                {favorites.map((code) => {
                  const dept = DEPARTMENT_OPTIONS.find((d) => d.code === code);
                  return (
                    <Badge
                      key={code}
                      variant="secondary"
                      className="gap-1 pr-1 bg-primary/10 text-primary border-primary/20"
                    >
                      <span className="font-mono">{code}</span>
                      {dept?.name}
                      <button
                        onClick={() => removeFavorite(code)}
                        className="ml-1 p-0.5 rounded hover:bg-primary/20 transition-normal"
                      >
                        <HiOutlineXMark className="h-3 w-3" />
                      </button>
                    </Badge>
                  );
                })}

                {favorites.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    Aucun departement favori
                  </p>
                )}
              </div>

              {/* Add favorite */}
              {showDeptSelect ? (
                <Select onValueChange={addFavorite}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Choisir un departement..." />
                  </SelectTrigger>
                  <SelectContent>
                    {DEPARTMENT_OPTIONS.filter(
                      (d) => !favorites.includes(d.code)
                    ).map((dept) => (
                      <SelectItem key={dept.code} value={dept.code}>
                        <span className="font-mono mr-2">{dept.code}</span>
                        {dept.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowDeptSelect(true)}
                  className="gap-1"
                >
                  <HiOutlinePlus className="h-4 w-4" />
                  Ajouter
                </Button>
              )}
            </div>
          </SettingSection>

          {/* Data */}
          <SettingSection
            title="Donnees"
            description="Gestion du cache et des exports"
            icon={HiOutlineCircleStack}
          >
            <div className="space-y-4">
              <SettingRow
                label="Vider le cache"
                description="Supprime toutes les donnees locales"
              >
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleClearCache}
                  className="gap-1 text-[var(--error)] border-[var(--error)]/30 hover:bg-[var(--error)]/10"
                >
                  <HiOutlineTrash className="h-4 w-4" />
                  Vider
                </Button>
              </SettingRow>

              <SettingRow
                label="Exporter les parametres"
                description="Telecharger vos preferences en JSON"
              >
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleExportData}
                  className="gap-1"
                >
                  <HiOutlineArrowDownTray className="h-4 w-4" />
                  Exporter
                </Button>
              </SettingRow>
            </div>
          </SettingSection>

          {/* Data Sources */}
          <SettingSection
            title="Sources de Donnees"
            description="APIs gouvernementales francaises"
            icon={HiOutlineGlobeAlt}
          >
            <SettingRow
              label="SIRENE (INSEE)"
              description="Recherche d'entreprises"
            >
              <Switch checked={sireneEnabled} onCheckedChange={setSireneEnabled} />
            </SettingRow>

            <SettingRow
              label="BODACC"
              description="Annonces legales (procedures, publications)"
            >
              <Switch checked={bodaccEnabled} onCheckedChange={setBodaccEnabled} />
            </SettingRow>

            <SettingRow
              label="BOAMP"
              description="Marches publics"
            >
              <Switch checked={boampEnabled} onCheckedChange={setBoampEnabled} />
            </SettingRow>

            <SettingRow
              label="BAN (Adresse)"
              description="Geocodage d'adresses"
            >
              <Switch checked={banEnabled} onCheckedChange={setBanEnabled} />
            </SettingRow>

            <SettingRow
              label="Token INSEE"
              description="Pour Donnees Locales et DVF"
            >
              <Input
                type="password"
                value={inseeToken}
                onChange={(e) => setInseeToken(e.target.value)}
                placeholder="Bearer token..."
                className="w-48"
              />
            </SettingRow>
          </SettingSection>

          {/* Knowledge Graph */}
          <SettingSection
            title="Knowledge Graph"
            description="Base de donnees Neo4j"
            icon={HiOutlineShieldCheck}
          >
            <SettingRow
              label="Activer Neo4j"
              description="Enrichissement relationnel des donnees"
            >
              <Switch checked={neo4jEnabled} onCheckedChange={setNeo4jEnabled} />
            </SettingRow>

            <SettingRow
              label="URL Neo4j"
              description="Connexion Bolt"
            >
              <Input
                value={neo4jUrl}
                onChange={(e) => setNeo4jUrl(e.target.value)}
                placeholder="bolt://localhost:7687"
                className="w-48"
                disabled={!neo4jEnabled}
              />
            </SettingRow>

            <SettingRow
              label="Utilisateur"
              description="Nom d'utilisateur Neo4j"
            >
              <Input
                value={neo4jUser}
                onChange={(e) => setNeo4jUser(e.target.value)}
                placeholder="neo4j"
                className="w-48"
                disabled={!neo4jEnabled}
              />
            </SettingRow>

            <SettingRow
              label="Mot de passe"
              description="Mot de passe Neo4j"
            >
              <Input
                type="password"
                value={neo4jPassword}
                onChange={(e) => setNeo4jPassword(e.target.value)}
                placeholder="••••••••"
                className="w-48"
                disabled={!neo4jEnabled}
              />
            </SettingRow>
          </SettingSection>

          {/* Crawler */}
          <SettingSection
            title="Crawler"
            description="Collecte de donnees web"
            icon={HiOutlineBeaker}
          >
            <SettingRow
              label="Rate Limit"
              description="Requetes par seconde"
            >
              <Select
                value={String(crawlerRateLimit)}
                onValueChange={(v) => setCrawlerRateLimit(parseInt(v))}
              >
                <SelectTrigger className="w-24">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">1/s</SelectItem>
                  <SelectItem value="2">2/s</SelectItem>
                  <SelectItem value="5">5/s</SelectItem>
                  <SelectItem value="10">10/s</SelectItem>
                </SelectContent>
              </Select>
            </SettingRow>

            <SettingRow
              label="Mode Stealth"
              description="Contournement anti-bot (nodriver)"
            >
              <Switch checked={crawlerStealthMode} onCheckedChange={setCrawlerStealthMode} />
            </SettingRow>

            <SettingRow
              label="Max Retries"
              description="Nombre de tentatives"
            >
              <Select
                value={String(crawlerMaxRetries)}
                onValueChange={(v) => setCrawlerMaxRetries(parseInt(v))}
              >
                <SelectTrigger className="w-24">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">1</SelectItem>
                  <SelectItem value="3">3</SelectItem>
                  <SelectItem value="5">5</SelectItem>
                </SelectContent>
              </Select>
            </SettingRow>

            <SettingRow
              label="User-Agent"
              description="En-tete HTTP"
            >
              <Input
                value={crawlerUserAgent}
                onChange={(e) => setCrawlerUserAgent(e.target.value)}
                placeholder="Mozilla/5.0..."
                className="w-48 text-xs"
              />
            </SettingRow>
          </SettingSection>

          {/* Monitoring */}
          <SettingSection
            title="Monitoring"
            description="Logs et telemetrie"
            icon={HiOutlineBugAnt}
          >
            <SettingRow
              label="Sentry DSN"
              description="URL de collecte d'erreurs"
            >
              <Input
                value={sentryDsn}
                onChange={(e) => setSentryDsn(e.target.value)}
                placeholder="https://xxx@sentry.io/yyy"
                className="w-48"
              />
            </SettingRow>

            <SettingRow
              label="Niveau de log"
              description="Verbosité des logs"
            >
              <Select value={loggingLevel} onValueChange={setLoggingLevel}>
                <SelectTrigger className="w-28">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="DEBUG">DEBUG</SelectItem>
                  <SelectItem value="INFO">INFO</SelectItem>
                  <SelectItem value="WARNING">WARNING</SelectItem>
                  <SelectItem value="ERROR">ERROR</SelectItem>
                </SelectContent>
              </Select>
            </SettingRow>

            <SettingRow
              label="Telemetrie"
              description="Envoyer des metriques anonymes"
            >
              <Switch checked={telemetryEnabled} onCheckedChange={setTelemetryEnabled} />
            </SettingRow>
          </SettingSection>

          {/* Agent Autonomy */}
          <SettingSection
            title="Autonomie Agent"
            description="Controle de l'agent TAJINE"
            icon={HiOutlineAdjustmentsHorizontal}
          >
            <SettingRow
              label="Niveau d'autonomie"
              description="Liberte de decision de l'agent"
            >
              <Select
                value={agentAutonomy}
                onValueChange={(v) => setAgentAutonomy(v as 'low' | 'medium' | 'high')}
              >
                <SelectTrigger className="w-28">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Faible</SelectItem>
                  <SelectItem value="medium">Moyen</SelectItem>
                  <SelectItem value="high">Eleve</SelectItem>
                </SelectContent>
              </Select>
            </SettingRow>

            <SettingRow
              label="Profondeur de delegation"
              description="Niveaux max de sous-agents"
            >
              <Select
                value={String(maxDelegationDepth)}
                onValueChange={(v) => setMaxDelegationDepth(parseInt(v))}
              >
                <SelectTrigger className="w-24">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">1</SelectItem>
                  <SelectItem value="2">2</SelectItem>
                  <SelectItem value="3">3</SelectItem>
                  <SelectItem value="5">5</SelectItem>
                </SelectContent>
              </Select>
            </SettingRow>

            <SettingRow
              label="Confirmer actions critiques"
              description="Demander validation pour actions importantes"
            >
              <Switch
                checked={confirmCriticalActions}
                onCheckedChange={setConfirmCriticalActions}
              />
            </SettingRow>

            <SettingRow
              label="Actions navigateur"
              description="Autoriser la navigation web automatique"
            >
              <Switch
                checked={browserActionsEnabled}
                onCheckedChange={setBrowserActionsEnabled}
              />
            </SettingRow>
          </SettingSection>

          {/* Advanced Configuration */}
          <SettingSection
            title="Configuration Avancee"
            description="Parametres techniques du systeme"
            icon={HiOutlineServerStack}
          >
            <SettingRow
              label="Configuration Crawler"
              description="Proxies, CAPTCHA, User-Agents, Stealth"
            >
              <a
                href="/dashboard/settings/crawler"
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary/20 hover:bg-primary/30 text-primary rounded-lg text-sm font-medium transition-colors"
              >
                <HiOutlineGlobeAlt className="h-4 w-4" />
                Configurer
              </a>
            </SettingRow>
            <SettingRow
              label="Fine-tuning"
              description="Entrainement et amelioration du modele"
            >
              <a
                href="/dashboard/fine-tuning"
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary/20 hover:bg-primary/30 text-primary rounded-lg text-sm font-medium transition-colors"
              >
                <HiOutlineBeaker className="h-4 w-4" />
                Configurer
              </a>
            </SettingRow>
          </SettingSection>
        </div>

        {/* Version info */}
        <div className="text-center text-xs text-muted-foreground pt-4">
          Tawiza v2.0 — Intelligence Territoriale
        </div>
      </div>
    </DashboardLayout>
  );
}
