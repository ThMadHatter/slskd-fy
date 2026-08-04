'use client';

import React, { useState, useEffect } from 'react';
import { useNavigationStore, TabType } from '../store/navigationStore';
import { useDownloadStore } from '../store/downloadStore';
import { useAuthStore } from '../store/authStore';
import { Home, Compass, Search, Download, Settings, X, Disc, User } from 'lucide-react';

export default function MobileNavDrawer() {
  const { activeTab, setActiveTab, mobileMenuOpen, setMobileMenuOpen } = useNavigationStore();
  const { queue } = useDownloadStore();
  const { user } = useAuthStore();

  const activeDownloads = queue.filter((dl) => dl.status === 'downloading').length;

  const [buildInfo, setBuildInfo] = useState({
    version: '0.4.7',
    git_commit: 'unknown',
  });

  useEffect(() => {
    fetch('/api/version')
      .then((res) => {
        if (res.ok) return res.json();
        throw new Error();
      })
      .then((data) => {
        setBuildInfo({
          version: data.version || '0.4.7',
          git_commit: data.git_commit || 'unknown',
        });
      })
      .catch(() => {});
  }, []);

  const navItems = [
    { id: 'home', label: 'Home', icon: Home },
    { id: 'explore', label: 'Explore', icon: Compass },
    { id: 'search', label: 'Search', icon: Search },
    { id: 'downloads', label: 'Downloads', icon: Download },
    { id: 'settings', label: 'Settings', icon: Settings },
  ] as const;

  if (!mobileMenuOpen) return null;

  return (
    <>
      {/* Navigation Drawer Overlay */}
      <div
        className="fixed inset-0 bg-black/60 z-[60] backdrop-blur-sm transition-opacity duration-300 opacity-100 md:hidden"
        id="drawer-overlay"
        onClick={() => setMobileMenuOpen(false)}
      ></div>

      {/* Navigation Drawer */}
      <aside
        className="fixed top-0 left-0 bottom-0 w-[280px] bg-[#131314] border-r border-[#27272a] z-[70] transform transition-transform duration-300 ease-in-out flex flex-col translate-x-0 md:hidden"
        id="nav-drawer"
      >
        {/* Header inside drawer */}
        <div className="h-16 px-4 flex items-center justify-between border-b border-[#27272a] shrink-0">
          <div className="flex items-center gap-2">
            <Disc className="text-[#10b981] animate-[spin_8s_linear_infinite] shrink-0" size={20} />
            <span className="font-headline-sm text-headline-sm font-bold text-[#e5e2e3] uppercase tracking-tighter">
              Sonic Archive
            </span>
          </div>
          <button
            className="text-[#bbcabf] hover:text-[#10b981] transition-colors p-2"
            onClick={() => setMobileMenuOpen(false)}
          >
            <X size={20} />
          </button>
        </div>

        {/* Scrollable navigation area */}
        <div className="flex-1 overflow-y-auto py-4">
          <div className="px-4 mb-6">
            <div className="font-data-mono text-[10px] text-[#bbcabf] uppercase tracking-widest mb-2 border-b border-[#27272a] pb-1">
              Navigation
            </div>
            <ul className="space-y-1">
              {navItems.map((item) => {
                const isActive = activeTab === item.id;
                const Icon = item.icon;
                return (
                  <li key={item.id}>
                    <button
                      onClick={() => {
                        setActiveTab(item.id);
                        setMobileMenuOpen(false);
                      }}
                      className={`w-full flex items-center gap-4 px-3 py-3 rounded text-left transition-colors font-headline-sm uppercase tracking-wide border-l-2 ${
                        isActive
                          ? 'bg-[#10b981]/10 text-[#10b981] border-[#10b981]'
                          : 'text-[#e5e2e3] border-transparent hover:bg-[#201f20]'
                      }`}
                    >
                      <Icon size={18} className={isActive ? 'text-[#10b981]' : 'text-[#bbcabf]'} />
                      <span className="text-sm tracking-wider font-semibold">{item.label}</span>
                      {item.id === 'downloads' && activeDownloads > 0 && (
                        <span className="ml-auto bg-[#10b981] text-[#003824] font-data-mono text-[10px] px-1.5 py-0.5 font-bold">
                          {activeDownloads}
                        </span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>

          {/* System Telemetry Section */}
          <div className="px-4">
            <div className="font-data-mono text-[10px] text-[#bbcabf] uppercase tracking-widest mb-2 border-b border-[#27272a] pb-1">
              System
            </div>
            <div className="bg-[#201f20] border border-[#27272a] p-3 font-data-mono text-data-mono text-[#bbcabf] flex flex-col gap-1.5">
              <div className="flex justify-between items-center">
                <span>NODE_STATUS:</span>
                <span className="text-[#10b981] font-bold flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 bg-[#10b981] inline-block animate-pulse"></span>
                  ONLINE
                </span>
              </div>
              <div className="flex justify-between">
                <span>VERSION:</span>
                <span>v{buildInfo.version}</span>
              </div>
              <div className="flex justify-between">
                <span>DB_SYNC:</span>
                <span className="text-[#10b981]">OK</span>
              </div>
            </div>
          </div>
        </div>

        {/* User Profile Footer */}
        <div className="p-4 border-t border-[#27272a] shrink-0 bg-[#0e0e0f]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-[#201f20] border border-[#27272a] flex items-center justify-center text-[#bbcabf] overflow-hidden shrink-0">
              <User size={16} />
            </div>
            <div className="flex flex-col min-w-0">
              <span className="font-headline-sm text-sm uppercase truncate text-[#e5e2e3]">
                {user?.username || 'Anon User'}
              </span>
              <span className="font-data-mono text-[10px] text-[#bbcabf] opacity-75">
                Connected
              </span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
