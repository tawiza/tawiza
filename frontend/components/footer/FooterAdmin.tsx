'use client';

export default function Footer() {
  return (
    <div className="flex w-full flex-col items-center justify-between px-1 pb-8 pt-3 xl:flex-row">
      <p className="mb-4 text-center text-sm font-medium text-zinc-500 dark:text-zinc-400 sm:!mb-0 md:text-lg">
        <span className="mb-4 text-center text-sm text-zinc-500 dark:text-zinc-400 sm:!mb-0 md:text-sm">
          ©{new Date().getFullYear()} Tawiza/TAJINE - Intelligence Territoriale.
        </span>
      </p>
      <div>
        <ul className="flex flex-wrap items-center gap-3 sm:flex-nowrap md:gap-10">
          <li>
            <a
              target="_blank"
              href="https://github.com/tawiza/tawiza"
              className="text-sm font-medium text-zinc-500 hover:text-zinc-950 dark:text-zinc-400"
              rel="noreferrer"
            >
              GitHub
            </a>
          </li>
          <li>
            <a
              target="_blank"
              href="https://api.insee.fr"
              className="text-sm font-medium text-zinc-500 hover:text-zinc-950 dark:text-zinc-400"
              rel="noreferrer"
            >
              API INSEE
            </a>
          </li>
          <li>
            <a
              target="_blank"
              href="https://bodacc.fr"
              className="text-sm font-medium text-zinc-500 hover:text-zinc-950 dark:text-zinc-400"
              rel="noreferrer"
            >
              BODACC
            </a>
          </li>
          <li>
            <a
              target="_blank"
              href="https://boamp.fr"
              className="text-sm font-medium text-zinc-500 hover:text-zinc-950 dark:text-zinc-400"
              rel="noreferrer"
            >
              BOAMP
            </a>
          </li>
        </ul>
      </div>
    </div>
  );
}
