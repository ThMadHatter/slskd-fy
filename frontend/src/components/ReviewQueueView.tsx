'use client';

import React, { useEffect, useState } from 'react';
import { useReviewQueueStore } from '../store/reviewQueueStore';
import { MatchCandidate } from '../types/beets';
import { Check, Disc, HelpCircle, ArrowRight, ShieldAlert, Sparkles, X, ChevronRight, CornerDownLeft } from 'lucide-react';
import Button from './ui/Button';
import Card from './ui/Card';
import SonicLoader from './ui/SonicLoader';

export default function ReviewQueueView() {
  const {
    items,
    selectedItemId,
    loading,
    error,
    fetchQueue,
    selectItem,
    selectNext,
    selectPrev,
    resolveAction,
  } = useReviewQueueStore();

  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [filterQuery, setFilterQuery] = useState('');

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const activeItem = items.find((i) => i.id === selectedItemId) || items[0] || null;

  // Set default selected candidate when active item changes
  useEffect(() => {
    if (activeItem && activeItem.candidates && activeItem.candidates.length > 0) {
      setSelectedCandidateId(activeItem.candidates[0].id);
    } else {
      setSelectedCandidateId(null);
    }
  }, [activeItem?.id]);

  // Keyboard navigation hotkeys (Linear issue workflow style)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input
      if (['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) return;

      if (!activeItem) return;

      if (e.key === 'a' || e.key === 'A') {
        e.preventDefault();
        handleAccept();
      } else if (e.key === 'k' || e.key === 'K') {
        e.preventDefault();
        handleKeepOriginal();
      } else if (e.key === 'x' || e.key === 'X') {
        e.preventDefault();
        handleSkip();
      } else if (e.key === 'ArrowDown' || e.key === 'j' || e.key === 'J') {
        e.preventDefault();
        selectNext();
      } else if (e.key === 'ArrowUp' || e.key === 'k' || e.key === 'K') {
        e.preventDefault();
        selectPrev();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeItem, selectedCandidateId]);

  const filteredItems = items.filter((item) => {
    if (!filterQuery.trim()) return true;
    const q = filterQuery.toLowerCase();
    return (
      item.artist.toLowerCase().includes(q) ||
      item.track.toLowerCase().includes(q) ||
      (item.album && item.album.toLowerCase().includes(q))
    );
  });

  const handleAccept = () => {
    if (!activeItem) return;
    if (selectedCandidateId) {
      resolveAction(activeItem.id, 'select_candidate', selectedCandidateId);
    } else {
      resolveAction(activeItem.id, 'accept');
    }
  };

  const handleKeepOriginal = () => {
    if (!activeItem) return;
    resolveAction(activeItem.id, 'keep_original');
  };

  const handleSkip = () => {
    if (!activeItem) return;
    resolveAction(activeItem.id, 'skip');
  };

  if (loading && items.length === 0) {
    return (
      <div className="w-full h-[60vh] flex flex-col items-center justify-center gap-4 text-[#bbcabf] select-none">
        <SonicLoader size="large" />
        <span className="font-data-mono text-data-mono text-sm uppercase tracking-wider">
          Loading Beets Review Queue...
        </span>
      </div>
    );
  }

  return (
    <div className="w-full max-w-7xl mx-auto h-[calc(100vh-80px)] flex flex-col gap-4 pb-4 animate-fade-in-up select-none">

      {/* Top Banner Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#27272a] pb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[#1c1b1c] border border-[#27272a] flex items-center justify-center text-[#fc7c78]">
            <ShieldAlert size={20} />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <h2 className="font-headline-md text-headline-sm font-bold text-[#e5e2e3] uppercase tracking-tight">
                Beets Metadata Review Queue
              </h2>
              <span className="bg-[#fc7c78]/20 text-[#fc7c78] border border-[#fc7c78]/40 font-data-mono text-[10px] px-2 py-0.5 font-bold">
                {items.length} PENDING
              </span>
            </div>
            <p className="font-data-mono text-xs text-[#bbcabf] opacity-80 mt-0.5">
              Linear-style triage workflow for ambiguous Beets autotagging candidate matches.
            </p>
          </div>
        </div>

        {/* Hotkey legend pills */}
        <div className="hidden lg:flex items-center gap-3 font-data-mono text-[11px] text-[#bbcabf]">
          <span className="flex items-center gap-1.5 bg-[#131314] border border-[#27272a] px-2 py-1">
            <kbd className="bg-[#201f20] border border-[#27272a] px-1 text-[#10b981] font-bold">A</kbd> Accept
          </span>
          <span className="flex items-center gap-1.5 bg-[#131314] border border-[#27272a] px-2 py-1">
            <kbd className="bg-[#201f20] border border-[#27272a] px-1 text-[#e5e2e3] font-bold">K</kbd> Keep Original
          </span>
          <span className="flex items-center gap-1.5 bg-[#131314] border border-[#27272a] px-2 py-1">
            <kbd className="bg-[#201f20] border border-[#27272a] px-1 text-[#fc7c78] font-bold">X</kbd> Skip
          </span>
          <span className="flex items-center gap-1.5 bg-[#131314] border border-[#27272a] px-2 py-1">
            <kbd className="bg-[#201f20] border border-[#27272a] px-1 text-[#bbcabf] font-bold">↑/↓</kbd> Navigate
          </span>
        </div>
      </div>

      {items.length === 0 ? (
        /* Empty Queue State */
        <div className="flex-1 bg-[#131314] border border-[#27272a] flex flex-col items-center justify-center gap-3 text-center p-12">
          <div className="w-16 h-16 rounded-full bg-[#10b981]/10 border border-[#10b981]/30 flex items-center justify-center text-[#10b981]">
            <Check size={32} />
          </div>
          <h3 className="font-headline-md text-headline-sm text-[#e5e2e3] font-bold uppercase tracking-tight">
            Review Queue Clean!
          </h3>
          <p className="font-data-mono text-xs text-[#bbcabf] max-w-md">
            All completed downloads have been cleanly processed with high confidence metadata matches. No ambiguous items require review.
          </p>
        </div>
      ) : (
        /* Main Linear-Style 2-Column Split View */
        <div className="flex-1 grid grid-cols-1 md:grid-cols-12 gap-6 min-h-0 overflow-hidden">

          {/* LEFT COLUMN: Queue List (4 cols) */}
          <div className="md:col-span-4 bg-[#131314] border border-[#27272a] flex flex-col min-h-0">
            {/* Filter Search Input */}
            <div className="p-3 border-b border-[#27272a] bg-[#1c1b1c]">
              <input
                type="text"
                placeholder="Filter queue by artist or track..."
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
                className="w-full bg-[#0a0a0b] border border-[#27272a] text-xs font-data-mono text-[#e5e2e3] px-3 py-2 focus:border-[#10b981] focus:outline-none"
              />
            </div>

            {/* Queue Items Scrollable List */}
            <div className="flex-1 overflow-y-auto divide-y divide-[#27272a]/50">
              {filteredItems.map((item) => {
                const isSelected = item.id === activeItem?.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => selectItem(item.id)}
                    className={`w-full text-left p-4 flex flex-col gap-2 cursor-pointer transition-colors border-l-2 ${
                      isSelected
                        ? 'bg-[#1c1b1c] border-[#10b981] text-[#e5e2e3]'
                        : 'bg-[#131314] border-transparent text-[#bbcabf] hover:bg-[#1c1b1c]/60'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-label-caps text-[10px] text-[#bbcabf]/70 truncate max-w-[180px]">
                        {item.artist}
                      </span>
                      <span className="bg-[#fc7c78]/15 text-[#fc7c78] border border-[#fc7c78]/30 font-data-mono text-[10px] px-1.5 py-0.5 font-bold">
                        {item.confidence_score}% Match
                      </span>
                    </div>

                    <h4 className="font-body-md font-bold text-[#e5e2e3] truncate leading-tight">
                      {item.track}
                    </h4>

                    {item.album && (
                      <span className="font-data-mono text-[11px] text-[#bbcabf]/60 truncate">
                        {item.album}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* RIGHT COLUMN: Review Details Panel (8 cols) */}
          {activeItem && (
            <div className="md:col-span-8 bg-[#131314] border border-[#27272a] flex flex-col justify-between p-6 min-h-0 overflow-y-auto">

              <div className="flex flex-col gap-6">

                {/* Active Item Title Header */}
                <div className="flex flex-col gap-1 border-b border-[#27272a] pb-4">
                  <div className="flex items-center justify-between">
                    <span className="font-label-caps text-xs text-[#10b981] uppercase font-bold tracking-widest">
                      AMBIGUOUS METADATA RESOLUTION
                    </span>
                    <span className="font-data-mono text-xs text-[#bbcabf]/50">
                      ID: #{activeItem.id}
                    </span>
                  </div>
                  <h3 className="font-headline-md text-headline-md font-bold text-[#e5e2e3]">
                    {activeItem.artist} — {activeItem.track}
                  </h3>
                  <p className="font-data-mono text-xs text-[#bbcabf]/70 truncate mt-1">
                    Path: <span className="text-[#e5e2e3] select-all">{activeItem.downloaded_path}</span>
                  </p>
                </div>

                {/* Side-by-side or comparison grid */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                  {/* Card 1: Original Downloaded File */}
                  <div className="border border-[#27272a] bg-[#0a0a0b] p-4 flex flex-col gap-3">
                    <div className="flex items-center justify-between border-b border-[#27272a] pb-2">
                      <span className="font-label-caps text-xs text-[#bbcabf] uppercase font-bold">
                        Raw Download Tags
                      </span>
                      <span className="bg-[#201f20] text-[#bbcabf] font-data-mono text-[10px] px-1.5 py-0.5 border border-[#27272a]">
                        Original File
                      </span>
                    </div>

                    <div className="flex flex-col gap-2 font-data-mono text-xs">
                      <div>
                        <span className="text-[#bbcabf]/60 block text-[10px] uppercase">Artist</span>
                        <span className="text-[#e5e2e3] font-bold">{activeItem.artist}</span>
                      </div>
                      <div>
                        <span className="text-[#bbcabf]/60 block text-[10px] uppercase">Track</span>
                        <span className="text-[#e5e2e3] font-bold">{activeItem.track}</span>
                      </div>
                      <div>
                        <span className="text-[#bbcabf]/60 block text-[10px] uppercase">Album</span>
                        <span className="text-[#e5e2e3] font-bold">{activeItem.album || 'Unknown'}</span>
                      </div>
                    </div>
                  </div>

                  {/* Card 2: Confidence Evaluation */}
                  <div className="border border-[#27272a] bg-[#0a0a0b] p-4 flex flex-col gap-3">
                    <div className="flex items-center justify-between border-b border-[#27272a] pb-2">
                      <span className="font-label-caps text-xs text-[#bbcabf] uppercase font-bold">
                        Beets Autotag Assessment
                      </span>
                      <span className="bg-[#fc7c78]/20 text-[#fc7c78] font-data-mono text-[10px] px-1.5 py-0.5 font-bold border border-[#fc7c78]/40">
                        {activeItem.confidence_score}% Score
                      </span>
                    </div>

                    <p className="font-data-mono text-xs text-[#bbcabf] leading-relaxed">
                      Beets detected multiple candidate releases with sub-threshold similarity scores. Manual triage is required to confirm the canonical MusicBrainz release.
                    </p>
                  </div>
                </div>

                {/* Candidate Matches Selector list */}
                <div className="flex flex-col gap-3">
                  <h4 className="font-label-caps text-xs text-[#e5e2e3] font-bold uppercase tracking-wider">
                    Select Best Beets Match Candidate ({activeItem.candidates.length} Found)
                  </h4>

                  <div className="flex flex-col gap-2">
                    {activeItem.candidates.map((cand) => {
                      const isCandSelected = cand.id === selectedCandidateId;
                      return (
                        <div
                          key={cand.id}
                          onClick={() => setSelectedCandidateId(cand.id)}
                          className={`p-4 border cursor-pointer transition-all flex flex-col gap-2 ${
                            isCandSelected
                              ? 'bg-[#1c1b1c] border-[#10b981] shadow-lg'
                              : 'bg-[#0a0a0b] border-[#27272a] hover:border-[#bbcabf]/50'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <div className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                                isCandSelected ? 'border-[#10b981] bg-[#10b981]' : 'border-[#3f3f46]'
                              }`}>
                                {isCandSelected && <div className="w-1.5 h-1.5 rounded-full bg-[#0a0a0b]" />}
                              </div>
                              <span className="font-body-md font-bold text-[#e5e2e3]">
                                {cand.title}
                              </span>
                            </div>

                            <span className={`font-data-mono text-xs font-bold px-2 py-0.5 ${
                              cand.confidence >= 85
                                ? 'bg-[#10b981]/20 text-[#10b981] border border-[#10b981]/40'
                                : 'bg-[#fc7c78]/20 text-[#fc7c78] border border-[#fc7c78]/40'
                            }`}>
                              {cand.confidence}% Match
                            </span>
                          </div>

                          <div className="flex flex-wrap items-center gap-4 text-xs font-data-mono text-[#bbcabf] ml-6">
                            <span>Artist: <strong className="text-[#e5e2e3]">{cand.artist}</strong></span>
                            <span>Year: <strong className="text-[#e5e2e3]">{cand.year}</strong></span>
                            <span>Format: <strong className="text-[#10b981]">{cand.format}</strong></span>
                            <span>Tracks: <strong className="text-[#e5e2e3]">{cand.track_count}</strong></span>
                            {cand.mbid && (
                              <span className="text-[10px] opacity-60 truncate">
                                MBID: {cand.mbid}
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Linear-Style Fixed Action Bar */}
              <div className="flex flex-wrap items-center justify-between gap-4 border-t border-[#27272a] pt-6 mt-6 select-none">
                <div className="flex items-center gap-3">
                  <Button
                    onClick={handleAccept}
                    variant="primary"
                    className="font-bold uppercase tracking-wider"
                  >
                    <Check size={16} />
                    ACCEPT MATCH
                    <span className="font-data-mono text-[10px] border border-current px-1 ml-1 opacity-80">A</span>
                  </Button>

                  <Button
                    onClick={handleKeepOriginal}
                    variant="secondary"
                    className="font-bold border-[#27272a]"
                  >
                    KEEP ORIGINAL TAGS
                    <span className="font-data-mono text-[10px] border border-current px-1 ml-1 opacity-60">K</span>
                  </Button>
                </div>

                <button
                  onClick={handleSkip}
                  className="text-xs font-data-mono text-[#bbcabf] hover:text-[#fc7c78] transition-colors cursor-pointer flex items-center gap-1.5 px-3 py-2 border border-[#27272a] hover:border-[#fc7c78]"
                >
                  <X size={14} /> SKIP ITEM <span className="text-[10px] border border-current px-1 opacity-60">X</span>
                </button>
              </div>

            </div>
          )}

        </div>
      )}
    </div>
  );
}
