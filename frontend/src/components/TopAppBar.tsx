'use client';

import React from 'react';
import { useNavigationStore } from '../store/navigationStore';
import { useSearchStore } from '../store/searchStore';
import { Search, Filter, Sliders, Settings2 } from 'lucide-react';

export default function TopAppBar() {
  const { toggleCommandPalette } = useNavigationStore();
  const { artist, track } = useSearchStore();

  const searchQueryDisplay = artist && track
    ? `${artist} - ${track}`
    : artist || track || '';

  return (
    <header className="bg-[#131314] border-b border-[#27272a] flex items-center justify-between h-16 px-8 w-full sticky top-0 z-40 shrink-0 select-none">
      <div className="flex items-center gap-4 flex-1">
        {/* Subtle Command Palette Input Trigger */}
        <div className="relative flex items-center w-full max-w-md">
          <Search size={16} className="absolute left-3 text-[#bbcabf]" />
          <button
            onClick={toggleCommandPalette}
            className="w-full bg-[#1c1b1c] border border-[#27272a] text-[#e5e2e3] font-body-md text-body-md text-left pl-10 pr-16 py-2 cursor-pointer transition-colors hover:border-[#10b981] focus:outline-none flex items-center justify-between"
          >
            <span className="text-[#bbcabf] truncate">
              {searchQueryDisplay ? `Search results for "${searchQueryDisplay}"...` : 'Search archive or run command...'}
            </span>
            <div className="flex items-center gap-0.5 opacity-60">
              <span className="font-data-mono text-[10px] text-[#bbcabf] bg-[#131314] border border-[#27272a] px-1 py-0.5 leading-none">⌘</span>
              <span className="font-data-mono text-[10px] text-[#bbcabf] bg-[#131314] border border-[#27272a] px-1 py-0.5 leading-none">K</span>
            </div>
          </button>
        </div>

        {/* Sync Indicator */}
        <span className="text-[#10b981] font-label-caps text-label-caps flex items-center gap-2 select-none">
          <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] inline-block animate-pulse"></span>
          Last.fm Sync Active
        </span>
      </div>

      {/* Trailing Icon Actions */}
      <div className="flex items-center gap-4 text-[#bbcabf]">
        <button className="hover:text-[#10b981] transition-colors cursor-pointer relative group flex items-center justify-center p-1">
          <Filter size={18} />
          <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-[#201f20] border border-[#27272a] px-1.5 py-0.5 font-data-mono text-[10px] text-[#e5e2e3] whitespace-nowrap pointer-events-none z-50">
            F
          </div>
        </button>
        <button className="hover:text-[#10b981] transition-colors cursor-pointer relative group flex items-center justify-center p-1">
          <Sliders size={18} />
          <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-[#201f20] border border-[#27272a] px-1.5 py-0.5 font-data-mono text-[10px] text-[#e5e2e3] whitespace-nowrap pointer-events-none z-50">
            T
          </div>
        </button>
        <button className="hover:text-[#10b981] transition-colors cursor-pointer relative group flex items-center justify-center p-1">
          <Settings2 size={18} />
          <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-[#201f20] border border-[#27272a] px-1.5 py-0.5 font-data-mono text-[10px] text-[#e5e2e3] whitespace-nowrap pointer-events-none z-50">
            C
          </div>
        </button>
      </div>
    </header>
  );
}
