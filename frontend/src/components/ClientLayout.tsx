'use client';

import React from 'react';
import SideNavBar from './SideNavBar';
import TopAppBar from './TopAppBar';
import CommandPalette from './CommandPalette';
import { useHotkeys } from '../hooks/useHotkeys';
import { useNavigationStore } from '../store/navigationStore';

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  useHotkeys();
  const { activeTab } = useNavigationStore();

  return (
    <div className="bg-[#0a0a0b] text-[#e5e2e3] font-body-md antialiased min-h-screen flex selection:bg-[#353436] selection:text-[#10b981]">
      <SideNavBar />
      <div className="flex-1 ml-[240px] flex flex-col h-screen overflow-hidden">
        <TopAppBar />
        <div className="flex-1 overflow-y-auto bg-[#0a0a0b] p-8">
          {children}
        </div>
      </div>
      <CommandPalette />
    </div>
  );
}
