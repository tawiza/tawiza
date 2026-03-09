'use client';

import { useState } from 'react';
import useSWR from 'swr';
import {
  GlassCard,
  GlassCardContent,
  GlassCardHeader,
  GlassCardTitle,
} from '@/components/ui/glass-card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { HiOutlineScale, HiOutlinePlus, HiOutlineXMark } from 'react-icons/hi2';

// Use relative URLs for Next.js proxy (same-origin cookies)
const API_BASE = '';

// Fetcher for SWR
const fetcher = async (url: string) => {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
};

interface DepartmentComparison {
  code: string;
  name?: string;
  region?: string;
  enterprises: number;
  growth: number;
  price_m2: number;
  unemployment_rate: number;
  budget_per_capita: number;
  debt_per_capita: number;
  error?: string;
}

// Common French departments for quick selection
const POPULAR_DEPARTMENTS = [
  { code: '75', name: 'Paris' },
  { code: '69', name: 'Rhône' },
  { code: '13', name: 'Bouches-du-Rhône' },
  { code: '33', name: 'Gironde' },
  { code: '31', name: 'Haute-Garonne' },
  { code: '44', name: 'Loire-Atlantique' },
  { code: '59', name: 'Nord' },
  { code: '06', name: 'Alpes-Maritimes' },
  { code: '34', name: 'Hérault' },
  { code: '67', name: 'Bas-Rhin' },
];

function MetricRow({
  label,
  values,
  format,
  higherIsBetter = true,
}: {
  label: string;
  values: (number | undefined)[];
  format: (v: number) => string;
  higherIsBetter?: boolean;
}) {
  const validValues = values.filter((v): v is number => v !== undefined);
  const best = higherIsBetter ? Math.max(...validValues) : Math.min(...validValues);

  return (
    <div className="grid grid-cols-4 gap-2 py-2 border-b border-white/5 last:border-0">
      <div className="text-sm text-muted-foreground">{label}</div>
      {values.map((value, i) => (
        <div
          key={i}
          className={`text-sm font-medium text-right ${
            value === best ? 'text-green-400' : 'text-foreground'
          }`}
        >
          {value !== undefined ? format(value) : '-'}
        </div>
      ))}
    </div>
  );
}

export function ComparatorWidget() {
  const [selectedCodes, setSelectedCodes] = useState<string[]>(['75', '69']);

  const codesParam = selectedCodes.join(',');
  const { data, error, isLoading } = useSWR<DepartmentComparison[] | { detail?: string }>(
    selectedCodes.length > 0
      ? `${API_BASE}/api/v1/territorial/compare?codes=${codesParam}`
      : null,
    fetcher,
    {
      revalidateOnFocus: false,
    }
  );

  // Handle both array and error object responses
  const departments = Array.isArray(data) ? data : [];

  const addDepartment = (code: string) => {
    if (selectedCodes.length < 3 && !selectedCodes.includes(code)) {
      setSelectedCodes([...selectedCodes, code]);
    }
  };

  const removeDepartment = (code: string) => {
    setSelectedCodes(selectedCodes.filter((c) => c !== code));
  };

  const availableDepartments = POPULAR_DEPARTMENTS.filter(
    (d) => !selectedCodes.includes(d.code)
  );

  // Pad data array to always have 3 slots
  const paddedData: (DepartmentComparison | null)[] = [
    ...departments,
    ...Array(3 - departments.length).fill(null),
  ].slice(0, 3);

  if (error) {
    return (
      <GlassCard glow="red">
        <GlassCardHeader>
          <GlassCardTitle className="flex items-center gap-2">
            <HiOutlineScale className="h-5 w-5 text-red-400" />
            Comparateur
          </GlassCardTitle>
        </GlassCardHeader>
        <GlassCardContent>
          <p className="text-sm text-muted-foreground">Erreur de chargement</p>
        </GlassCardContent>
      </GlassCard>
    );
  }

  return (
    <GlassCard glow="cyan" hoverGlow>
      <GlassCardHeader className="flex flex-row items-center justify-between pb-2">
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineScale className="h-5 w-5 text-primary" />
          Comparateur
        </GlassCardTitle>
        {selectedCodes.length < 3 && availableDepartments.length > 0 && (
          <Select onValueChange={addDepartment}>
            <SelectTrigger className="w-[140px] h-8 text-xs">
              <HiOutlinePlus className="h-4 w-4 mr-1" />
              <SelectValue placeholder="Ajouter" />
            </SelectTrigger>
            <SelectContent>
              {availableDepartments.map((dept) => (
                <SelectItem key={dept.code} value={dept.code}>
                  {dept.code} - {dept.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </GlassCardHeader>
      <GlassCardContent>
        {isLoading ? (
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-8 bg-muted/20 rounded animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {/* Department headers */}
            <div className="grid grid-cols-4 gap-2 pb-2 border-b border-white/10">
              <div className="text-xs text-muted-foreground uppercase tracking-wider">
                Métrique
              </div>
              {paddedData.map((dept, i) => (
                <div key={i} className="flex items-center justify-end gap-1">
                  {dept ? (
                    <>
                      <Badge variant="outline" className="text-xs">
                        {dept.code}
                      </Badge>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-5 w-5"
                        onClick={() => removeDepartment(dept.code)}
                      >
                        <HiOutlineXMark className="h-3 w-3" />
                      </Button>
                    </>
                  ) : (
                    <span className="text-xs text-muted-foreground">-</span>
                  )}
                </div>
              ))}
            </div>

            {/* Metric rows */}
            <MetricRow
              label="Entreprises"
              values={paddedData.map((d) => d?.enterprises)}
              format={(v) => v.toLocaleString('fr-FR')}
            />
            <MetricRow
              label="Croissance"
              values={paddedData.map((d) => d?.growth)}
              format={(v) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`}
            />
            <MetricRow
              label="Prix m²"
              values={paddedData.map((d) => d?.price_m2)}
              format={(v) => `${v.toLocaleString('fr-FR')} €`}
              higherIsBetter={false}
            />
            <MetricRow
              label="Chômage"
              values={paddedData.map((d) => d?.unemployment_rate)}
              format={(v) => `${v.toFixed(1)}%`}
              higherIsBetter={false}
            />
            <MetricRow
              label="Budget/hab"
              values={paddedData.map((d) => d?.budget_per_capita)}
              format={(v) => `${v.toLocaleString('fr-FR')} €`}
            />
            <MetricRow
              label="Dette/hab"
              values={paddedData.map((d) => d?.debt_per_capita)}
              format={(v) => `${v.toLocaleString('fr-FR')} €`}
              higherIsBetter={false}
            />
          </div>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}

export default ComparatorWidget;
