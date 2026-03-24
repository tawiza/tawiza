'use client';

import { useState, useRef, useEffect } from 'react';
import { useOllamaModels } from '@/hooks/use-system-health';
import { ChevronDown, Check, Cpu, Download, Loader2 } from 'lucide-react';

interface OllamaModelSelectorProps {
  compact?: boolean;
  onModelChange?: (model: string) => void;
}

export function OllamaModelSelector({ compact = false, onModelChange }: OllamaModelSelectorProps) {
  const { models, defaultModel, isLoading, setDefaultModel, pullModel } = useOllamaModels();
  const [isOpen, setIsOpen] = useState(false);
  const [isPulling, setIsPulling] = useState(false);
  const [pullModelName, setPullModelName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectModel = async (modelName: string) => {
    try {
      setError(null);
      await setDefaultModel(modelName);
      onModelChange?.(modelName);
      setIsOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur');
    }
  };

  const handlePullModel = async () => {
    if (!pullModelName.trim()) return;

    try {
      setIsPulling(true);
      setError(null);
      await pullModel(pullModelName.trim());
      setPullModelName('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Echec du telechargement');
    } finally {
      setIsPulling(false);
    }
  };

  // Format model name for display
  const formatModelName = (name: string): string => {
    // Extract the model name without the tag
    const [base, tag] = name.split(':');
    if (compact) {
      // Show just the base name in compact mode
      return base.split('/').pop() || base;
    }
    return tag ? `${base}:${tag.substring(0, 8)}` : base;
  };

  const currentModelDisplay = defaultModel ? formatModelName(defaultModel) : 'Aucun modele';

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Trigger button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 px-2 py-1 rounded-md bg-white/5 hover:bg-white/10 transition-colors border border-white/10 ${
          isLoading ? 'opacity-50' : ''
        }`}
        disabled={isLoading}
      >
        <Cpu className="w-3.5 h-3.5 text-info" />
        <span className="text-xs text-gray-300 max-w-[100px] truncate">
          {isLoading ? 'Chargement...' : currentModelDisplay}
        </span>
        <ChevronDown
          className={`w-3 h-3 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-72 bg-card border border-white/10 rounded-lg shadow-xl z-50 overflow-hidden">
          {/* Header */}
          <div className="px-3 py-2 border-b border-white/10 bg-white/5">
            <h3 className="text-xs font-medium text-gray-300">Modeles Ollama</h3>
            <p className="text-[10px] text-gray-500">{models.length} modeles disponibles</p>
          </div>

          {/* Model list */}
          <div className="max-h-48 overflow-y-auto">
            {models.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-gray-500">
                Aucun modele disponible
              </div>
            ) : (
              models.map((model) => (
                <button
                  key={model.name}
                  onClick={() => handleSelectModel(model.name)}
                  className={`w-full flex items-center justify-between px-3 py-2 hover:bg-white/5 transition-colors ${
                    model.name === defaultModel ? 'bg-info/10' : ''
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {model.name === defaultModel && (
                      <Check className="w-3.5 h-3.5 text-success" />
                    )}
                    <div className={model.name === defaultModel ? '' : 'ml-5'}>
                      <p className="text-xs text-gray-200 text-left">{model.name}</p>
                      <p className="text-[10px] text-gray-500">{model.size_gb} GB</p>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>

          {/* Pull new model */}
          <div className="px-3 py-2 border-t border-white/10 bg-white/5">
            <div className="flex gap-2">
              <input
                type="text"
                value={pullModelName}
                onChange={(e) => setPullModelName(e.target.value)}
                placeholder="nom-modele:tag"
                className="flex-1 px-2 py-1 text-xs bg-muted border border-white/10 rounded text-gray-200 placeholder-gray-500 focus:outline-none focus:border-info"
                onKeyDown={(e) => e.key === 'Enter' && handlePullModel()}
              />
              <button
                onClick={handlePullModel}
                disabled={isPulling || !pullModelName.trim()}
                className="px-2 py-1 bg-primary hover:bg-primary/80 disabled:opacity-50 disabled:cursor-not-allowed rounded text-xs text-white flex items-center gap-1"
              >
                {isPulling ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <Download className="w-3 h-3" />
                )}
              </button>
            </div>
            {error && <p className="mt-1 text-[10px] text-error">{error}</p>}
          </div>
        </div>
      )}
    </div>
  );
}

export default OllamaModelSelector;
