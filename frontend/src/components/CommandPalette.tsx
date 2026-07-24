'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useNavigationStore, TabType } from '../store/navigationStore';
import { useDownloadStore } from '../store/downloadStore';
import { Search, Compass, Download, Settings, History, HelpCircle } from 'lucide-react';

interface CommandItem {
  id: string;
  title: string;
  description?: string;
  hotkey?: string;
  icon: React.ComponentType<any>;
  action: () => void;
}

export default function CommandPalette() {
  const { commandPaletteOpen, setCommandPaletteOpen, setActiveTab } = useNavigationStore();
  const { pauseAll, resumeAll, clearCompleted } = useDownloadStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commandItems: CommandItem[] = [
    {
      id: 'nav-home',
      title: 'Go to Home',
      description: 'Navigate to search home',
      hotkey: '⌘1',
      icon: Search,
      action: () => setActiveTab('home'),
    },
    {
      id: 'nav-explore',
      title: 'Go to Explore',
      description: 'Explore trending network additions',
      hotkey: '⌘2',
      icon: Compass,
      action: () => setActiveTab('explore'),
    },
    {
      id: 'nav-downloads',
      title: 'Go to Downloads',
      description: 'Manage current transfer queues',
      hotkey: '⌘4',
      icon: Download,
      action: () => setActiveTab('downloads'),
    },
    {
      id: 'nav-settings',
      title: 'Go to Settings',
      description: 'Configure network services and thresholds',
      hotkey: '⌘,',
      icon: Settings,
      action: () => setActiveTab('settings'),
    },
    {
      id: 'cmd-pause-all',
      title: 'Pause All Downloads',
      description: 'Set all active transfers to pending state',
      hotkey: '⇧P',
      icon: Download,
      action: () => pauseAll(),
    },
    {
      id: 'cmd-resume-all',
      title: 'Resume All Downloads',
      description: 'Start all pending transfers',
      hotkey: '⇧R',
      icon: Download,
      action: () => resumeAll(),
    },
    {
      id: 'cmd-clear-completed',
      title: 'Clear Completed Downloads',
      description: 'Purge all successful items from queue',
      hotkey: '⇧⌘⌫',
      icon: History,
      action: () => clearCompleted(),
    },
  ];

  const filteredItems = commandItems.filter((item) =>
    item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (item.description && item.description.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  useEffect(() => {
    if (commandPaletteOpen) {
      setSearchQuery('');
      setSelectedIndex(0);
      setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
    }
  }, [commandPaletteOpen]);

  useEffect(() => {
    if (!commandPaletteOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % Math.max(1, filteredItems.length));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + filteredItems.length) % Math.max(1, filteredItems.length));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (filteredItems[selectedIndex]) {
          filteredItems[selectedIndex].action();
          setCommandPaletteOpen(false);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [commandPaletteOpen, filteredItems, selectedIndex, setCommandPaletteOpen]);

  if (!commandPaletteOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh] px-4">
      <div
        className="absolute inset-0 bg-[#0a0a0b]/80 backdrop-blur-sm"
        onClick={() => setCommandPaletteOpen(false)}
      ></div>

      <div className="relative w-full max-w-2xl bg-[#131314] border border-[#27272a] shadow-2xl flex flex-col overflow-hidden animate-fade-in-up">
        <div className="flex items-center px-4 py-4 border-b border-[#27272a] bg-[#1c1b1c]">
          <Search className="text-[#10b981] mr-3 shrink-0" size={20} />
          <input
            ref={inputRef}
            type="text"
            className="flex-1 bg-transparent border-none text-[#e5e2e3] font-body-lg focus:outline-none focus:ring-0 p-0 placeholder:text-[#bbcabf]/50 text-lg"
            placeholder="Type a command or navigate..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setSelectedIndex(0);
            }}
          />
          <button
            onClick={() => setCommandPaletteOpen(false)}
            className="font-data-mono text-[10px] text-[#bbcabf]/70 border border-[#27272a] px-1.5 py-0.5 select-none hover:text-[#e5e2e3] hover:border-[#10b981] cursor-pointer"
          >
            ESC
          </button>
        </div>

        <div className="max-h-[50vh] overflow-y-auto py-2">
          {filteredItems.length === 0 ? (
            <div className="px-6 py-12 text-center text-[#bbcabf] font-body-md flex flex-col items-center gap-2">
              <HelpCircle size={24} className="text-[#bbcabf]/50" />
              <span>No matching command found. Try searching for "go to" or "downloads".</span>
            </div>
          ) : (
            <div className="px-2 py-1.5">
              <span className="font-label-caps text-label-caps text-[#bbcabf] px-3 py-2 block text-xs tracking-widest opacity-80 uppercase select-none">
                Sonic Archive Commands
              </span>
              <ul className="flex flex-col gap-0.5">
                {filteredItems.map((item, index) => {
                  const isSelected = index === selectedIndex;
                  const Icon = item.icon;
                  return (
                    <li key={item.id}>
                      <button
                        onClick={() => {
                          item.action();
                          setCommandPaletteOpen(false);
                        }}
                        className={`w-full flex items-center px-3 py-3 text-left transition-colors cursor-pointer border-l-2 focus:outline-none ${
                          isSelected
                            ? 'bg-[#1c1b1c] border-[#10b981] text-[#10b981]'
                            : 'bg-transparent border-transparent text-[#bbcabf] hover:bg-[#1c1b1c] hover:text-[#e5e2e3]'
                        }`}
                      >
                        <Icon size={18} className="mr-4 shrink-0" />
                        <div className="flex-1 flex flex-col">
                          <span className="font-body-md font-semibold">{item.title}</span>
                          {item.description && (
                            <span className="text-xs text-[#bbcabf]/65 font-light">{item.description}</span>
                          )}
                        </div>
                        {item.hotkey && (
                          <span className={`font-data-mono text-[10px] border px-1.5 py-0.5 rounded-none ${
                            isSelected
                              ? 'bg-[#131314] border-[#10b981]/40 text-[#10b981]'
                              : 'bg-[#1c1b1c] border-[#27272a] text-[#bbcabf]/50'
                          }`}>
                            {item.hotkey}
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>

        <div className="px-4 py-3 border-t border-[#27272a] bg-[#0e0e0f] flex items-center gap-4 text-[#bbcabf]/60 font-data-mono text-[11px] select-none">
          <div className="flex items-center gap-1.5">
            <span className="bg-[#1c1b1c] border border-[#27272a] px-1 py-0.5">↑</span>
            <span className="bg-[#1c1b1c] border border-[#27272a] px-1 py-0.5">↓</span>
            <span>Navigate</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="bg-[#1c1b1c] border border-[#27272a] px-1.5 py-0.5 font-bold">↵</span>
            <span>Select</span>
          </div>
        </div>
      </div>
    </div>
  );
}
