'use client';

import React, { useState, useEffect } from 'react';
import { useDownloadStore } from '../store/downloadStore';
import { DownloadItem, DownloadStatus } from '../types';
import { Search, Pause, Play, RefreshCw, X, FolderOpen, AlertTriangle, CheckCircle, Clock, Music } from 'lucide-react';
import Input from './ui/Input';
import ProgressBar from './ui/ProgressBar';

export default function DownloadsView() {
  const {
    queue,
    fetchQueue,
    pollInterval,
    cancelDownload,
    retryDownload,
    pauseAll,
    resumeAll,
    clearCompleted,
  } = useDownloadStore();

  const [filterQuery, setFilterQuery] = useState('');

  useEffect(() => {
    let timeoutId: any;

    const poll = async () => {
      await fetchQueue();
      const currentInterval = useDownloadStore.getState().pollInterval;
      timeoutId = setTimeout(poll, currentInterval);
    };

    poll();

    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [fetchQueue]);

  const formatBytes = (bytes: number) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + sizes[i];
  };

  const formatSpeed = (bytesPerSec: number) => {
    if (!bytesPerSec || bytesPerSec === 0) return '--';
    return `${formatBytes(bytesPerSec)}/s`;
  };

  const formatEta = (seconds: number) => {
    if (!seconds || seconds === 0) return '--';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const filteredQueue = queue.filter((item) =>
    item.filename.toLowerCase().includes(filterQuery.toLowerCase()) ||
    item.username.toLowerCase().includes(filterQuery.toLowerCase())
  );

  const activeDownloads = filteredQueue.filter((item) => item.status === 'downloading');
  const queuedDownloads = filteredQueue.filter((item) => item.status === 'queued');
  const completedDownloads = filteredQueue.filter((item) => item.status === 'completed');
  const failedDownloads = filteredQueue.filter((item) => item.status === 'failed');

  return (
    <div className="w-full max-w-5xl mx-auto flex flex-col gap-8 animate-fade-in-up mt-4 select-none">

      {/* Toolbar Head */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h2 className="font-headline-md text-headline-md font-bold text-[#e5e2e3]">
            Transfer Queue
          </h2>
          <p className="font-data-mono text-data-mono text-[#bbcabf] opacity-75 mt-1">
            Real-time slskd download manager
          </p>
        </div>

        {/* Toolbar Controls */}
        <div className="flex flex-wrap items-center gap-4 w-full md:w-auto">
          <div className="relative flex items-center w-full md:w-64">
            <Input
              icon={Search}
              placeholder="Filter transfers..."
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
            />
          </div>

          <div className="flex bg-[#131314] border border-[#27272a] shrink-0">
            <button
              onClick={pauseAll}
              title="Pause All"
              className="px-4 py-2 hover:bg-[#201f20] transition-colors border-r border-[#27272a] text-[#bbcabf] hover:text-[#e5e2e3] cursor-pointer flex items-center gap-1.5"
            >
              <Pause size={16} />
              <span className="font-data-mono text-[10px] opacity-60">⌘P</span>
            </button>
            <button
              onClick={resumeAll}
              title="Resume All"
              className="px-4 py-2 hover:bg-[#201f20] transition-colors border-r border-[#27272a] text-[#bbcabf] hover:text-[#e5e2e3] cursor-pointer flex items-center gap-1.5"
            >
              <Play size={16} />
              <span className="font-data-mono text-[10px] opacity-60">⌘R</span>
            </button>
            <button
              onClick={clearCompleted}
              title="Clear Completed"
              className="px-4 py-2 hover:bg-[#201f20] transition-colors text-[#bbcabf] hover:text-red-400 cursor-pointer flex items-center gap-1.5"
            >
              <X size={16} />
              <span className="font-data-mono text-[10px] opacity-60">SHIFT+⌘+DEL</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Queue Data Grid Container */}
      <div className="border border-[#27272a] bg-[#131314] flex flex-col divide-y divide-[#27272a]">

        {/* Table Headers - Hidden on Mobile */}
        <div className="hidden md:grid grid-cols-12 gap-4 px-6 py-3 bg-[#1c1b1c] font-label-caps text-label-caps text-[#bbcabf] tracking-widest uppercase text-xs">
          <div className="col-span-5">Filename</div>
          <div className="col-span-3">Status</div>
          <div className="col-span-1 text-right">Size</div>
          <div className="col-span-1 text-right">Speed</div>
          <div className="col-span-1 text-right">ETA</div>
          <div className="col-span-1 text-right">Actions</div>
        </div>

        {/* SECTION: ACTIVE DOWNLOADS */}
        {activeDownloads.length > 0 && (
          <div className="flex flex-col divide-y divide-[#27272a]/30">
            <div className="px-6 py-2 bg-[#0e0e0f] border-b border-[#27272a] flex items-center select-none">
              <span className="w-1.5 h-1.5 bg-[#10b981] inline-block animate-pulse rounded-none mr-2"></span>
              <span className="font-label-caps text-label-caps text-[#10b981] uppercase tracking-wider font-bold">
                Active ({activeDownloads.length})
              </span>
            </div>

            {activeDownloads.map((item) => (
              <React.Fragment key={item.id}>
                {/* Desktop layout row */}
                <div className="hidden md:grid grid-cols-12 gap-4 px-6 py-4 items-center hover:bg-[#1c1b1c] transition-colors group">
                  <div className="col-span-5 truncate pr-4 text-[#e5e2e3] font-semibold text-sm" title={item.filename}>
                    {item.filename}
                  </div>
                  <div className="col-span-3 flex flex-col justify-center">
                    <div className="flex justify-between font-data-mono text-[11px] text-[#bbcabf] mb-1.5 select-none">
                      <span>Downloading ({item.username})</span>
                      <span className="text-[#10b981] font-bold">{Math.round(item.progress)}%</span>
                    </div>
                    <ProgressBar progress={item.progress} animateStripe />
                  </div>
                  <div className="col-span-1 text-right font-data-mono text-data-mono text-[#bbcabf]">{formatBytes(item.size)}</div>
                  <div className="col-span-1 text-right font-data-mono text-data-mono text-[#10b981]">{formatSpeed(item.speed)}</div>
                  <div className="col-span-1 text-right font-data-mono text-data-mono text-[#10b981]">{formatEta(item.eta)}</div>
                  <div className="col-span-1 flex justify-end gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => cancelDownload(item.id, item.username)}
                      className="p-1 text-[#bbcabf] hover:text-red-400 cursor-pointer"
                      title="Cancel"
                    >
                      <X size={16} />
                    </button>
                  </div>
                </div>

                {/* Mobile layout card */}
                <div className="md:hidden flex flex-col gap-2 p-3 bg-[#131314]">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-10 h-10 bg-[#201f20] border border-[#27272a] flex-shrink-0 flex items-center justify-center">
                        <span className="text-[#10b981]"><Music size={20} /></span>
                      </div>
                      <div className="flex flex-col min-w-0">
                        <h3 className="font-body-md text-[13px] font-semibold text-[#e5e2e3] truncate" title={item.filename}>{item.filename}</h3>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="font-data-mono text-[10px] text-[#bbcabf] truncate">{item.username}</span>
                          <span className="w-1 h-1 rounded-full bg-[#10b981] animate-pulse"></span>
                          <span className="font-data-mono text-[10px] text-[#10b981]">{formatSpeed(item.speed)}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {item.eta > 0 && <span className="font-data-mono text-[10px] text-[#bbcabf] mr-1">ETA: {formatEta(item.eta)}</span>}
                      <button
                        onClick={() => cancelDownload(item.id, item.username)}
                        className="p-1.5 text-red-400 hover:text-red-500 cursor-pointer"
                        title="Cancel"
                      >
                        <X size={16} />
                      </button>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-grow">
                      <ProgressBar progress={item.progress} animateStripe />
                    </div>
                    <span className="font-data-mono text-[10px] text-[#10b981] w-8 text-right shrink-0">{Math.round(item.progress)}%</span>
                  </div>
                </div>
              </React.Fragment>
            ))}
          </div>
        )}

        {/* SECTION: QUEUED/PENDING DOWNLOADS */}
        {queuedDownloads.length > 0 && (
          <div className="flex flex-col divide-y divide-[#27272a]/30">
            <div className="px-6 py-2 bg-[#0e0e0f] border-b border-[#27272a] flex items-center select-none border-t border-[#27272a]">
              <Clock size={12} className="text-[#bbcabf]/70 mr-2" />
              <span className="font-label-caps text-label-caps text-[#bbcabf]/70 uppercase tracking-wider font-bold">
                Queued ({queuedDownloads.length})
              </span>
            </div>

            {queuedDownloads.map((item) => (
              <React.Fragment key={item.id}>
                {/* Desktop layout row */}
                <div className="hidden md:grid grid-cols-12 gap-4 px-6 py-4 items-center hover:bg-[#1c1b1c] transition-colors group">
                  <div className="col-span-5 truncate pr-4 text-[#bbcabf] text-sm" title={item.filename}>
                    {item.filename}
                  </div>
                  <div className="col-span-3 flex items-center font-data-mono text-data-mono text-[#bbcabf]/70">
                    <Clock size={14} className="mr-2" />
                    <span>Pending</span>
                  </div>
                  <div className="col-span-1 text-right font-data-mono text-data-mono text-[#bbcabf]/70">{formatBytes(item.size)}</div>
                  <div className="col-span-1 text-right font-data-mono text-data-mono text-[#bbcabf]/70">--</div>
                  <div className="col-span-1 text-right font-data-mono text-data-mono text-[#bbcabf]/70">--</div>
                  <div className="col-span-1 flex justify-end gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => cancelDownload(item.id, item.username)}
                      className="p-1 text-[#bbcabf] hover:text-red-400 cursor-pointer"
                      title="Cancel"
                    >
                      <X size={16} />
                    </button>
                  </div>
                </div>

                {/* Mobile layout card */}
                <div className="md:hidden flex items-center justify-between gap-4 p-3 bg-[#131314]">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 bg-[#201f20] border border-[#27272a] flex-shrink-0 flex items-center justify-center">
                      <span className="text-[#bbcabf]"><Clock size={20} /></span>
                    </div>
                    <div className="flex flex-col min-w-0">
                      <h3 className="font-body-md text-[13px] font-semibold text-[#bbcabf] truncate" title={item.filename}>{item.filename}</h3>
                      <p className="font-data-mono text-[10px] text-[#bbcabf]/75 mt-0.5">{formatBytes(item.size)} • Waiting in queue</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      onClick={() => cancelDownload(item.id, item.username)}
                      className="p-1.5 text-red-400 hover:text-red-500 cursor-pointer"
                      title="Cancel"
                    >
                      <X size={16} />
                    </button>
                  </div>
                </div>
              </React.Fragment>
            ))}
          </div>
        )}

        {/* SECTION: COMPLETED DOWNLOADS */}
        {completedDownloads.length > 0 && (
          <div className="flex flex-col divide-y divide-[#27272a]/30">
            <div className="px-6 py-2 bg-[#0e0e0f] border-b border-[#27272a] flex items-center select-none border-t border-[#27272a]">
              <CheckCircle size={12} className="text-[#10b981] mr-2" />
              <span className="font-label-caps text-label-caps text-[#bbcabf]/70 uppercase tracking-wider font-bold">
                Completed ({completedDownloads.length})
              </span>
            </div>

            {completedDownloads.map((item) => (
              <React.Fragment key={item.id}>
                {/* Desktop layout row */}
                <div className="hidden md:grid grid-cols-12 gap-4 px-6 py-4 items-center hover:bg-[#1c1b1c] transition-colors group">
                  <div className="col-span-5 truncate pr-4 text-[#bbcabf]/80 text-sm" title={item.filename}>
                    {item.filename}
                  </div>
                  <div className="col-span-3 flex items-center font-data-mono text-data-mono text-[#10b981]">
                    <CheckCircle size={14} className="mr-2" />
                    <span>Done</span>
                  </div>
                  <div className="col-span-1 text-right font-data-mono text-data-mono text-[#bbcabf]/70">{formatBytes(item.size)}</div>
                  <div className="col-span-1 text-right font-data-mono text-data-mono text-[#bbcabf]/70">-</div>
                  <div className="col-span-1 text-right font-data-mono text-data-mono text-[#bbcabf]/70">-</div>
                  <div className="col-span-1 flex justify-end">
                    <button
                      className="p-1 text-[#bbcabf] hover:text-[#10b981] cursor-pointer"
                      title="Open Folder"
                    >
                      <FolderOpen size={16} />
                    </button>
                  </div>
                </div>

                {/* Mobile layout card */}
                <div className="md:hidden flex items-center justify-between gap-4 p-3 bg-[#131314]">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 bg-[#201f20] border border-[#27272a] flex-shrink-0 flex items-center justify-center">
                      <span className="text-[#10b981]"><CheckCircle size={20} /></span>
                    </div>
                    <div className="flex flex-col min-w-0">
                      <h3 className="font-body-md text-[13px] font-semibold text-[#e5e2e3] truncate" title={item.filename}>{item.filename}</h3>
                      <p className="font-data-mono text-[10px] text-[#bbcabf]/75 mt-0.5">{formatBytes(item.size)} • Done</p>
                    </div>
                  </div>
                  <button className="p-2 text-[#bbcabf] hover:text-[#e5e2e3] cursor-pointer shrink-0">
                    <FolderOpen size={16} />
                  </button>
                </div>
              </React.Fragment>
            ))}
          </div>
        )}

        {/* SECTION: FAILED DOWNLOADS */}
        {failedDownloads.length > 0 && (
          <div className="flex flex-col divide-y divide-[#27272a]/30">
            <div className="px-6 py-2 bg-[#0e0e0f] border-b border-[#27272a] flex items-center select-none border-t border-[#27272a]">
              <AlertTriangle size={12} className="text-red-400 mr-2" />
              <span className="font-label-caps text-label-caps text-red-400 uppercase tracking-wider font-bold">
                Failed ({failedDownloads.length})
              </span>
            </div>

            {failedDownloads.map((item) => (
              <React.Fragment key={item.id}>
                {/* Desktop layout row */}
                <div className="hidden md:grid grid-cols-12 gap-4 px-6 py-4 items-center hover:bg-[#1c1b1c] transition-colors group">
                  <div className="col-span-5 truncate pr-4 text-[#bbcabf]/80 text-sm" title={item.filename}>
                    {item.filename}
                  </div>
                  <div className="col-span-3 flex items-center font-data-mono text-data-mono text-red-400">
                    <AlertTriangle size={14} className="mr-2" />
                    <span>Connection Lost ({formatBytes(item.bytesTransferred)}/{formatBytes(item.size)})</span>
                  </div>
                  <div className="col-span-1 text-right font-data-mono text-data-mono text-[#bbcabf]/70">{formatBytes(item.size)}</div>
                  <div className="col-span-1 text-right font-data-mono text-data-mono text-[#bbcabf]/70">-</div>
                  <div className="col-span-1 text-right font-data-mono text-data-mono text-[#bbcabf]/70">-</div>
                  <div className="col-span-1 flex justify-end gap-1.5">
                    <button
                      onClick={() => retryDownload(item.id)}
                      className="p-1 text-[#bbcabf] hover:text-[#10b981] cursor-pointer"
                      title="Retry"
                    >
                      <RefreshCw size={16} />
                    </button>
                    <button
                      onClick={() => cancelDownload(item.id, item.username)}
                      className="p-1 text-[#bbcabf] hover:text-red-400 cursor-pointer"
                      title="Remove"
                    >
                      <X size={16} />
                    </button>
                  </div>
                </div>

                {/* Mobile layout card */}
                <div className="md:hidden flex items-center justify-between gap-4 p-3 bg-[#131314]">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 bg-[#201f20] border border-[#27272a] flex-shrink-0 flex items-center justify-center">
                      <span className="text-red-400"><AlertTriangle size={20} /></span>
                    </div>
                    <div className="flex flex-col min-w-0">
                      <h3 className="font-body-md text-[13px] font-semibold text-[#bbcabf] truncate" title={item.filename}>{item.filename}</h3>
                      <p className="font-data-mono text-[10px] text-red-400 mt-0.5">Connection Lost ({formatBytes(item.bytesTransferred || 0)}/{formatBytes(item.size)})</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button onClick={() => retryDownload(item.id)} className="p-1.5 text-[#bbcabf] hover:text-[#10b981] cursor-pointer">
                      <RefreshCw size={16} />
                    </button>
                    <button onClick={() => cancelDownload(item.id, item.username)} className="p-1.5 text-red-400 hover:text-red-500 cursor-pointer">
                      <X size={16} />
                    </button>
                  </div>
                </div>
              </React.Fragment>
            ))}
          </div>
        )}

        {filteredQueue.length === 0 && (
          <div className="p-12 text-center text-[#bbcabf] font-body-md flex flex-col items-center gap-2">
            <Clock size={24} className="text-[#27272a]" />
            <span>No transfers found matching your filter query.</span>
          </div>
        )}
      </div>
    </div>
  );
}
