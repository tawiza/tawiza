'use client';

import { useEffect } from 'react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
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
        source: 'global-error',
      }),
    }).catch(() => {});
  }, [error]);

  return (
    <html lang="fr">
      <body className="bg-background text-foreground">
        <div className="min-h-screen flex items-center justify-center p-4">
          <div className="max-w-md w-full text-center space-y-6">
            <div className="text-6xl">&#x26A0;&#xFE0F;</div>
            <h1 className="text-2xl font-bold text-amber-400">
              Erreur critique
            </h1>
            <p className="text-sm text-gray-400">
              L&apos;application a rencontre une erreur inattendue.
            </p>
            {error.digest && (
              <p className="text-xs text-gray-500 font-mono">
                Ref: {error.digest}
              </p>
            )}
            <button
              onClick={reset}
              className="px-6 py-2.5 bg-amber-500 text-black rounded-lg font-medium hover:bg-amber-400 transition-colors"
            >
              Reessayer
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
