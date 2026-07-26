'use client';

import React, { useState, useMemo } from 'react';
import { useSearchStore } from '../store/searchStore';
import { useDownloadStore } from '../store/downloadStore';
import { SlskdResult } from '../types';
import { useReactTable, getCoreRowModel, getPaginationRowModel, flexRender, createColumnHelper } from '@tanstack/react-table';
import { Search, Filter, Sliders, CheckSquare, Square, Download, ChevronDown, ChevronRight, HelpCircle, ArrowUpDown } from 'lucide-react';
import Button from './ui/Button';
import Card from './ui/Card';
import ScoreBadge from './ui/ScoreBadge';

export default function SearchResultsView() {
  const { results, isSearching, artist, track, filters, updateFilters, toggleFormatFilter, clearFilters } = useSearchStore();
  const { addDownload } = useDownloadStore();

  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [toastType, setToastType] = useState<'success' | 'error'>('success');
  const [isAccordionMode, setIsAccordionMode] = useState(false);
  const [expandedAlbums, setExpandedAlbums] = useState<Record<string, boolean>>({});
  const [rowSelection, setRowSelection] = useState<Record<string, boolean>>({});

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToastMessage(message);
    setToastType(type);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const handleDownloadSingle = async (item: SlskdResult) => {
    try {
      const response = await fetch('/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          artist: item.parsed_artist || item.username,
          track: item.parsed_track || item.filename,
          album: item.parsed_album || '',
          filename: item.filename,
          size: item.size,
          username: item.username,
          format: item.format,
          bitrate: item.bitrate || 0,
        }),
      });

      if (!response.ok) throw new Error('Failed to enqueue download');

      addDownload({
        filename: item.filename,
        username: item.username,
        status: 'queued',
        size: item.size,
      });

      showToast(`Enqueued download: "${item.filename}" successfully!`);
    } catch (err: any) {
      showToast(err.message || 'Download enqueued failed', 'error');
    }
  };

  const handleDownloadSelected = async () => {
    const selectedItems = table.getSelectedRowModel().rows.map(r => r.original);
    if (selectedItems.length === 0) return;

    let successCount = 0;
    for (const item of selectedItems) {
      try {
        await fetch('/api/download', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            artist: item.parsed_artist || item.username,
            track: item.parsed_track || item.filename,
            album: item.parsed_album || '',
            filename: item.filename,
            size: item.size,
            username: item.username,
            format: item.format,
            bitrate: item.bitrate || 0,
          }),
        });

        addDownload({
          filename: item.filename,
          username: item.username,
          status: 'queued',
          size: item.size,
        });
        successCount++;
      } catch (err) {
        console.error(err);
      }
    }

    showToast(`Successfully enqueued ${successCount} downloads!`);
    setRowSelection({});
  };

  const formatBytes = (bytes: number) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + sizes[i];
  };

  const filteredResults = useMemo(() => {
    return results.filter((item) => {
      const ext = item.format.toLowerCase();
      if (ext === 'flac' && !filters.format.flac) return false;
      if (ext === 'mp3' && !filters.format.mp3) return false;
      if (ext === 'wav' && !filters.format.wav) return false;

      if (filters.bitrate !== 'All') {
        const br = item.bitrate || 0;
        if (filters.bitrate === 'Lossless' && !['flac', 'wav', 'alac'].includes(ext)) return false;
        if (filters.bitrate === '320kbps' && br < 320) return false;
        if (filters.bitrate === 'V0 (VBR)' && ext === 'mp3' && br > 280) return false;
      }

      if (item.size > filters.maxSize * 1024 * 1024) return false;
      if (filters.queueLength === 'empty' && item.queue_length > 0) return false;
      if (filters.queueLength === 'under5' && item.queue_length >= 5) return false;
      if (filters.username && !item.username.toLowerCase().includes(filters.username.toLowerCase())) return false;

      return true;
    });
  }, [results, filters]);

  const getParentFolder = (filepath: string) => {
    if (!filepath) return "Root";
    const parts = filepath.split(/[\\/]/);
    if (parts.length > 1) {
      return parts[parts.length - 2];
    }
    return "Root";
  };

  const canonicalGroupedResults = useMemo(() => {
    const releases: Record<string, {
      name: string;
      year?: number;
      mbid?: string;
      confidence: number;
      verified: boolean;
      tracksCount: number;
      unresolvedCount: number;
      avgScore: number;
      sourceCount: number;
      folders: Record<string, {
        folderName: string;
        avgScore: number;
        tracks: SlskdResult[];
      }>;
    }> = {};

    filteredResults.forEach((item) => {
      const releaseName = item.canonical_album || item.parsed_album || 'Single/Unclassified';
      const isVerified = !!item.canonical_verified;

      const key = isVerified ? `${releaseName}::${item.canonical_year || ''}` : `Unresolved::${releaseName}`;

      if (!releases[key]) {
        releases[key] = {
          name: releaseName,
          year: item.canonical_year || item.parsed_year || undefined,
          mbid: item.canonical_mbid || undefined,
          confidence: item.canonical_confidence || 0,
          verified: isVerified,
          tracksCount: 0,
          unresolvedCount: 0,
          avgScore: 0,
          sourceCount: 0,
          folders: {}
        };
      }

      const release = releases[key];
      release.tracksCount++;
      if (!isVerified) {
        release.unresolvedCount++;
      }

      const parentFolder = getParentFolder(item.filename);
      if (!release.folders[parentFolder]) {
        release.folders[parentFolder] = {
          folderName: parentFolder,
          avgScore: 0,
          tracks: []
        };
      }

      release.folders[parentFolder].tracks.push(item);
    });

    return Object.entries(releases).map(([key, rel]) => {
      const foldersList = Object.values(rel.folders).map(folder => {
        const sum = folder.tracks.reduce((acc, t) => acc + (t.score || 0), 0);
        folder.avgScore = Math.round(sum / folder.tracks.length);
        return folder;
      });

      foldersList.sort((a, b) => {
        if (b.tracks.length !== a.tracks.length) {
          return b.tracks.length - a.tracks.length;
        }
        return b.avgScore - a.avgScore;
      });

      const totalScoreSum = foldersList.reduce((acc, f) => acc + f.avgScore, 0);
      rel.avgScore = foldersList.length > 0 ? Math.round(totalScoreSum / foldersList.length) : 0;
      rel.sourceCount = foldersList.length;

      return {
        ...rel,
        key,
        foldersList
      };
    });
  }, [filteredResults]);

  const columnHelper = createColumnHelper<SlskdResult>();
  const columns = useMemo(() => [
    columnHelper.display({
      id: 'select',
      header: ({ table }) => (
        <input
          type="checkbox"
          checked={table.getIsAllRowsSelected()}
          onChange={table.getToggleAllRowsSelectedHandler()}
          className="rounded-none bg-[#0a0a0b] border-[#27272a] text-[#10b981] focus:ring-0 h-3 w-3 cursor-pointer"
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={row.getIsSelected()}
          onChange={row.getToggleSelectedHandler()}
          className="rounded-none bg-[#0a0a0b] border-[#27272a] text-[#10b981] focus:ring-0 h-3 w-3 cursor-pointer"
        />
      ),
      meta: { width: 'w-12' }
    }),
    columnHelper.accessor('score', {
      header: 'Score',
      cell: (info) => {
        const score = info.getValue() || 0;
        const reasons = info.row.original.score_reasons || '';
        return (
          <div className="relative group/score inline-block">
            <ScoreBadge score={score} />
            {reasons && (
              <div className="absolute left-12 top-0 scale-0 group-hover/score:scale-100 transition-all duration-150 bg-[#131314] border border-[#27272a] p-3 text-left font-data-mono text-[10px] text-[#bbcabf] whitespace-pre z-50 shadow-2xl rounded-none w-max max-w-xs pointer-events-none select-none">
                {reasons}
              </div>
            )}
          </div>
        );
      },
      meta: { width: 'w-16' }
    }),
    columnHelper.accessor('parsed_track', {
      header: 'Track',
      cell: (info) => <span className="font-semibold text-[#e5e2e3] truncate block" title={info.getValue()}>{info.getValue() || 'Unknown'}</span>,
      meta: { width: 'w-48' }
    }),
    columnHelper.accessor('parsed_artist', {
      header: 'Artist',
      cell: (info) => <span className="truncate block" title={info.getValue()}>{info.getValue() || 'Unknown'}</span>,
      meta: { width: 'w-32' }
    }),
    columnHelper.accessor('parsed_album', {
      header: 'Album',
      cell: (info) => <span className="truncate block text-[#bbcabf]/70" title={info.getValue()}>{info.getValue() || 'Unknown'}</span>,
      meta: { width: 'w-48' }
    }),
    columnHelper.accessor('format', {
      header: 'Fmt',
      cell: (info) => <span className="font-data-mono text-data-mono text-[#e5e2e3] uppercase">{info.getValue()}</span>,
      meta: { width: 'w-16' }
    }),
    columnHelper.accessor('bitrate', {
      header: 'Bitrate',
      cell: (info) => <span className="font-data-mono text-data-mono">{info.getValue() ? `${info.getValue()}kbps` : 'Lossless'}</span>,
      meta: { width: 'w-20' }
    }),
    columnHelper.accessor('size', {
      header: 'Size',
      cell: (info) => <span className="font-data-mono text-data-mono text-right block pr-2">{formatBytes(info.getValue())}</span>,
      meta: { width: 'w-20' }
    }),
    columnHelper.accessor('username', {
      header: 'User',
      cell: (info) => <span className="font-data-mono text-data-mono text-[#10b981] truncate block" title={info.getValue()}>{info.getValue()}</span>,
      meta: { width: 'w-28' }
    }),
    columnHelper.accessor('queue_length', {
      header: 'Q',
      cell: (info) => <span className="font-data-mono text-data-mono text-right block pr-2">{info.getValue()}</span>,
      meta: { width: 'w-12' }
    }),
    columnHelper.display({
      id: 'actions',
      header: '',
      cell: ({ row }) => (
        <button
          onClick={() => handleDownloadSingle(row.original)}
          className="opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity p-1 text-[#bbcabf] hover:text-[#10b981] cursor-pointer"
        >
          <Download size={16} />
        </button>
      ),
      meta: { width: 'w-10' }
    }),
  ], [columnHelper, addDownload]);

  const table = useReactTable({
    data: filteredResults,
    columns,
    state: { rowSelection },
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getRowId: (row) => `${row.username}-${row.filename}-${row.size}`,
    initialState: {
      pagination: {
        pageSize: 50,
      },
    },
  });

  const selectedCount = Object.keys(rowSelection).length;
  const toggleAlbumExpand = (album: string) => {
    setExpandedAlbums((prev) => ({ ...prev, [album]: !prev[album] }));
  };

  return (
    <div className="flex h-[calc(100vh-10rem)] overflow-hidden bg-[#0a0a0b] animate-fade-in-up -mx-8 -my-8 select-none">

      {toastMessage && (
        <div className={`fixed bottom-6 right-6 border p-4 z-50 flex items-center gap-3 ${
          toastType === 'success' ? 'bg-[#131314] border-[#10b981] text-[#10b981]' : 'bg-[#131314] border-red-500 text-red-400'
        }`}>
          <span className="font-semibold text-sm">{toastMessage}</span>
        </div>
      )}

      {/* Main Grid Section */}
      <div className="flex-1 flex flex-col h-full overflow-hidden border-r border-[#27272a]">

        {/* Table Title Header */}
        <div className="p-8 pb-4 border-b border-[#27272a] shrink-0 bg-[#0a0a0b]">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-headline-lg text-headline-lg text-[#e5e2e3] font-bold tracking-tight">
                Search Results
              </h2>
              <p className="font-data-mono text-data-mono text-[#bbcabf] mt-1">
                {isSearching
                  ? 'Searching P2P networks and enriching results...'
                  : `${filteredResults.length} candidates found for "${artist ? `${artist} - ${track}` : track}"`
                }
              </p>
            </div>

            <button
              onClick={() => setIsAccordionMode(!isAccordionMode)}
              className={`border border-[#27272a] px-4 py-2 font-label-caps text-label-caps tracking-wider cursor-pointer hover:border-[#10b981] ${
                isAccordionMode ? 'bg-[#1c1b1c] text-[#10b981]' : 'bg-transparent text-[#bbcabf]'
              }`}
            >
              {isAccordionMode ? 'Flat Grid View' : 'Canonical Album Grouping'}
            </button>
          </div>
        </div>

        {/* Bulk Action Header bar */}
        {selectedCount > 0 && (
          <div className="bg-[#201f20] border-b border-[#27272a] px-8 py-2.5 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-4">
              <span className="font-data-mono text-data-mono text-[#e5e2e3] bg-[#2a2a2b] border border-[#27272a] px-2.5 py-1">
                {selectedCount} selected
              </span>
              <Button onClick={handleDownloadSelected} variant="primary" className="py-1.5 px-4 h-auto">
                <Download size={14} />
                Download Selected
              </Button>
              <Button onClick={() => showToast(`Comparing bitrates...`)} variant="secondary" className="py-1.5 px-4 h-auto">
                Compare Bitrates
              </Button>
            </div>
            <button
              onClick={() => setRowSelection({})}
              className="text-[#bbcabf] hover:text-[#e5e2e3] font-body-md text-sm flex items-center gap-1 cursor-pointer"
            >
              Clear Selection
            </button>
          </div>
        )}

        {/* Scrollable grid canvas */}
        <div className="flex-1 overflow-auto bg-[#0a0a0b]">
          {isSearching ? (
            <div className="h-full flex flex-col items-center justify-center gap-4 text-[#bbcabf]">
              <Loader2 className="animate-spin text-[#10b981]" size={36} />
              <span className="font-data-mono text-data-mono text-sm">Executing fallback strategies sequentially...</span>
            </div>
          ) : results.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center gap-2 text-[#bbcabf] py-24 select-none">
              <HelpCircle size={32} className="text-[#27272a]" />
              <span className="font-body-md text-[#bbcabf]">No search executed or zero results returned.</span>
              <span className="font-data-mono text-data-mono text-xs opacity-60">Go to Home tab to initiate a query.</span>
            </div>
          ) : isAccordionMode ? (
            /* SECTION: ACCORDION ALBUM GROUPINGS */
            <div className="divide-y divide-[#27272a] border-b border-[#27272a]">
              {canonicalGroupedResults.map((rel) => {
                const isExpanded = !!expandedAlbums[rel.key];
                return (
                  <div key={rel.key} className="bg-[#0e0e0f]">
                    <button
                      onClick={() => toggleAlbumExpand(rel.key)}
                      className="w-full flex items-center justify-between px-8 py-4 text-left hover:bg-[#1c1b1c] border-l-2 border-[#10b981] transition-colors cursor-pointer"
                    >
                      <div className="flex items-center gap-3">
                        {isExpanded ? <ChevronDown size={18} className="text-[#10b981]" /> : <ChevronRight size={18} className="text-[#bbcabf]" />}
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-headline-sm text-headline-sm text-[#e5e2e3] font-bold">
                            {rel.name} {rel.year ? `(${rel.year})` : ''}
                          </span>

                          {/* Visual Verified MusicBrainz Badges */}
                          {rel.verified && (
                            <span className="bg-[#10b981]/10 text-[#10b981] border border-[#10b981]/30 font-label-caps text-[9px] px-1.5 py-0.5 font-bold uppercase select-none rounded-none tracking-widest flex items-center gap-1">
                              ✓ Verified MB ({rel.confidence}%)
                            </span>
                          )}

                          <span className="font-data-mono text-[10px] text-[#bbcabf]/50 border border-[#27272a] px-1.5 py-0.5">
                            {rel.tracksCount} tracks
                          </span>
                          <span className="font-data-mono text-[10px] text-[#bbcabf]/50 border border-[#27272a] px-1.5 py-0.5">
                            {rel.sourceCount} sources
                          </span>
                          {rel.unresolvedCount > 0 && (
                            <span className="bg-amber-500/10 text-amber-500 border border-amber-500/30 font-data-mono text-[10px] px-1.5 py-0.5">
                              {rel.unresolvedCount} unresolved
                            </span>
                          )}
                        </div>
                      </div>
                      <span className="font-data-mono text-data-mono text-[#10b981]">
                        Avg Score: {rel.avgScore}%
                      </span>
                    </button>

                    {/* Level 2 Accordion Sources List */}
                    {isExpanded && (
                      <div className="bg-[#0e0e0f] pl-8 pr-8 pb-4 flex flex-col gap-4 border-t border-[#27272a]/50">
                        {rel.foldersList.map((folder, folderIdx) => {
                          const folderKey = `${rel.key}::folder::${folder.folderName}::${folderIdx}`;
                          const isFolderExpanded = !!expandedAlbums[folderKey];

                          return (
                            <div key={folderKey} className="border border-[#27272a]/60 bg-[#131314] mt-2">
                              {/* Level 2: Source Folder Header */}
                              <button
                                onClick={() => toggleAlbumExpand(folderKey)}
                                className="w-full flex items-center justify-between px-6 py-2.5 hover:bg-[#1c1b1c] text-left transition-colors cursor-pointer"
                              >
                                <div className="flex items-center gap-2">
                                  {isFolderExpanded ? <ChevronDown size={14} className="text-[#10b981]" /> : <ChevronRight size={14} className="text-[#bbcabf]" />}
                                  <span className="font-data-mono text-xs text-[#bbcabf] uppercase tracking-wider">Source Folder:</span>
                                  <span className="font-semibold text-sm text-[#e5e2e3] font-data-mono truncate" title={folder.folderName}>
                                    {folder.folderName}
                                  </span>
                                  <span className="font-data-mono text-[9px] text-[#bbcabf]/50 border border-[#27272a] px-1 py-0.5">
                                    {folder.tracks.length} tracks
                                  </span>
                                </div>
                                <span className="font-data-mono text-xs text-[#10b981]">
                                  Avg Score: {folder.avgScore}%
                                </span>
                              </button>

                              {/* Level 3: Files (Tracks Table) */}
                              {isFolderExpanded && (
                                <div className="bg-[#0a0a0b] border-t border-[#27272a] overflow-x-auto">
                                  <table className="w-full text-left border-collapse table-fixed whitespace-nowrap min-w-[700px]">
                                    <thead className="bg-[#131314] text-xs font-label-caps text-label-caps text-[#bbcabf]/70 uppercase border-b border-[#27272a]">
                                      <tr>
                                        <th className="p-2 w-16">Score</th>
                                        <th className="p-2 w-48">Track</th>
                                        <th className="p-2 w-16">Format</th>
                                        <th className="p-2 w-20">Bitrate</th>
                                        <th className="p-2 w-20">Size</th>
                                        <th className="p-2 w-24">User</th>
                                        <th className="p-2 w-12">Q</th>
                                        <th className="p-2 w-10 text-center"></th>
                                      </tr>
                                    </thead>
                                    <tbody className="divide-y divide-[#27272a]/40 font-body-md text-sm text-[#bbcabf]">
                                      {folder.tracks.map((track) => (
                                        <tr key={`${track.username}-${track.filename}-${track.size}`} className="hover:bg-[#1c1b1c]/70 group border-b border-[#27272a]/30">
                                          <td className="p-2 relative group/scorecell">
                                            <span className="font-data-mono text-data-mono text-[#10b981] font-bold cursor-help">{track.score}</span>
                                            {track.score_reasons && (
                                              <div className="absolute left-12 top-0 scale-0 group-hover/scorecell:scale-100 transition-all duration-150 bg-[#131314] border border-[#27272a] p-3 text-left font-data-mono text-[10px] text-[#bbcabf] whitespace-pre z-50 shadow-2xl rounded-none w-max max-w-xs pointer-events-none select-none">
                                                {track.score_reasons}
                                              </div>
                                            )}
                                          </td>
                                          <td className="p-2 text-[#e5e2e3] font-medium truncate" title={track.parsed_track}>{track.parsed_track || 'Unknown'}</td>
                                          <td className="p-2 font-data-mono text-data-mono uppercase">{track.format}</td>
                                          <td className="p-2 font-data-mono text-data-mono">{track.bitrate ? `${track.bitrate}k` : 'Lossless'}</td>
                                          <td className="p-2 font-data-mono text-data-mono">{formatBytes(track.size)}</td>
                                          <td className="p-2 font-data-mono text-data-mono text-[#10b981] truncate" title={track.username}>{track.username}</td>
                                          <td className="p-2 font-data-mono text-data-mono">{track.queue_length}</td>
                                          <td className="p-2 text-center">
                                            <button
                                              onClick={() => handleDownloadSingle(track)}
                                              className="p-1 text-[#bbcabf] hover:text-[#10b981] cursor-pointer"
                                            >
                                              <Download size={14} />
                                            </button>
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            /* SECTION: FLAT GRID VIEW (DEFAULT) */
            <div className="w-full h-full overflow-x-auto flex flex-col justify-between">
              <div className="overflow-auto flex-1">
                <table className="w-full text-left border-collapse whitespace-nowrap table-fixed">
                  <thead className="sticky top-0 bg-[#1c1b1c] border-b border-[#27272a] z-10 font-label-caps text-label-caps text-[#bbcabf] uppercase tracking-widest">
                    {table.getHeaderGroups().map(headerGroup => (
                      <tr key={headerGroup.id}>
                        {headerGroup.headers.map(header => (
                          <th
                            key={header.id}
                            className="p-3 border-r border-[#27272a] text-left select-none text-[11px]"
                            style={{ width: (header.column.columnDef.meta as any)?.width }}
                          >
                            {header.isPlaceholder
                              ? null
                              : flexRender(
                                  header.column.columnDef.header,
                                  header.getContext()
                                )}
                          </th>
                        ))}
                      </tr>
                    ))}
                  </thead>
                  <tbody className="font-body-md text-body-md text-[#bbcabf] divide-y divide-[#27272a]">
                    {table.getRowModel().rows.map((row, idx) => (
                      <tr
                        key={row.id}
                        className={`hover:bg-[#1c1b1c] transition-colors duration-150 group cursor-pointer border-b border-[#27272a] ${
                          idx % 2 === 1 ? 'bg-[#0e0e0f]' : 'bg-[#131314]'
                        }`}
                      >
                        {row.getVisibleCells().map(cell => (
                          <td
                            key={cell.id}
                            className="p-3 border-r border-[#27272a] last:border-0 overflow-hidden truncate"
                          >
                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination Controls */}
              <div className="bg-[#131314] border-t border-[#27272a] px-8 py-3 flex items-center justify-between shrink-0 select-none">
                <div className="flex items-center gap-2 font-data-mono text-data-mono text-xs text-[#bbcabf]">
                  <span>Page</span>
                  <strong className="text-[#e5e2e3]">
                    {table.getState().pagination.pageIndex + 1} of{' '}
                    {table.getPageCount() || 1}
                  </strong>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => table.previousPage()}
                    disabled={!table.getCanPreviousPage()}
                    className="border border-[#27272a] px-3 py-1 font-label-caps text-label-caps text-xs hover:border-[#10b981] disabled:opacity-30 disabled:hover:border-[#27272a] cursor-pointer bg-[#1c1b1c] text-[#bbcabf]"
                  >
                    PREV
                  </button>
                  <button
                    onClick={() => table.nextPage()}
                    disabled={!table.getCanNextPage()}
                    className="border border-[#27272a] px-3 py-1 font-label-caps text-label-caps text-xs hover:border-[#10b981] disabled:opacity-30 disabled:hover:border-[#27272a] cursor-pointer bg-[#1c1b1c] text-[#bbcabf]"
                  >
                    NEXT
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Refinement Inspector Sidebar (Right) */}
      <aside className="w-[280px] bg-[#131314] flex flex-col shrink-0 overflow-hidden z-30 select-none">
        <div className="p-4 border-b border-[#27272a] bg-[#1c1b1c] shrink-0 flex items-center justify-between">
          <h3 className="font-label-caps text-label-caps text-[#e5e2e3] uppercase tracking-widest flex items-center gap-1.5 font-bold">
            <Filter size={14} className="text-[#10b981]" />
            Refine Search
          </h3>
          <button
            onClick={clearFilters}
            className="text-[#bbcabf] hover:text-[#e5e2e3] transition-colors font-label-caps text-[10px] uppercase tracking-wider block cursor-pointer"
          >
            Clear All
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {/* Filter: Format */}
          <div>
            <h4 className="font-label-caps text-label-caps text-[#bbcabf] uppercase tracking-widest mb-3 border-b border-[#27272a] pb-1.5">
              Format
            </h4>
            <div className="space-y-2">
              {(['flac', 'mp3', 'wav'] as const).map((fmt) => (
                <label key={fmt} className="flex items-center gap-2 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={filters.format[fmt]}
                    onChange={() => toggleFormatFilter(fmt)}
                    className="rounded-none bg-[#0a0a0b] border-[#27272a] text-[#10b981] focus:ring-0 h-3 w-3 transition-colors cursor-pointer"
                  />
                  <span className="font-body-md text-body-md text-[#e5e2e3] group-hover:text-[#10b981] uppercase font-bold">
                    {fmt}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Filter: Bitrate */}
          <div>
            <h4 className="font-label-caps text-label-caps text-[#bbcabf] uppercase tracking-widest mb-3 border-b border-[#27272a] pb-1.5">
              Bitrate Preference
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {(['All', 'Lossless', '320kbps', 'V0 (VBR)', '256kbps'] as const).map((br) => (
                <button
                  key={br}
                  onClick={() => updateFilters({ bitrate: br })}
                  className={`font-data-mono text-data-mono px-2 py-0.5 rounded-none border transition-colors cursor-pointer ${
                    filters.bitrate === br
                      ? 'bg-[#10b981] text-[#003824] border-[#10b981] font-bold'
                      : 'bg-[#0a0a0b] text-[#bbcabf] border-[#27272a] hover:border-[#bbcabf]'
                  }`}
                >
                  {br}
                </button>
              ))}
            </div>
          </div>

          {/* Filter: Max File Size */}
          <div>
            <h4 className="font-label-caps text-label-caps text-[#bbcabf] uppercase tracking-widest mb-3 border-b border-[#27272a] pb-1.5">
              Max File Size
            </h4>
            <div className="px-1">
              <input
                type="range"
                min="10"
                max="500"
                step="10"
                value={filters.maxSize}
                onChange={(e) => updateFilters({ maxSize: parseInt(e.target.value) })}
                className="w-full h-1 bg-[#0a0a0b] rounded-none appearance-none cursor-pointer accent-[#10b981] border border-[#27272a]"
              />
              <div className="flex justify-between mt-2 font-data-mono text-data-mono text-[#bbcabf]">
                <span>10MB</span>
                <span className="text-[#10b981] font-bold">{filters.maxSize}MB</span>
              </div>
            </div>
          </div>

          {/* Filter: Queue length */}
          <div>
            <h4 className="font-label-caps text-label-caps text-[#bbcabf] uppercase tracking-widest mb-3 border-b border-[#27272a] pb-1.5">
              Queue Length
            </h4>
            <div className="space-y-2">
              {[
                { id: 'any', label: 'Any Status' },
                { id: 'empty', label: 'Empty Queue Only (0)' },
                { id: 'under5', label: '< 5 Users Ahead' },
              ].map((opt) => (
                <label key={opt.id} className="flex items-center gap-2 cursor-pointer group">
                  <input
                    type="radio"
                    name="queueLength"
                    checked={filters.queueLength === opt.id}
                    onChange={() => updateFilters({ queueLength: opt.id as any })}
                    className="bg-[#0a0a0b] border-[#27272a] text-[#10b981] focus:ring-0 h-3 w-3 cursor-pointer"
                  />
                  <span className={`font-body-md text-body-md ${
                    filters.queueLength === opt.id ? 'text-[#10b981] font-bold' : 'text-[#bbcabf]'
                  } group-hover:text-[#10b981]`}>
                    {opt.label}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Filter: Specific User */}
          <div>
            <h4 className="font-label-caps text-label-caps text-[#bbcabf] uppercase tracking-widest mb-3 border-b border-[#27272a] pb-1.5">
              Filter by User
            </h4>
            <div className="relative flex items-center">
              <input
                type="text"
                placeholder="Type peer username..."
                value={filters.username}
                onChange={(e) => updateFilters({ username: e.target.value })}
                className="w-full bg-[#0a0a0b] border border-[#27272a] text-[#e5e2e3] font-data-mono text-data-mono rounded-none px-3 py-1.5 focus:border-[#10b981] focus:outline-none"
              />
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}

// Loader mock
function Loader2({ className = '', size = 16 }) {
  return <span className={`animate-spin inline-block border-2 border-t-transparent border-[#10b981] rounded-full`} style={{ width: size, height: size }} />;
}
