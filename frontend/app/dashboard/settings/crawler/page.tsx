import Link from "next/link";

export default function CrawlerSettingsPage() {
  return (
    <div className="flex h-full w-full items-center justify-center p-8">
      <div className="max-w-xl space-y-4 text-center">
        <h1 className="text-2xl font-semibold">Configuration du crawler</h1>
        <p className="text-muted-foreground">
          L&apos;interface de configuration du crawler n&apos;est pas encore
          disponible dans cette version. La configuration courante est lue
          via les variables d&apos;environnement et exposée en lecture seule
          par l&apos;API REST.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Link
            href="/dashboard/settings"
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Retour aux paramètres
          </Link>
          <Link
            href="/api/v1/sources/feeds/config"
            className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted"
          >
            API: GET /api/v1/sources/feeds/config
          </Link>
        </div>
      </div>
    </div>
  );
}
