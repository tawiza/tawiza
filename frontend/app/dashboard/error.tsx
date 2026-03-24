'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const router = useRouter();

  useEffect(() => {
    console.error('Dashboard error:', error);

    // Report to backend
    fetch('/api/v1/errors/frontend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: error.message,
        stack: error.stack,
        digest: error.digest,
        url: window.location.href,
        timestamp: new Date().toISOString(),
        source: 'dashboard-error',
      }),
    }).catch(() => {});
  }, [error]);

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center">
      <div className="glass p-8 max-w-lg w-full text-center space-y-4">
        <div className="text-5xl">&#x26A0;&#xFE0F;</div>
        <h2 className="text-xl font-bold text-amber-400">Erreur Dashboard</h2>
        <p className="text-sm text-muted-foreground">
          {error.message || 'Une erreur est survenue lors du chargement du dashboard.'}
        </p>
        {error.digest && (
          <p className="text-xs text-gray-500 font-mono">Ref: {error.digest}</p>
        )}
        <div className="flex gap-3 justify-center pt-2">
          <button
            onClick={reset}
            className="px-5 py-2 bg-amber-500 text-black rounded-lg font-medium hover:bg-amber-400 transition-colors"
          >
            Reessayer
          </button>
          <button
            onClick={() => router.push('/dashboard')}
            className="px-5 py-2 border border-border rounded-lg text-sm hover:bg-muted transition-colors"
          >
            Retour accueil
          </button>
        </div>
      </div>
    </div>
  );
}
