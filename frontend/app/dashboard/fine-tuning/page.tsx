import Link from "next/link";

export default function FineTuningPage() {
  return (
    <div className="flex h-full w-full items-center justify-center p-8">
      <div className="max-w-xl space-y-4 text-center">
        <h1 className="text-2xl font-semibold">Fine-tuning</h1>
        <p className="text-muted-foreground">
          L&apos;interface de fine-tuning n&apos;est pas encore disponible
          dans cette version. L&apos;entrainement et l&apos;amélioration du
          modèle se font via les scripts <code>src/</code> et MLflow, en
          dehors du tableau de bord.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Link
            href="/dashboard/settings"
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Retour aux paramètres
          </Link>
          <Link
            href="https://github.com/tawiza/tawiza/blob/main/docs/modules/llm.md"
            className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted"
          >
            Documentation LLM
          </Link>
        </div>
      </div>
    </div>
  );
}
