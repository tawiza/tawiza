import { IRoute } from '@/types/types';
import {
  HiOutlineHome,
  HiOutlineChatBubbleLeftRight,
  HiOutlineMapPin,
  HiOutlineChartBar,
  HiOutlineCog8Tooth,
  HiOutlineGlobeAlt,
  HiOutlineGlobeEuropeAfrica,
  HiOutlineShieldCheck,
  HiOutlineAcademicCap,
  HiOutlineBugAnt,
  HiOutlineSparkles,
  HiOutlineCpuChip,
} from 'react-icons/hi2';

export const routes: IRoute[] = [
  {
    name: 'Dashboard',
    path: '/dashboard/main',
    icon: <HiOutlineHome className="-mt-[7px] h-4 w-4 stroke-2 text-inherit" />,
    collapse: false
  },
  {
    name: '✨ Intelligence Hub',
    path: '/dashboard/intelligence',
    icon: <HiOutlineSparkles className="-mt-[7px] h-4 w-4 stroke-2 text-inherit" />,
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
    name: 'TAJINE Chat',
    path: '/dashboard/ai-chat',
    icon: (
      <HiOutlineChatBubbleLeftRight className="-mt-[7px] h-4 w-4 stroke-2 text-inherit" />
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
    name: 'Analyses',
    path: '/dashboard/analytics',
    icon: (
      <HiOutlineChartBar className="-mt-[7px] h-4 w-4 stroke-2 text-inherit" />
    ),
    collapse: false
  },
  {
    name: 'Sources de Donnees',
    path: '/dashboard/data-sources',
    icon: (
      <HiOutlineGlobeAlt className="-mt-[7px] h-4 w-4 stroke-2 text-inherit" />
    ),
    collapse: false
  },
  {
    name: 'Investigation',
    path: '/dashboard/investigation',
    icon: (
      <HiOutlineShieldCheck className="-mt-[7px] h-4 w-4 stroke-2 text-inherit" />
    ),
    collapse: false
  },
  {
    name: 'Predictions',
    path: '/dashboard/predictions',
    icon: (
      <HiOutlineCpuChip className="-mt-[7px] h-4 w-4 stroke-2 text-inherit" />
    ),
    collapse: false
  },
  {
    name: 'Fine-Tuning',
    path: '/dashboard/fine-tuning',
    icon: (
      <HiOutlineAcademicCap className="-mt-[7px] h-4 w-4 stroke-2 text-inherit" />
    ),
    collapse: false
  },
  {
    name: 'Crawler',
    path: '/dashboard/settings/crawler',
    icon: (
      <HiOutlineBugAnt className="-mt-[7px] h-4 w-4 stroke-2 text-inherit" />
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
