'use client';

import React, { useState } from 'react';
import { useSettingsStore } from '../store/settingsStore';
import { Settings, Save, Server, Sliders, Cloud, CheckSquare, Info } from 'lucide-react';
import Button from './ui/Button';
import Input from './ui/Input';

export default function SettingsView() {
  const {
    slskdUrl,
    slskdKey,
    navidromeUrl,
    navidromeUser,
    navidromePass,
    lastfmKey,
    lastfmSecret,
    beetsPath,
    minScoreThreshold,
    updateSettings,
  } = useSettingsStore();

  const [formState, setFormState] = useState({
    slskdUrl,
    slskdKey,
    navidromeUrl,
    navidromeUser,
    navidromePass,
    lastfmKey,
    lastfmSecret,
    beetsPath,
    minScoreThreshold,
  });

  const [isSaved, setIsSaved] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    updateSettings(formState);
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 2000);
  };

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col gap-8 animate-fade-in-up mt-4 select-none">

      {/* Title Header */}
      <div>
        <h2 className="font-headline-md text-headline-md font-bold text-[#e5e2e3]">
          System Configurations
        </h2>
        <p className="font-data-mono text-data-mono text-[#bbcabf] opacity-75 mt-1">
          Precision tuning parameters for Sonic Archive services
        </p>
      </div>

      {isSaved && (
        <div className="bg-[#131314] border border-[#10b981] p-4 text-[#10b981] font-semibold text-sm flex items-center gap-3">
          <Info size={16} />
          <span>Configuration settings saved successfully!</span>
        </div>
      )}

      {/* Main Settings Form */}
      <form onSubmit={handleSave} className="bg-[#131314] border border-[#27272a] divide-y divide-[#27272a] rounded-none">

        {/* Section: slskd */}
        <div className="p-6 flex flex-col gap-4">
          <h3 className="font-label-caps text-label-caps text-[#e5e2e3] font-bold flex items-center gap-2 select-none uppercase tracking-widest border-b border-[#27272a] pb-2">
            <Server size={14} className="text-[#10b981]" />
            slskd Daemon config
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block font-label-caps text-[10px] text-[#bbcabf] mb-1.5 uppercase">API Endpoint URL</label>
              <Input
                type="text"
                value={formState.slskdUrl}
                onChange={(e) => setFormState({ ...formState, slskdUrl: e.target.value })}
              />
            </div>
            <div>
              <label className="block font-label-caps text-[10px] text-[#bbcabf] mb-1.5 uppercase">REST API Key</label>
              <Input
                type="password"
                value={formState.slskdKey}
                onChange={(e) => setFormState({ ...formState, slskdKey: e.target.value })}
              />
            </div>
          </div>
        </div>

        {/* Section: Navidrome */}
        <div className="p-6 flex flex-col gap-4">
          <h3 className="font-label-caps text-label-caps text-[#e5e2e3] font-bold flex items-center gap-2 select-none uppercase tracking-widest border-b border-[#27272a] pb-2">
            <Server size={14} className="text-[#10b981]" />
            Navidrome Subsonic Integration
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-3">
              <label className="block font-label-caps text-[10px] text-[#bbcabf] mb-1.5 uppercase">Server Web URL</label>
              <Input
                type="text"
                value={formState.navidromeUrl}
                onChange={(e) => setFormState({ ...formState, navidromeUrl: e.target.value })}
              />
            </div>
            <div>
              <label className="block font-label-caps text-[10px] text-[#bbcabf] mb-1.5 uppercase">Admin Username</label>
              <Input
                type="text"
                value={formState.navidromeUser}
                onChange={(e) => setFormState({ ...formState, navidromeUser: e.target.value })}
              />
            </div>
            <div className="md:col-span-2">
              <label className="block font-label-caps text-[10px] text-[#bbcabf] mb-1.5 uppercase">Subsonic Token Password</label>
              <Input
                type="password"
                value={formState.navidromePass}
                onChange={(e) => setFormState({ ...formState, navidromePass: e.target.value })}
              />
            </div>
          </div>
        </div>

        {/* Section: Last.fm */}
        <div className="p-6 flex flex-col gap-4">
          <h3 className="font-label-caps text-label-caps text-[#e5e2e3] font-bold flex items-center gap-2 select-none uppercase tracking-widest border-b border-[#27272a] pb-2">
            <Cloud size={14} className="text-[#10b981]" />
            Last.fm Recommendation sync
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block font-label-caps text-[10px] text-[#bbcabf] mb-1.5 uppercase">API Key</label>
              <Input
                type="text"
                value={formState.lastfmKey}
                onChange={(e) => setFormState({ ...formState, lastfmKey: e.target.value })}
              />
            </div>
            <div>
              <label className="block font-label-caps text-[10px] text-[#bbcabf] mb-1.5 uppercase">API Shared Secret</label>
              <Input
                type="password"
                value={formState.lastfmSecret}
                onChange={(e) => setFormState({ ...formState, lastfmSecret: e.target.value })}
              />
            </div>
          </div>
        </div>

        {/* Section: Beets & Monitoring */}
        <div className="p-6 flex flex-col gap-4">
          <h3 className="font-label-caps text-label-caps text-[#e5e2e3] font-bold flex items-center gap-2 select-none uppercase tracking-widest border-b border-[#27272a] pb-2">
            <Sliders size={14} className="text-[#10b981]" />
            Beets Library & Monitoring Rules
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-2">
              <label className="block font-label-caps text-[10px] text-[#bbcabf] mb-1.5 uppercase">Beets Music Library Path</label>
              <Input
                type="text"
                value={formState.beetsPath}
                onChange={(e) => setFormState({ ...formState, beetsPath: e.target.value })}
              />
            </div>
            <div>
              <label className="block font-label-caps text-[10px] text-[#bbcabf] mb-1.5 uppercase">Min Confidence Threshold</label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="50"
                  max="100"
                  step="5"
                  value={formState.minScoreThreshold}
                  onChange={(e) => setFormState({ ...formState, minScoreThreshold: parseInt(e.target.value) })}
                  className="w-full h-1 bg-[#0a0a0b] rounded-none appearance-none cursor-pointer accent-[#10b981] border border-[#27272a]"
                />
                <span className="font-data-mono text-data-mono text-[#10b981] font-bold select-none shrink-0 w-8 text-right">
                  {formState.minScoreThreshold}%
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Form Actions footer */}
        <div className="p-6 bg-[#1c1b1c] flex justify-end select-none">
          <Button type="submit" variant="primary">
            <Save size={14} />
            SAVE CONFIGURATIONS
          </Button>
        </div>
      </form>
    </div>
  );
}
