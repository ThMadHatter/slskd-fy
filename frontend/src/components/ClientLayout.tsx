'use client';

import React, { useEffect } from 'react';
import SideNavBar from './SideNavBar';
import TopAppBar from './TopAppBar';
import CommandPalette from './CommandPalette';
import { useHotkeys } from '../hooks/useHotkeys';
import { useNavigationStore } from '../store/navigationStore';
import { useAuthStore } from '../store/authStore';
import LoginView from './LoginView';
import { Loader2 } from 'lucide-react';

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  const { user, checking, checkAuth } = useAuthStore();

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useHotkeys();
  const { activeTab } = useNavigationStore();

  if (checking) {
    return (
      <div className="bg-[#0a0a0b] text-[#e5e2e3] font-body-md antialiased min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-2">
          <Loader2 size={32} className="animate-spin text-[#10b981]" />
          <span className="text-xs uppercase tracking-wider text-[#bbcabf] font-data-mono">
            Loading Sonic Archive...
          </span>
        </div>
      </div>
    );
  }

  if (!user) {
    return <LoginView />;
  }

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
