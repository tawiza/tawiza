import { IRoute } from '@/types/types';
import {
  HiOutlineHome,
  HiOutlineChatBubbleLeftRight,
  HiOutlineMapPin,
  HiOutlineChartBar,
  HiOutlineCog8Tooth,
  HiOutlineGlobeAlt,
  HiOutlineGlobeEuropeAfrica,
} from 'react-icons/hi2';

export const routes: IRoute[] = [
  {
    name: 'Dashboard',
    path: '/dashboard/main',
    icon: <HiOutlineHome className="-mt-[7px] h-4 w-4 stroke-2 text-inherit" />,
    collapse: false
  },
  {
    name: 'TAJINE',
    path: '/dashboard/tajine',
    icon: (
      <HiOutlineGlobeEuropeAfrica className="-mt-[7px] h-4 w-4 stroke-2 text-inherit" />
    ),
    collapse: false
  },
  {
    name: 'Chat',
    path: '/dashboard/ai-chat',
    icon: (
      <HiOutlineChatBubbleLeftRight className="-mt-[7px] h-4 w-4 stroke-2 text-inherit" />
    ),
    collapse: false
  },
  {
    name: 'Analytics',
    path: '/dashboard/analytics',
    icon: (
      <HiOutlineChartBar className="-mt-[7px] h-4 w-4 stroke-2 text-inherit" />
    ),
    collapse: false
  },
  {
    name: 'Departements',
    path: '/dashboard/departments',
    icon: (
      <HiOutlineMapPin className="-mt-[7px] h-4 w-4 stroke-2 text-inherit" />
    ),
    collapse: false
  },
  {
    name: 'Sources',
    path: '/dashboard/data-sources',
    icon: (
      <HiOutlineGlobeAlt className="-mt-[7px] h-4 w-4 stroke-2 text-inherit" />
    ),
    collapse: false
  },
  {
    name: 'Configuration',
    path: '/dashboard/settings',
    icon: (
      <HiOutlineCog8Tooth className="-mt-[7px] h-4 w-4 stroke-2 text-inherit" />
    ),
    collapse: false
  }
];
