'use client';

import React, { useState, useEffect } from 'react';
import { useSearchStore } from '../store/searchStore';
import { useNavigationStore } from '../store/navigationStore';
import { useQuery } from '@tanstack/react-query';
import { Search, User, Music, HelpCircle, CornerDownLeft, Loader2, Compass } from 'lucide-react';
import Button from './ui/Button';
import Input from './ui/Input';
import Card from './ui/Card';
import Kbd from './ui/Kbd';

export default function HomeView() {
  const { setActiveTab } = useNavigationStore();
  const {
    artist,
    track,
    searchMode,
    setArtist,
    setTrack,
    setSearchMode,
    setResults,
    setIsSearching,
  } = useSearchStore();

  const [searchType, setSearchType] = useState<'structured' | 'keyword'>('structured');
  const [keywordQuery, setKeywordQuery] = useState('');
  const [artistInput, setArtistInput] = useState(artist);
  const [trackInput, setTrackInput] = useState(track);
  const [showArtistDropdown, setShowArtistDropdown] = useState(false);
  const [showTrackDropdown, setShowTrackDropdown] = useState(false);

  const [debouncedArtist, setDebouncedArtist] = useState('');
  const [debouncedTrack, setDebouncedTrack] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedArtist(artistInput), 300);
    return () => clearTimeout(timer);
  }, [artistInput]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedTrack(trackInput), 300);
    return () => clearTimeout(timer);
  }, [trackInput]);

  const { data: artistSuggestions = [], isFetching: isArtistFetching } = useQuery({
    queryKey: ['autocompleteArtist', debouncedArtist],
    queryFn: async () => {
      if (debouncedArtist.trim().length < 2) return [];
      const res = await fetch(`/api/autocomplete/artist?q=${encodeURIComponent(debouncedArtist)}`);
      if (!res.ok) return [];
      return res.json();
    },
    enabled: debouncedArtist.trim().length >= 2,
  });

  const { data: trackSuggestions = [], isFetching: isTrackFetching } = useQuery({
    queryKey: ['autocompleteTrack', debouncedArtist, debouncedTrack],
    queryFn: async () => {
      if (debouncedTrack.trim().length < 2) return [];
      const res = await fetch(
        `/api/autocomplete/track?artist_name=${encodeURIComponent(debouncedArtist)}&q=${encodeURIComponent(debouncedTrack)}`
      );
      if (!res.ok) return [];
      return res.json();
    },
    enabled: debouncedTrack.trim().length >= 2 && debouncedArtist.trim().length > 0,
  });

  const handleSearchExecute = async () => {
    const searchArtist = searchType === 'structured' ? artistInput.trim() : '';
    const searchTrack = searchType === 'structured' ? trackInput.trim() : keywordQuery.trim();

    if (!searchArtist && !searchTrack) return;

    setArtist(searchArtist);
    setTrack(searchTrack);
    setIsSearching(true);
    setResults([]);
    setActiveTab('search');

    try {
      const response = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          artist: searchArtist,
          track_or_album: searchTrack,
          mode: searchMode,
        }),
      });

      if (!response.ok) throw new Error('Search failed');
      const data = await response.json();
      setResults(data.results || []);
    } catch (error) {
      console.error(error);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col gap-8 animate-fade-in-up mt-8">
      {/* Title Header */}
      <div className="text-center md:text-left select-none mb-2">
        <h2 className="font-headline-lg text-headline-lg font-bold text-[#e5e2e3] tracking-tight uppercase">
          Sonic Database Search
        </h2>
        <p className="font-data-mono text-data-mono text-[#bbcabf] opacity-80 mt-1">
          High-performance Soulseek metadata querying engine.
        </p>
      </div>

      {/* Command Card container */}
      <div className="bg-[#131314] border border-[#27272a] rounded-none flex flex-col">
        {/* Tab Selector Molecules */}
        <div className="flex border-b border-[#27272a] select-none">
          <button
            onClick={() => setSearchType('structured')}
            className={`flex-1 py-3 text-center font-label-caps text-label-caps tracking-widest cursor-pointer transition-colors ${
              searchType === 'structured'
                ? 'bg-[#1c1b1c] text-[#10b981] border-b-2 border-[#10b981]'
                : 'text-[#bbcabf] hover:text-[#e5e2e3] hover:bg-[#1c1b1c]'
            }`}
          >
            Structured Query
          </button>
          <button
            onClick={() => setSearchType('keyword')}
            className={`flex-1 py-3 text-center font-label-caps text-label-caps tracking-widest cursor-pointer transition-colors ${
              searchType === 'keyword'
                ? 'bg-[#1c1b1c] text-[#10b981] border-b-2 border-[#10b981]'
                : 'text-[#bbcabf] hover:text-[#e5e2e3] hover:bg-[#1c1b1c]'
            }`}
          >
            Free Text Keywords
          </button>
        </div>

        {/* Input Fields Body */}
        <div className="p-6 flex flex-col gap-6 relative">
          {searchType === 'structured' ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Artist Search input atom */}
              <div className="relative">
                <label className="block font-label-caps text-label-caps text-[#bbcabf] mb-2 uppercase">
                  Artist Name
                </label>
                <div className="relative flex items-center">
                  <Input
                    icon={User}
                    placeholder="e.g. Aphex Twin"
                    value={artistInput}
                    onChange={(e) => {
                      setArtistInput(e.target.value);
                      setShowArtistDropdown(true);
                    }}
                    onFocus={() => setShowArtistDropdown(true)}
                    onBlur={() => setTimeout(() => setShowArtistDropdown(false), 200)}
                  />
                  {isArtistFetching && (
                    <Loader2 size={16} className="absolute right-3 text-[#10b981] animate-spin" />
                  )}
                </div>

                {/* Autocomplete Dropdown */}
                {showArtistDropdown && artistSuggestions.length > 0 && (
                  <ul className="absolute left-0 right-0 mt-1 bg-[#131314] border border-[#27272a] z-50 flex flex-col divide-y divide-[#27272a] max-h-60 overflow-y-auto rounded-none shadow-2xl">
                    {artistSuggestions.map((item: any) => (
                      <li key={item.id}>
                        <button
                          onMouseDown={() => {
                            setArtistInput(item.name);
                            setShowArtistDropdown(false);
                          }}
                          className="w-full text-left px-4 py-2.5 hover:bg-[#1c1b1c] text-[#bbcabf] hover:text-[#e5e2e3] font-data-mono text-data-mono flex items-center justify-between cursor-pointer"
                        >
                          <span className="font-semibold text-[#e5e2e3]">{item.name}</span>
                          <span className="text-[10px] text-[#bbcabf]/50 border border-[#27272a] px-1.5 py-0.5">
                            {item.disambiguation || 'Artist'}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Track Search input atom */}
              <div className="relative">
                <label className="block font-label-caps text-label-caps text-[#bbcabf] mb-2 uppercase">
                  Track or Album
                </label>
                <div className="relative flex items-center">
                  <Input
                    icon={Music}
                    placeholder="e.g. Selected Ambient Works"
                    value={trackInput}
                    onChange={(e) => {
                      setTrackInput(e.target.value);
                      setShowTrackDropdown(true);
                    }}
                    onFocus={() => setShowTrackDropdown(true)}
                    onBlur={() => setTimeout(() => setShowTrackDropdown(false), 200)}
                    disabled={!artistInput.trim()}
                  />
                  {isTrackFetching && (
                    <Loader2 size={16} className="absolute right-3 text-[#10b981] animate-spin" />
                  )}
                </div>

                {/* Autocomplete Dropdown */}
                {showTrackDropdown && trackSuggestions.length > 0 && (
                  <ul className="absolute left-0 right-0 mt-1 bg-[#131314] border border-[#27272a] z-50 flex flex-col divide-y divide-[#27272a] max-h-60 overflow-y-auto rounded-none shadow-2xl">
                    {trackSuggestions.map((item: any) => (
                      <li key={item.id}>
                        <button
                          onMouseDown={() => {
                            setTrackInput(item.title);
                            setShowTrackDropdown(false);
                          }}
                          className="w-full text-left px-4 py-2.5 hover:bg-[#1c1b1c] text-[#bbcabf] hover:text-[#e5e2e3] font-data-mono text-data-mono flex items-center justify-between cursor-pointer"
                        >
                          <div className="flex flex-col">
                            <span className="font-semibold text-[#e5e2e3]">{item.title}</span>
                            <span className="text-[11px] text-[#bbcabf]/50">{item.album}</span>
                          </div>
                          {item.year && (
                            <span className="text-[10px] text-[#bbcabf]/50 border border-[#27272a] px-1.5 py-0.5">
                              {item.year}
                            </span>
                          )}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ) : (
            <div className="relative">
              <label className="block font-label-caps text-label-caps text-[#bbcabf] mb-2 uppercase">
                Raw Search String
              </label>
              <Input
                icon={Search}
                placeholder="e.g. Aphex Twin selected ambient works flac 1992"
                value={keywordQuery}
                onChange={(e) => setKeywordQuery(e.target.value)}
              />
            </div>
          )}

          {/* Form Actions footer */}
          <div className="flex flex-wrap items-center justify-between gap-4 border-t border-[#27272a] pt-6 select-none">
            {/* Mode selection buttons */}
            <div className="flex items-center gap-2">
              <span className="font-label-caps text-label-caps text-[#bbcabf]/70 uppercase">Strategy:</span>
              <div className="flex bg-[#0a0a0b] border border-[#27272a]">
                {(['A', 'B', 'C'] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setSearchMode(mode)}
                    className={`px-3 py-1.5 font-data-mono text-data-mono transition-colors cursor-pointer border-r border-[#27272a] last:border-0 ${
                      searchMode === mode
                        ? 'bg-[#201f20] text-[#10b981] font-bold'
                        : 'text-[#bbcabf] hover:text-[#e5e2e3]'
                    }`}
                  >
                    {mode === 'A' ? 'Mode A' : mode === 'B' ? 'Mode B' : 'Mode C'}
                  </button>
                ))}
              </div>
            </div>

            {/* Submit button atom */}
            <Button onClick={handleSearchExecute} variant="primary">
              EXECUTE SEARCH
              <CornerDownLeft size={14} />
            </Button>
          </div>
        </div>
      </div>

      {/* Network suggestions using Card molecules */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 select-none mt-4">
        {/* Popular Network Queries */}
        <Card className="flex flex-col gap-4">
          <h3 className="font-label-caps text-label-caps text-[#bbcabf] flex items-center justify-between border-b border-[#27272a] pb-2 uppercase tracking-wider">
            Popular Network Queries
            <Compass size={14} className="text-[#10b981]" />
          </h3>
          <div className="flex flex-col gap-3">
            {[
              { label: 'ARTIST', value: 'Burial' },
              { label: 'ALBUM', value: 'Untrue' },
              { label: 'TRACK', value: 'Archangel' },
            ].map((q, idx) => (
              <button
                key={idx}
                onClick={() => {
                  if (q.label === 'ARTIST') {
                    setArtistInput(q.value);
                  } else {
                    setTrackInput(q.value);
                  }
                  setSearchType('structured');
                }}
                className="border border-[#27272a] p-4 hover:border-[#10b981] transition-all duration-150 cursor-pointer text-left bg-[#0a0a0b] group flex flex-col gap-1 rounded-none"
              >
                <span className="font-label-caps text-[10px] text-[#bbcabf]/50 group-hover:text-[#10b981] transition-colors">
                  {q.label}
                </span>
                <span className="font-data-mono text-data-mono text-[#e5e2e3] truncate">
                  {q.value}
                </span>
              </button>
            ))}
          </div>
        </Card>

        {/* Technical Guidelines */}
        <Card className="flex flex-col gap-4">
          <h3 className="font-label-caps text-label-caps text-[#bbcabf] border-b border-[#27272a] pb-2 uppercase tracking-wider flex items-center justify-between">
            Technical Guidelines
            <HelpCircle size={14} className="text-[#10b981]" />
          </h3>
          <ul className="flex flex-col gap-4 font-body-md text-[#bbcabf] text-sm leading-relaxed">
            <li className="flex gap-3">
              <span className="font-data-mono text-[#10b981] font-bold select-none shrink-0">01</span>
              <span><strong>Universal Search:</strong> Search by entering both fields or query for broad keywords like catalogs or labels directly.</span>
            </li>
            <li className="flex gap-3">
              <span className="font-data-mono text-[#10b981] font-bold select-none shrink-0">02</span>
              <span><strong>Strategy Modes:</strong> Mode A is progressive keywords, Mode B exact quotes for perfect fits, and Mode C is prefixed Lucene format fields for power users.</span>
            </li>
            <li className="flex gap-3">
              <span className="font-data-mono text-[#10b981] font-bold select-none shrink-0">03</span>
              <span><strong>Autocompletion:</strong> Artist suggestions are generated via local database cache fallbacks and MusicBrainz live indexes instantly.</span>
            </li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
