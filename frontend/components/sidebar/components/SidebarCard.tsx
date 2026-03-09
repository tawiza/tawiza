'use client';

import { Button } from '@/components/ui/button';
import Link from 'next/link';
import { HiOutlineSparkles, HiOutlineCpuChip } from 'react-icons/hi2';

export default function SidebarDocs() {
  return (
    <div className="relative flex flex-col items-center rounded-lg border border-zinc-200 px-3 py-4 dark:border-white/10">
      <div className="flex h-[54px] w-[54px] items-center justify-center rounded-full bg-primary/10">
        <HiOutlineCpuChip className="h-8 w-8 text-primary" />
      </div>
      <div className="mb-3 flex w-full flex-col pt-4">
        <p className="mb-2.5 text-center text-lg font-bold text-zinc-950 dark:text-white">
          TAJINE Agent
        </p>
        <p className="text-center text-sm font-medium text-zinc-500 dark:text-zinc-400">
          Analyse economique territoriale avec 5 niveaux cognitifs et sources officielles francaises.
        </p>
      </div>
      <Link href="/dashboard/ai-chat" className="w-full">
        <Button className="mt-auto flex h-full w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium">
          <HiOutlineSparkles className="h-4 w-4" />
          Demarrer une analyse
        </Button>
      </Link>
    </div>
  );
}
