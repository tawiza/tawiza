import { createContext } from 'react';

interface OpenContextType {
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

interface SidebarContextType {
  isCollapsed: boolean;
  setIsCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
}

export const OpenContext = createContext<OpenContextType | undefined>(undefined);
export const SidebarContext = createContext<SidebarContextType | undefined>(undefined);
