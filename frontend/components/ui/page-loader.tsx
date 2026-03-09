/**
 * PageLoader - Consistent full-page loading spinner.
 * Use this for page-level or section-level loading states.
 * For content-specific loading, prefer skeleton components from @/components/skeletons.
 */
export function PageLoader({ text, fullScreen = false }: { text?: string; fullScreen?: boolean }) {
  return (
    <div className={`flex flex-col items-center justify-center ${fullScreen ? 'h-screen w-screen bg-background' : 'h-96'}`}>
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      {text && <p className="mt-4 text-sm text-muted-foreground">{text}</p>}
    </div>
  );
}
