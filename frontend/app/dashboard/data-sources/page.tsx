import Link from "next/link";

export default function DataSourcesPage() {
  return (
    <div className="flex h-full w-full items-center justify-center p-8">
      <div className="max-w-xl space-y-4 text-center">
        <h1 className="text-2xl font-semibold">Sources de données</h1>
        <p className="text-muted-foreground">
          La vue détaillée des sources n&apos;est pas encore disponible dans
          cette version. En attendant, un récapitulatif des sources actives
          est affiché sur le tableau de bord principal, et l&apos;API REST
          expose la liste complète.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Link
            href="/dashboard/main"
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Voir le tableau de bord
          </Link>
          <Link
            href="/api/v1/sources/"
            className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted"
          >
            API: GET /api/v1/sources/
          </Link>
        </div>
      </div>
    </div>
  );
}
