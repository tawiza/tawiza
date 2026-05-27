import Link from "next/link";

export default function InvestigationPage() {
  return (
    <div className="flex h-full w-full items-center justify-center p-8">
      <div className="max-w-xl space-y-4 text-center">
        <h1 className="text-2xl font-semibold">Investigation</h1>
        <p className="text-muted-foreground">
          L&apos;interface d&apos;investigation territoriale n&apos;est pas
          encore disponible dans cette version. Les analyses peuvent être
          lancées depuis l&apos;agent TAJINE ou via l&apos;API REST.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Link
            href="/dashboard/tajine"
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Ouvrir TAJINE
          </Link>
          <Link
            href="/api/v1/tajine/conversations"
            className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted"
          >
            API: GET /api/v1/tajine/conversations
          </Link>
        </div>
      </div>
    </div>
  );
}
