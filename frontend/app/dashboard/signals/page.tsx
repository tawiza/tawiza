import Link from "next/link";

export default function SignalsPage() {
  return (
    <div className="flex h-full w-full items-center justify-center p-8">
      <div className="max-w-xl space-y-4 text-center">
        <h1 className="text-2xl font-semibold">Signaux territoriaux</h1>
        <p className="text-muted-foreground">
          La vue détaillée des signaux territoriaux n&apos;est pas encore
          disponible. Les signaux par département sont accessibles via
          l&apos;API REST, et un récapitulatif est visible sur la fiche du
          département concerné.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Link
            href="/dashboard/departments"
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Voir les départements
          </Link>
          <Link
            href="/api/v1/signals/list"
            className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted"
          >
            API: GET /api/v1/signals/list
          </Link>
        </div>
      </div>
    </div>
  );
}
