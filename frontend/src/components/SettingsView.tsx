'use client';

import React, { useState, useEffect } from 'react';
import { useSettingsStore } from '../store/settingsStore';
import { Server, Cloud, Info, Terminal, CheckCircle2, AlertTriangle, RefreshCw, Save, RotateCcw, ShieldCheck, Database, FileCode, Sliders, Layers, PlugZap, AlertOctagon, Radio } from 'lucide-react';
import Button from './ui/Button';
import Input from './ui/Input';
import SonicLoader from './ui/SonicLoader';

export default function SettingsView() {
  const {
    slskdUrl,
    slskdKey,
    searchTimeoutSec,
    waitUntilComplete,
    navidromeUrl,
    navidromeUser,
    navidromePass,
    lastfmKey,
    lastfmSecret,
    beetsPath,
    minScoreThreshold,
    updateSettings,
  } = useSettingsStore();

  const [activeSubMenu, setActiveSubMenu] = useState<'slskd' | 'beets' | 'integrations'>('beets');

  // General Settings Form State
  const [formState, setFormState] = useState({
    slskdUrl,
    slskdKey,
    searchTimeoutSec,
    waitUntilComplete,
    navidromeUrl,
    navidromeUser,
    navidromePass,
    lastfmKey,
    lastfmSecret,
    beetsPath,
    minScoreThreshold,
  });

  const [isSaved, setIsSaved] = useState(false);

  // Beets YAML Config Editor State
  const [yamlContent, setYamlContent] = useState<string>('');
  const [originalYaml, setOriginalYaml] = useState<string>('');
  const [yamlLoading, setYamlLoading] = useState<boolean>(false);
  const [yamlSaving, setYamlSaving] = useState<boolean>(false);
  const [yamlValidating, setYamlValidating] = useState<boolean>(false);
  const [yamlMessage, setYamlMessage] = useState<{ type: 'success' | 'error'; text: string; line?: number; column?: number } | null>(null);
  const [beetsRuntimeStatus, setBeetsRuntimeStatus] = useState<any>(null);
  const [showResetConfirm, setShowResetConfirm] = useState<boolean>(false);
  const [reloadingPlugins, setReloadingPlugins] = useState<boolean>(false);
  const [migratingDb, setMigratingDb] = useState<boolean>(false);
  const [pluginLogOutput, setPluginLogOutput] = useState<string | null>(null);

  const hasUnsavedYaml = yamlContent !== originalYaml;

  // Fetch Beets YAML configuration and engine status on mount or subtab change
  useEffect(() => {
    if (activeSubMenu === 'beets') {
      fetchBeetsConfig();
      fetchBeetsStatus();
    }
  }, [activeSubMenu]);

  const fetchBeetsConfig = async () => {
    setYamlLoading(true);
    setYamlMessage(null);
    try {
      const res = await fetch('/api/beets/config');
      if (res.ok) {
        const data = await res.json();
        setYamlContent(data.yaml_text || '');
        setOriginalYaml(data.yaml_text || '');
      } else {
        setYamlMessage({ type: 'error', text: 'Failed to retrieve Beets YAML configuration.' });
      }
    } catch (err: any) {
      setYamlMessage({ type: 'error', text: err.message || 'Error connecting to backend.' });
    } finally {
      setYamlLoading(false);
    }
  };

  const fetchBeetsStatus = async () => {
    try {
      const res = await fetch('/api/beets/status');
      if (res.ok) {
        const data = await res.json();
        setBeetsRuntimeStatus(data);
      }
    } catch (e) {
      console.error('Failed to fetch Beets engine status:', e);
    }
  };

  const handleForceReloadPlugins = async () => {
    setReloadingPlugins(true);
    setPluginLogOutput(null);
    try {
      const res = await fetch('/api/beets/plugins/reload', {
        method: 'POST',
      });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        setPluginLogOutput(data.logs || 'Plugins reloaded successfully.');
        setYamlMessage({
          type: 'success',
          text: `Forced Beets Plugin Reload Success! Loaded ${data.loaded_plugins?.length || 0} plugins into runtime memory.`,
        });
        fetchBeetsStatus();
      } else {
        setPluginLogOutput(data.logs || data.message || 'Error reloading plugins.');
        setYamlMessage({
          type: 'error',
          text: `Plugin Reload Failed: ${data.message || 'Error executing load sequence'}`,
        });
      }
    } catch (err: any) {
      setPluginLogOutput(err.message || 'Failed to connect to backend.');
      setYamlMessage({ type: 'error', text: err.message || 'Reload request failed.' });
    } finally {
      setReloadingPlugins(false);
    }
  };

  const handleValidateYaml = async () => {
    setYamlValidating(true);
    setYamlMessage(null);
    try {
      const res = await fetch('/api/beets/config/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ yaml_text: yamlContent }),
      });
      const data = await res.json();
      if (data.valid) {
        setYamlMessage({
          type: 'success',
          text: `YAML Syntax Valid! Configured plugins: ${(data.plugins || []).join(', ')}`,
        });
      } else {
        setYamlMessage({
          type: 'error',
          text: `Validation Error: ${data.error || 'Syntax error'}`,
          line: data.line,
          column: data.column,
        });
      }
    } catch (err: any) {
      setYamlMessage({ type: 'error', text: err.message || 'Validation request failed.' });
    } finally {
      setYamlValidating(false);
    }
  };

  const handleSaveYaml = async () => {
    setYamlSaving(true);
    setYamlMessage(null);
    try {
      const res = await fetch('/api/beets/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ yaml_text: yamlContent }),
      });
      const data = await res.json();
      if (res.ok && (data.status === 'success' || data.status === 'ok')) {
        setOriginalYaml(yamlContent);
        setYamlMessage({ type: 'success', text: 'Beets YAML configuration saved and applied atomically!' });
        fetchBeetsStatus();
      } else {
        setYamlMessage({
          type: 'error',
          text: `Save Failed: ${data.error || data.message || 'Failed to save configuration'}`,
          line: data.line,
          column: data.column,
        });
      }
    } catch (err: any) {
      setYamlMessage({ type: 'error', text: err.message || 'Save request failed.' });
    } finally {
      setYamlSaving(false);
    }
  };

  const handleResetYaml = () => {
    setYamlContent(originalYaml);
    setYamlMessage({ type: 'success', text: 'Reverted editor changes to last saved version.' });
  };

  const handleRestoreDefaultYaml = () => {
    const defaultYaml = `directory: /music
library: /config/beets/library.db
pluginpath: []
plugins: >
  fromfilename
  musicbrainz
  fetchart
  embedart
  scrub
  lastgenre
  chroma
  web
  duplicates
  info
  missing

import:
  write: yes
  copy: yes
  move: no
  link: no
  resume: yes
  incremental: yes
  incremental_skip_later: yes
  quiet: yes
  quiet_fallback: skip
  autotag: yes
  detail: yes

musicbrainz:
  searchlimit: 5

paths:
  default: $albumartist/$album%aformat{}/$track - $title
  singleton: Non-Album/$artist - $title
  comp: Compilations/$album%aformat{}/$track - $title
`;
    setYamlContent(defaultYaml);
    setShowResetConfirm(false);
    setYamlMessage({ type: 'success', text: 'Restored recommended Sonic Archive default YAML template.' });
  };

  const handleGeneralSave = (e: React.FormEvent) => {
    e.preventDefault();
    updateSettings(formState);
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 2000);
  };

  return (
    <div className="w-full max-w-5xl mx-auto flex flex-col gap-6 animate-fade-in-up mt-4 select-none pb-12">

      {/* Header Title */}
      <div>
        <h2 className="font-headline-md text-headline-md font-bold text-[#e5e2e3]">
          System Configurations
        </h2>
        <p className="font-data-mono text-data-mono text-[#bbcabf] opacity-75 mt-1">
          Precision tuning parameters and isolated Beets engine settings
        </p>
      </div>

      {/* Submenu Navigation Tabs */}
      <div className="flex border-b border-[#27272a] bg-[#131314]">
        <button
          type="button"
          onClick={() => setActiveSubMenu('beets')}
          className={`flex items-center gap-2 px-6 py-3 font-data-mono text-xs font-bold uppercase transition-all border-b-2 cursor-pointer ${
            activeSubMenu === 'beets'
              ? 'border-[#10b981] text-[#10b981] bg-[#1c1b1c]'
              : 'border-transparent text-[#bbcabf] hover:text-[#e5e2e3] hover:bg-[#1c1b1c]/50'
          }`}
        >
          <FileCode size={16} />
          BEETS ENGINE (YAML)
          {hasUnsavedYaml && (
            <span className="w-2 h-2 rounded-full bg-[#fc7c78] animate-pulse" title="Unsaved changes" />
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveSubMenu('slskd')}
          className={`flex items-center gap-2 px-6 py-3 font-data-mono text-xs font-bold uppercase transition-all border-b-2 cursor-pointer ${
            activeSubMenu === 'slskd'
              ? 'border-[#10b981] text-[#10b981] bg-[#1c1b1c]'
              : 'border-transparent text-[#bbcabf] hover:text-[#e5e2e3] hover:bg-[#1c1b1c]/50'
          }`}
        >
          <Server size={16} />
          SLSKD NETWORK
        </button>

        <button
          type="button"
          onClick={() => setActiveSubMenu('integrations')}
          className={`flex items-center gap-2 px-6 py-3 font-data-mono text-xs font-bold uppercase transition-all border-b-2 cursor-pointer ${
            activeSubMenu === 'integrations'
              ? 'border-[#10b981] text-[#10b981] bg-[#1c1b1c]'
              : 'border-transparent text-[#bbcabf] hover:text-[#e5e2e3] hover:bg-[#1c1b1c]/50'
          }`}
        >
          <Cloud size={16} />
          SERVICES & INTEGRATIONS
        </button>
      </div>

      {/* SUBMENU 1: BEETS ISOLATED YAML EDITOR */}
      {activeSubMenu === 'beets' && (
        <div className="flex flex-col gap-6">

          {/* Engine Info & Environment Paths Card */}
          <div className="bg-[#131314] border border-[#27272a] p-5 flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-[#27272a] pb-3">
              <div className="flex items-center gap-2">
                <Terminal size={18} className="text-[#10b981]" />
                <h3 className="font-label-caps text-xs text-[#e5e2e3] font-bold uppercase tracking-wider">
                  Beets Engine Runtime Diagnostics
                </h3>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={async () => {
                    setMigratingDb(true);
                    setPluginLogOutput(null);
                    try {
                      const res = await fetch('/api/beets/migrate-database', { method: 'POST' });
                      const data = await res.json();
                      if (res.ok) {
                        setPluginLogOutput(data.logs || 'Database migration completed.');
                        setYamlMessage({ type: 'success', text: 'Database Schema Migration & Verification Success!' });
                        fetchBeetsStatus();
                      } else {
                        setPluginLogOutput(data.logs || data.message || 'Error migrating database.');
                        setYamlMessage({ type: 'error', text: `Migration Failed: ${data.message || 'Unknown error'}` });
                      }
                    } catch (e: any) {
                      setPluginLogOutput(e.message || 'Failed to connect to backend.');
                      setYamlMessage({ type: 'error', text: 'Migration request failed.' });
                    } finally {
                      setMigratingDb(false);
                    }
                  }}
                  disabled={migratingDb}
                  className="text-xs font-data-mono bg-[#1c1b1c] hover:bg-[#10b981] text-[#10b981] hover:text-[#0a0a0b] border border-[#10b981]/40 px-2.5 py-1 font-bold flex items-center gap-1.5 transition-all cursor-pointer disabled:opacity-50 uppercase"
                >
                  {migratingDb ? <SonicLoader size="small" /> : <Database size={12} />}
                  MIGRATE / REPAIR DB SCHEMA
                </button>
                <button
                  onClick={handleForceReloadPlugins}
                  disabled={reloadingPlugins}
                  className="text-xs font-data-mono bg-[#1c1b1c] hover:bg-[#10b981] text-[#10b981] hover:text-[#0a0a0b] border border-[#10b981]/40 px-2.5 py-1 font-bold flex items-center gap-1.5 transition-all cursor-pointer disabled:opacity-50 uppercase"
                >
                  {reloadingPlugins ? <SonicLoader size="small" /> : <PlugZap size={12} />}
                  FORCE RELOAD PLUGINS
                </button>
                <button
                  onClick={fetchBeetsStatus}
                  className="text-xs font-data-mono text-[#bbcabf] hover:text-[#10b981] flex items-center gap-1 cursor-pointer"
                >
                  <RefreshCw size={12} /> RELOAD STATUS
                </button>
              </div>
            </div>

            {beetsRuntimeStatus ? (
              <div className="flex flex-col gap-4 font-data-mono text-xs">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-[#0a0a0b] p-3 border border-[#27272a]">
                    <span className="text-[#bbcabf]/60 block text-[10px] uppercase">CLI Version</span>
                    <span className="text-[#10b981] font-bold">
                      {beetsRuntimeStatus.beet_version || 'v2.14.1'}
                    </span>
                  </div>
                  <div className="bg-[#0a0a0b] p-3 border border-[#27272a]">
                    <span className="text-[#bbcabf]/60 block text-[10px] uppercase">Effective Config File</span>
                    <span className="text-[#e5e2e3] font-bold truncate block" title={beetsRuntimeStatus.config_path}>
                      {beetsRuntimeStatus.config_path || '/app/app/beets_config.yaml'}
                    </span>
                  </div>
                  <div className="bg-[#0a0a0b] p-3 border border-[#27272a]">
                    <span className="text-[#bbcabf]/60 block text-[10px] uppercase">Target Music Library</span>
                    <span className="text-[#e5e2e3] font-bold truncate block" title={beetsRuntimeStatus.library_db_path}>
                      {beetsRuntimeStatus.library_db_path || '/config/beets/library.db'}
                    </span>
                  </div>
                </div>

                {/* Plugin Execution Log Viewer Drawer */}
                {pluginLogOutput && (
                  <div className="bg-[#0a0a0b] border border-[#10b981]/40 p-3 flex flex-col gap-2 font-data-mono text-xs">
                    <div className="flex items-center justify-between border-b border-[#27272a] pb-1.5 text-[#10b981] font-bold">
                      <span className="flex items-center gap-1.5 uppercase text-[11px]">
                        <Terminal size={13} />
                        Plugin Load Execution Logs
                      </span>
                      <button
                        onClick={() => setPluginLogOutput(null)}
                        className="text-[10px] text-[#bbcabf] hover:text-[#e5e2e3] cursor-pointer"
                      >
                        CLOSE LOGS
                      </button>
                    </div>
                    <pre className="bg-[#131314] p-3 text-[11px] text-[#bbcabf] overflow-x-auto whitespace-pre-wrap max-h-48 border border-[#27272a] leading-relaxed">
                      {pluginLogOutput}
                    </pre>
                  </div>
                )}

                {/* Plugin Diagnostics Grid (Configured, Loaded, Failed, Metadata Sources) */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">

                  {/* Configured Plugins */}
                  <div className="bg-[#0a0a0b] p-3 border border-[#27272a] flex flex-col gap-2">
                    <span className="font-bold text-[11px] text-[#e5e2e3] flex items-center gap-1.5 uppercase">
                      <Layers size={13} className="text-[#bbcabf]" />
                      Configured Plugins ({beetsRuntimeStatus.configured_plugins?.length || 0})
                    </span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {beetsRuntimeStatus.configured_plugins?.map((p: string) => (
                        <span key={p} className="bg-[#1c1b1c] text-[#bbcabf] border border-[#27272a] text-[10px] px-1.5 py-0.5 font-bold">
                          {p}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Loaded Plugins */}
                  <div className="bg-[#0a0a0b] p-3 border border-[#27272a] flex flex-col gap-2">
                    <span className="font-bold text-[11px] text-[#10b981] flex items-center gap-1.5 uppercase">
                      <PlugZap size={13} />
                      Loaded Plugins ({beetsRuntimeStatus.loaded_plugins?.length || 0})
                    </span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {beetsRuntimeStatus.loaded_plugins?.map((p: string) => (
                        <span key={p} className="bg-[#10b981]/15 text-[#10b981] border border-[#10b981]/30 text-[10px] px-1.5 py-0.5 font-bold">
                          {p}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Failed Plugins */}
                  <div className="bg-[#0a0a0b] p-3 border border-[#27272a] flex flex-col gap-2">
                    <span className="font-bold text-[11px] text-[#fc7c78] flex items-center gap-1.5 uppercase">
                      <AlertOctagon size={13} />
                      Failed Plugins ({beetsRuntimeStatus.failed_plugins?.length || 0})
                    </span>
                    {beetsRuntimeStatus.failed_plugins?.length > 0 ? (
                      <div className="flex flex-col gap-1 mt-1 text-[10px]">
                        {beetsRuntimeStatus.failed_plugins.map((fp: any) => (
                          <div key={fp.name} className="text-[#fc7c78] bg-[#fc7c78]/10 p-1 border border-[#fc7c78]/20">
                            <strong>{fp.name}:</strong> {fp.reason}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <span className="text-[10px] text-[#bbcabf]/60 italic mt-1">None (All configured plugins loaded)</span>
                    )}
                  </div>

                  {/* Metadata Sources */}
                  <div className="bg-[#0a0a0b] p-3 border border-[#27272a] flex flex-col gap-2">
                    <span className="font-bold text-[11px] text-[#e5e2e3] flex items-center gap-1.5 uppercase">
                      <Radio size={13} className="text-[#10b981]" />
                      Metadata Sources
                    </span>
                    <div className="flex flex-col gap-1 mt-1 text-[10px]">
                      {beetsRuntimeStatus.metadata_sources?.map((src: any) => (
                        <div key={src.name} className="flex items-center justify-between">
                          <span className="text-[#e5e2e3]">{src.name}</span>
                          <span className={`px-1 py-0.2 font-bold ${src.active ? 'text-[#10b981]' : 'text-[#fc7c78]'}`}>
                            {src.active ? 'ACTIVE' : 'INACTIVE'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-xs font-data-mono text-[#bbcabf]">
                <SonicLoader size="small" /> Querying Beets runtime diagnostic status...
              </div>
            )}
          </div>

          {/* YAML Editor Block */}
          <div className="bg-[#131314] border border-[#27272a] flex flex-col">

            {/* Editor Toolbar Header */}
            <div className="p-4 bg-[#1c1b1c] border-b border-[#27272a] flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <FileCode size={16} className="text-[#10b981]" />
                <span className="font-label-caps text-xs text-[#e5e2e3] font-bold uppercase tracking-wider">
                  Isolated App Config (YAML)
                </span>
                {hasUnsavedYaml ? (
                  <span className="bg-[#fc7c78]/20 text-[#fc7c78] border border-[#fc7c78]/40 font-data-mono text-[10px] px-2 py-0.5 font-bold uppercase">
                    Unsaved Changes
                  </span>
                ) : (
                  <span className="bg-[#10b981]/20 text-[#10b981] border border-[#10b981]/40 font-data-mono text-[10px] px-2 py-0.5 font-bold uppercase">
                    Saved
                  </span>
                )}
              </div>

              {/* YAML Editor Toolbar Controls */}
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleValidateYaml}
                  disabled={yamlValidating || yamlLoading}
                  className="flex items-center gap-1.5 bg-[#0a0a0b] hover:bg-[#27272a] text-[#e5e2e3] border border-[#27272a] px-3 py-1.5 font-data-mono text-xs font-bold transition-all cursor-pointer disabled:opacity-50"
                >
                  {yamlValidating ? <SonicLoader size="small" /> : <ShieldCheck size={14} className="text-[#10b981]" />}
                  VALIDATE SYNTAX
                </button>

                <button
                  type="button"
                  onClick={handleResetYaml}
                  disabled={!hasUnsavedYaml}
                  className="flex items-center gap-1.5 bg-[#0a0a0b] hover:bg-[#27272a] text-[#bbcabf] border border-[#27272a] px-3 py-1.5 font-data-mono text-xs font-bold transition-all cursor-pointer disabled:opacity-40"
                >
                  <RotateCcw size={14} />
                  REVERT
                </button>

                <button
                  type="button"
                  onClick={() => setShowResetConfirm(true)}
                  className="flex items-center gap-1.5 bg-[#0a0a0b] hover:bg-[#27272a] text-[#fc7c78] border border-[#27272a] px-3 py-1.5 font-data-mono text-xs font-bold transition-all cursor-pointer"
                >
                  RESTORE DEFAULTS
                </button>

                <Button
                  type="button"
                  onClick={handleSaveYaml}
                  disabled={yamlSaving || !hasUnsavedYaml}
                  variant="primary"
                  className="py-1.5 font-bold uppercase text-xs"
                >
                  {yamlSaving ? <SonicLoader size="small" /> : <Save size={14} />}
                  SAVE YAML
                </Button>
              </div>
            </div>

            {/* Validation Banner / Error Message */}
            {yamlMessage && (
              <div className={`p-4 border-b flex items-start gap-3 font-data-mono text-xs ${
                yamlMessage.type === 'success'
                  ? 'bg-[#10b981]/10 border-[#10b981]/30 text-[#10b981]'
                  : 'bg-[#fc7c78]/10 border-[#fc7c78]/30 text-[#fc7c78]'
              }`}>
                {yamlMessage.type === 'success' ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
                <div className="flex flex-col gap-1">
                  <span className="font-bold">{yamlMessage.text}</span>
                  {yamlMessage.line && (
                    <span className="text-[11px] opacity-80">
                      Error Location: Line {yamlMessage.line}, Column {yamlMessage.column || 1}
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Confirm Default Restore Modal Dialog */}
            {showResetConfirm && (
              <div className="p-4 bg-[#fc7c78]/10 border-b border-[#fc7c78]/30 flex items-center justify-between font-data-mono text-xs text-[#fc7c78]">
                <span>Are you sure you want to reset your editor to default Beets settings?</span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleRestoreDefaultYaml}
                    className="bg-[#fc7c78] text-[#0a0a0b] font-bold px-3 py-1 uppercase cursor-pointer"
                  >
                    Confirm Reset
                  </button>
                  <button
                    onClick={() => setShowResetConfirm(false)}
                    className="bg-[#27272a] text-[#e5e2e3] font-bold px-3 py-1 uppercase cursor-pointer"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {/* Monospaced Editor Textarea */}
            <div className="relative">
              {yamlLoading ? (
                <div className="h-96 flex flex-col items-center justify-center gap-3 bg-[#0a0a0b] text-[#bbcabf]">
                  <SonicLoader size="large" />
                  <span className="font-data-mono text-xs uppercase tracking-wider">Loading Beets Configuration...</span>
                </div>
              ) : (
                <textarea
                  value={yamlContent}
                  onChange={(e) => setYamlContent(e.target.value)}
                  spellCheck={false}
                  rows={22}
                  className="w-full bg-[#0a0a0b] p-4 font-data-mono text-xs text-[#e5e2e3] leading-relaxed resize-y focus:outline-none focus:ring-1 focus:ring-[#10b981] border-none select-text"
                  placeholder="# Write or paste custom Beets YAML configuration here..."
                />
              )}
            </div>

            <div className="p-3 bg-[#1c1b1c] border-t border-[#27272a] font-data-mono text-[11px] text-[#bbcabf] opacity-75">
              * Isolated Application Config: Changes made here only affect Track Portal and will not modify global user <code>~/.config/beets/config.yaml</code>.
            </div>
          </div>
        </div>
      )}

      {/* SUBMENU 2: SLSKD NETWORK CONFIGURATION */}
      {activeSubMenu === 'slskd' && (
        <form onSubmit={handleGeneralSave} className="bg-[#131314] border border-[#27272a] divide-y divide-[#27272a] rounded-none">
          {isSaved && (
            <div className="bg-[#131314] border border-[#10b981] p-4 text-[#10b981] font-semibold text-sm flex items-center gap-3">
              <Info size={16} />
              <span>SLSKD daemon configurations saved successfully!</span>
            </div>
          )}

          <div className="p-6 flex flex-col gap-4">
            <h3 className="font-label-caps text-label-caps text-[#e5e2e3] font-bold flex items-center gap-2 select-none uppercase tracking-widest border-b border-[#27272a] pb-2">
              <Server size={14} className="text-[#10b981]" />
              slskd Daemon Connection
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

              <div>
                <label className="block font-label-caps text-[10px] text-[#bbcabf] mb-1.5 uppercase">
                  Search Timeout (seconds)
                </label>
                <Input
                  type="number"
                  min="5"
                  max="120"
                  value={formState.waitUntilComplete ? '' : formState.searchTimeoutSec}
                  disabled={formState.waitUntilComplete}
                  placeholder={formState.waitUntilComplete ? 'Unavailable (Wait Until Complete active)' : '15'}
                  onChange={(e) => setFormState({ ...formState, searchTimeoutSec: parseInt(e.target.value) || 15 })}
                  className={formState.waitUntilComplete ? 'opacity-50 cursor-not-allowed bg-[#18181b]' : ''}
                />
              </div>

              <div className="flex flex-col justify-end">
                <label className="flex items-center gap-3 cursor-pointer p-3 border border-[#27272a] bg-[#0a0a0b] hover:border-[#3f3f46] transition">
                  <input
                    type="checkbox"
                    checked={formState.waitUntilComplete}
                    onChange={(e) => setFormState({ ...formState, waitUntilComplete: e.target.checked })}
                    className="w-4 h-4 accent-[#10b981] bg-[#18181b] border-[#3f3f46] rounded-none cursor-pointer"
                  />
                  <div className="flex flex-col">
                    <span className="font-label-caps text-[11px] font-bold text-[#e5e2e3] uppercase">
                      Wait until search is over
                    </span>
                    <span className="font-data-mono text-[10px] text-[#bbcabf] opacity-75">
                      Poll search state until complete; disables fixed search timeout
                    </span>
                  </div>
                </label>
              </div>
            </div>
          </div>

          <div className="p-6 bg-[#1c1b1c] flex justify-end select-none">
            <Button type="submit" variant="primary">
              <Save size={14} />
              SAVE NETWORK CONFIGS
            </Button>
          </div>
        </form>
      )}

      {/* SUBMENU 3: INTEGRATIONS & SERVICES */}
      {activeSubMenu === 'integrations' && (
        <form onSubmit={handleGeneralSave} className="bg-[#131314] border border-[#27272a] divide-y divide-[#27272a] rounded-none">
          {isSaved && (
            <div className="bg-[#131314] border border-[#10b981] p-4 text-[#10b981] font-semibold text-sm flex items-center gap-3">
              <Info size={16} />
              <span>Integration credentials saved successfully!</span>
            </div>
          )}

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
              Last.fm Recommendation Sync
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

          <div className="p-6 bg-[#1c1b1c] flex justify-end select-none">
            <Button type="submit" variant="primary">
              <Save size={14} />
              SAVE INTEGRATIONS
            </Button>
          </div>
        </form>
      )}

    </div>
  );
}
