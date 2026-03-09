'use client';

import { Badge } from '../ui/badge';
import {
  renderThumb,
  renderTrack,
  renderView
} from '@/components/scrollbar/Scrollbar';
import Links from '@/components/sidebar/components/Links';
import SidebarCard from '@/components/sidebar/components/SidebarCard';
import { Card } from '@/components/ui/card';
import { IRoute } from '@/types/types';
import React, { PropsWithChildren } from 'react';
import { Scrollbars } from 'react-custom-scrollbars-2';
import { HiX } from 'react-icons/hi';
import { HiSparkles } from 'react-icons/hi2';

export interface SidebarProps extends PropsWithChildren {
  routes: IRoute[];
  [x: string]: any;
}

function Sidebar(props: SidebarProps) {
  const { routes } = props;

  return (
    <div
      className={`lg:!z-99 fixed !z-[99] min-h-full w-[300px] transition-all md:!z-[99] xl:!z-0 ${
        props.variant === 'auth' ? 'xl:hidden' : 'xl:block'
      } ${props.open ? '' : '-translate-x-[120%] xl:translate-x-[unset]'}`}
    >
      <Card
        className={`m-3 ml-3 h-[96.5vh] w-full overflow-hidden !rounded-lg border-zinc-200 pe-4 dark:border-zinc-800 sm:my-4 sm:mr-4 md:m-5 md:mr-[-50px]`}
      >
        <Scrollbars
          autoHide
          renderTrackVertical={renderTrack}
          renderThumbVertical={renderThumb}
          renderView={renderView}
          universal={true}
        >
          <div className="flex h-full flex-col justify-between">
            <div>
              <span
                className="absolute top-4 block cursor-pointer text-zinc-200 dark:text-white/40 xl:hidden"
                onClick={() => props.setOpen(false)}
              >
                <HiX />
              </span>
              <div className={`mt-8 flex items-center justify-center`}>
                <div className="me-2 flex h-[40px] w-[40px] items-center justify-center rounded-md bg-blue-600 text-white">
                  <HiSparkles className="h-5 w-5" />
                </div>
                <h5 className="me-2 text-2xl font-bold leading-5 text-zinc-950 dark:text-white">
                  Tawiza
                </h5>
                <Badge
                  variant="outline"
                  className="my-auto w-max px-2 py-0.5 text-xs text-zinc-950 dark:border-none dark:bg-zinc-800 dark:text-white"
                >
                  TAJINE
                </Badge>
              </div>
              <div className="mb-8 mt-8 h-px bg-zinc-200 dark:bg-white/10" />
              {/* Nav item */}
              <ul>
                <Links routes={routes} />
              </ul>
            </div>
            {/* Info Card */}
            <div className="mb-9 mt-7">
              <div className="flex justify-center">
                <SidebarCard />
              </div>
            </div>
          </div>
        </Scrollbars>
      </Card>
    </div>
  );
}

export default Sidebar;
