'use client';

import React, { useState, useEffect } from 'react';
import { useNavigationStore, TabType } from '../store/navigationStore';
import { useDownloadStore } from '../store/downloadStore';
import { Home, Compass, Search, Download, Settings, User, RefreshCw, Disc } from 'lucide-react';

export default function SideNavBar() {
  const { activeTab, setActiveTab } = useNavigationStore();
  const { queue } = useDownloadStore();

  const activeDownloads = queue.filter((dl) => dl.status === 'downloading').length;

  const [buildInfo, setBuildInfo] = useState({
    version: '0.4.7',
    git_commit: 'unknown',
    build_date: 'unknown',
    api_version: '2.0.0',
    slskd_version: '0.17.x',
    beets_version: '1.6.0',
  });
  const [showBuildInfo, setShowBuildInfo] = useState(false);

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
          build_date: data.build_date || 'unknown',
          api_version: data.api_version || '2.0.0',
          slskd_version: data.slskd_version || '0.17.x',
          beets_version: data.beets_version || '1.6.0',
        });
      })
      .catch(() => {});
  }, []);

  const navItems = [
    { id: 'home', label: 'Home', icon: Home, hotkey: '⌘1', seq: 'G H' },
    { id: 'explore', label: 'Explore', icon: Compass, hotkey: '⌘2', seq: 'G E' },
    { id: 'search', label: 'Search', icon: Search, hotkey: '⌘3', seq: 'G S' },
    { id: 'downloads', label: 'Downloads', icon: Download, hotkey: '⌘4', seq: 'G D' },
    { id: 'settings', label: 'Settings', icon: Settings, hotkey: '⌘,', seq: 'G ,' },
  ] as const;

  return (
    <nav className="fixed left-0 top-0 h-full w-[240px] bg-[#0a0a0b] border-r border-[#27272a] flex flex-col py-8 z-50 shrink-0">
      <div className="px-6 mb-8 flex items-center gap-3">
        <Disc className="text-[#10b981] animate-[spin_8s_linear_infinite] shrink-0" size={24} />
        <div className="flex flex-col">
          <h1 className="font-headline-sm text-headline-sm font-bold tracking-tighter text-[#e5e2e3] uppercase leading-tight">
            Sonic Archive
          </h1>
          <span className="font-data-mono text-data-mono text-[#bbcabf] opacity-75 mt-1 leading-none">
            Technical Audiophile V1
          </span>
        </div>
      </div>

      <ul className="flex-1 flex flex-col gap-1 px-4 mt-4">
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          const Icon = item.icon;
          return (
            <li key={item.id}>
              <button
                onClick={() => setActiveTab(item.id)}
                className={`w-full text-left font-label-caps text-label-caps px-4 py-3 flex items-center justify-between cursor-pointer border-r-2 transition-all duration-150 focus-visible:outline-none ${
                  isActive
                    ? 'text-[#10b981] border-[#10b981] bg-[#201f20]'
                    : 'text-[#bbcabf] border-transparent hover:text-[#e5e2e3] hover:bg-[#1c1b1c]'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon size={18} className={isActive ? 'text-[#10b981]' : ''} />
                  <span>{item.label}</span>
                </div>
                <span className={`font-data-mono text-[10px] border px-1.5 py-0.5 rounded-none leading-none select-none ${
                  isActive
                    ? 'bg-[#131314] border-[#10b981]/30 text-[#10b981]'
                    : 'bg-[#131314] border-[#27272a] text-[#bbcabf]/50'
                }`}>
                  {item.hotkey}
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      <div className="px-6 mt-auto flex flex-col gap-4">
        <div className="border border-[#27272a] p-3 text-center bg-[#131314]">
          <span className="font-data-mono text-data-mono text-[#bbcabf] flex items-center justify-center gap-2 mb-2">
            <span className="w-1.5 h-1.5 bg-[#10b981] inline-block animate-pulse"></span>
            slskd connected
          </span>
          <span className="font-data-mono text-data-mono text-[#e5e2e3] font-medium block">
            Active DL: {activeDownloads}
          </span>
          {activeDownloads > 0 && (
            <div className="w-full bg-[#201f20] h-1 mt-2.5 overflow-hidden border border-[#27272a]">
              <div className="bg-[#10b981] h-full w-[75%] animate-pulse"></div>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-1 border-t border-[#27272a] pt-4">
          <button className="text-[#bbcabf] hover:text-[#e5e2e3] py-2 flex items-center justify-between font-label-caps text-label-caps text-left w-full transition-colors cursor-pointer">
            <div className="flex items-center gap-3">
              <User size={16} />
              <span>Profile</span>
            </div>
            <span className="font-data-mono text-[10px] text-[#bbcabf]/40">G P</span>
          </button>
          <button className="text-[#bbcabf] hover:text-[#e5e2e3] py-2 flex items-center justify-between font-label-caps text-label-caps text-left w-full transition-colors cursor-pointer">
            <div className="flex items-center gap-3">
              <RefreshCw size={16} />
              <span>Status</span>
            </div>
            <span className="font-data-mono text-[10px] text-[#bbcabf]/40">G T</span>
          </button>
        </div>

        <div className="border-t border-[#27272a] pt-4 flex flex-col items-center">
          <button
            onClick={() => setShowBuildInfo(true)}
            className="text-[10px] font-data-mono text-data-mono text-[#bbcabf]/50 hover:text-[#10b981] transition-colors cursor-pointer text-center select-none focus:outline-none"
          >
            v{buildInfo.version} ({buildInfo.git_commit})
          </button>
        </div>
      </div>

      {showBuildInfo && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/80 backdrop-blur-sm"
            onClick={() => setShowBuildInfo(false)}
          ></div>
          <div className="relative w-full max-w-sm bg-[#131314] border border-[#27272a] p-6 shadow-2xl flex flex-col gap-4 text-left">
            <h3 className="font-label-caps text-label-caps text-[#e5e2e3] font-bold border-b border-[#27272a] pb-2 uppercase tracking-wider">
              Build Verification Heuristics
            </h3>
            <div className="flex flex-col gap-2 font-data-mono text-data-mono text-xs text-[#bbcabf]">
              <div className="flex justify-between border-b border-[#27272a]/40 pb-1">
                <span>Application Version</span>
                <span className="text-[#10b981] font-bold">{buildInfo.version}</span>
              </div>
              <div className="flex justify-between border-b border-[#27272a]/40 pb-1">
                <span>Git Commit</span>
                <span className="text-[#e5e2e3]">{buildInfo.git_commit}</span>
              </div>
              <div className="flex justify-between border-b border-[#27272a]/40 pb-1">
                <span>Build Timestamp</span>
                <span className="text-[#e5e2e3] text-right">{buildInfo.build_date}</span>
              </div>
              <div className="flex justify-between border-b border-[#27272a]/40 pb-1">
                <span>Backend API Version</span>
                <span className="text-[#e5e2e3]">{buildInfo.api_version}</span>
              </div>
              <div className="flex justify-between border-b border-[#27272a]/40 pb-1">
                <span>slskd version</span>
                <span className="text-[#e5e2e3]">{buildInfo.slskd_version}</span>
              </div>
              <div className="flex justify-between border-b border-[#27272a]/40 pb-1">
                <span>Beets version</span>
                <span className="text-[#e5e2e3]">{buildInfo.beets_version}</span>
              </div>
            </div>
            <button
              onClick={() => setShowBuildInfo(false)}
              className="mt-2 w-full border border-[#27272a] py-2 bg-[#1c1b1c] text-[#bbcabf] hover:text-[#e5e2e3] hover:border-[#10b981] font-label-caps text-label-caps text-xs tracking-widest cursor-pointer text-center transition-colors"
            >
              CLOSE VERIFICATION
            </button>
          </div>
        </div>
      )}
    </nav>
  );
}
