import React from 'react';
import { GlassCard, GlassCardContent, GlassCardHeader, GlassCardTitle } from '@/components/ui/glass-card';
import { Badge } from '@/components/ui/badge';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { HiOutlineLightBulb, HiOutlineDocumentText, HiOutlineClipboardDocumentList } from 'react-icons/hi2';

interface SynthesizedSection {
  level: string;
  title: string;
  summary: string;
  key_points: string[];
  confidence: number;
}

interface Recommendation {
  description: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  rationale?: string;
  type?: string;
}

interface UnifiedSynthesisData {
  executive_summary: string;
  sections: SynthesizedSection[];
  recommendations: Recommendation[];
  overall_confidence: number;
  territory?: string;
  sector?: string;
}

interface UnifiedSynthesisDisplayProps {
  data: UnifiedSynthesisData;
  className?: string;
}

export default function UnifiedSynthesisDisplay({ data, className }: UnifiedSynthesisDisplayProps) {
  if (!data) return null;

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'destructive';
      case 'high': return 'orange'; // destructive variant or custom
      case 'medium': return 'default'; // primary
      case 'low': return 'secondary';
      default: return 'outline';
    }
  };

  const getLevelIcon = (level: string) => {
    switch (level) {
      case 'discovery': return '🔍';
      case 'causal': return '🔗';
      case 'scenario': return '📊';
      case 'strategy': return '🎯';
      case 'theoretical': return '📚';
      default: return '📌';
    }
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Executive Summary */}
      <GlassCard glow="cyan" hoverGlow>
        <GlassCardHeader>
          <GlassCardTitle className="flex items-center gap-2">
            <HiOutlineDocumentText className="h-5 w-5 text-primary" />
            Synthèse Exécutive
          </GlassCardTitle>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="prose prose-invert max-w-none">
            <p className="text-sm leading-relaxed whitespace-pre-line">
              {data.executive_summary}
            </p>
          </div>
          <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
             <span>Confiance globale:</span>
             <Badge variant={data.overall_confidence > 0.7 ? "default" : "secondary"}>
                {(data.overall_confidence * 100).toFixed(0)}%
             </Badge>
          </div>
        </GlassCardContent>
      </GlassCard>

      {/* Recommendations */}
      {data.recommendations && data.recommendations.length > 0 && (
        <GlassCard glow="green" hoverGlow>
            <GlassCardHeader>
            <GlassCardTitle className="flex items-center gap-2">
                <HiOutlineLightBulb className="h-5 w-5 text-green-500" />
                Recommandations Stratégiques
            </GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent>
            <div className="space-y-3">
                {data.recommendations.map((rec, idx) => (
                <div key={idx} className="flex flex-col gap-1 p-3 rounded-lg bg-white/5 border border-white/10">
                    <div className="flex items-start justify-between gap-2">
                        <span className="font-medium text-sm">{rec.description}</span>
                        <Badge variant={getPriorityColor(rec.priority) as any} className="shrink-0 uppercase text-[10px]">
                            {rec.priority}
                        </Badge>
                    </div>
                    {rec.rationale && (
                        <p className="text-xs text-muted-foreground mt-1">
                            {rec.rationale}
                        </p>
                    )}
                </div>
                ))}
            </div>
            </GlassCardContent>
        </GlassCard>
      )}

      {/* Detailed Sections */}
      <GlassCard glow="cyan" hoverGlow>
        <GlassCardHeader>
          <GlassCardTitle className="flex items-center gap-2">
            <HiOutlineClipboardDocumentList className="h-5 w-5 text-blue-500" />
            Détails par Niveau Cognitif
          </GlassCardTitle>
        </GlassCardHeader>
        <GlassCardContent>
          <Accordion type="single" collapsible className="w-full">
            {data.sections.map((section, idx) => (
              <AccordionItem key={idx} value={section.level}>
                <AccordionTrigger className="hover:no-underline">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{getLevelIcon(section.level)}</span>
                    <span>{section.title}</span>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="space-y-3 pt-2">
                    <p className="text-sm text-muted-foreground italic">
                        {section.summary}
                    </p>
                    {section.key_points && section.key_points.length > 0 && (
                        <ul className="list-disc list-inside space-y-1">
                            {section.key_points.map((point, pIdx) => (
                                <li key={pIdx} className="text-sm">
                                    {point}
                                </li>
                            ))}
                        </ul>
                    )}
                    <div className="flex justify-end mt-2">
                        <span className="text-xs text-muted-foreground">
                            Confiance: {(section.confidence * 100).toFixed(0)}%
                        </span>
                    </div>
                  </div>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </GlassCardContent>
      </GlassCard>
    </div>
  );
}
