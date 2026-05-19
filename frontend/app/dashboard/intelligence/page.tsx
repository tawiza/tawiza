import Link from "next/link";

export default function IntelligencePage() {
  return (
    <div className="flex h-full w-full items-center justify-center p-8">
      <div className="max-w-xl space-y-4 text-center">
        <h1 className="text-2xl font-semibold">Intelligence territoriale</h1>
        <p className="text-muted-foreground">
          La vue dédiée à l&apos;intelligence territoriale n&apos;est pas
          encore disponible. Une synthèse est affichée sur le tableau de
          bord principal, et les analyses détaillées passent par
          l&apos;agent TAJINE.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Link
            href="/dashboard/main"
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Voir le tableau de bord
          </Link>
          <Link
            href="/dashboard/tajine"
            className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted"
          >
            Ouvrir TAJINE
          </Link>
        </div>
      </div>
    </div>
  );
}
