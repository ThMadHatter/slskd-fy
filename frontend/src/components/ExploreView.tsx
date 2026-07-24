'use client';

import React from 'react';
import { useSearchStore } from '../store/searchStore';
import { useNavigationStore } from '../store/navigationStore';
import { useDownloadStore } from '../store/downloadStore';
import { Disc, Users, GitFork, CheckSquare, Sparkles, FolderSync, Search, Download } from 'lucide-react';
import Card from './ui/Card';
import Button from './ui/Button';

export default function ExploreView() {
  const { setArtist, setTrack, setIsSearching, setResults } = useSearchStore();
  const { setActiveTab } = useNavigationStore();
  const { addDownload } = useDownloadStore();

  const handleQuickSearch = async (artistName: string, trackName: string) => {
    setArtist(artistName);
    setTrack(trackName);
    setIsSearching(true);
    setResults([]);
    setActiveTab('search');

    try {
      const response = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ artist: artistName, track_or_album: trackName }),
      });
      if (response.ok) {
        const data = await response.json();
        setResults(data.results || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsSearching(false);
    }
  };

  const handleQuickDownload = (filename: string, username: string, size: number) => {
    addDownload({
      filename,
      username,
      status: 'queued',
      size,
    });
  };

  return (
    <div className="w-full max-w-5xl mx-auto flex flex-col gap-12 pb-32 animate-fade-in-up mt-4 select-none">

      {/* 1. Trending Albums */}
      <section className="flex flex-col gap-4">
        <div className="flex items-center justify-between border-b border-[#27272a] pb-2">
          <div className="flex items-center gap-2">
            <Disc className="text-[#10b981]" size={20} />
            <h2 className="font-headline-md text-headline-md font-bold text-[#e5e2e3] tracking-tight">
              Trending Albums
            </h2>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 auto-rows-[280px]">
          {/* Featured Large Span Card */}
          <div className="col-span-1 md:col-span-2 row-span-2 group relative overflow-hidden border border-[#27272a] bg-[#131314] flex flex-col">
            <div className="absolute inset-0 bg-gradient-to-t from-[#0a0a0b] via-[#0a0a0b]/80 to-transparent z-10"></div>
            <div className="absolute inset-0 w-full h-full bg-[#1c1b1c] opacity-60 group-hover:opacity-85 group-hover:scale-105 transition-all duration-500 flex items-center justify-center">
              <span className="font-data-mono text-data-mono text-[#bbcabf]/20 uppercase text-8xl tracking-tighter">ARCHIVE</span>
            </div>
            <div className="relative z-20 mt-auto p-6 flex flex-col gap-2">
              <div className="flex items-center gap-2 mb-2">
                <span className="bg-[#10b981] text-[#003824] font-label-caps text-label-caps px-2 py-0.5 font-bold">
                  Highest Seeders
                </span>
                <span className="bg-[#1c1b1c] text-[#10b981] font-data-mono text-data-mono border border-[#27272a] px-1.5 py-0.5">
                  FLAC 24-bit/96kHz
                </span>
              </div>
              <h3 className="font-headline-lg text-headline-lg text-[#e5e2e3] font-bold leading-none">
                Architectural Silence
              </h3>
              <p className="font-body-lg text-body-lg text-[#bbcabf]">
                Autechre & Ryoji Ikeda
              </p>
              <div className="flex gap-2 mt-2">
                <span className="font-data-mono text-data-mono text-[#bbcabf]/60 border border-[#27272a] px-1.5 py-0.5">2024</span>
                <span className="font-data-mono text-data-mono text-[#bbcabf]/60 border border-[#27272a] px-1.5 py-0.5">IDM</span>
                <span className="font-data-mono text-data-mono text-[#bbcabf]/60 border border-[#27272a] px-1.5 py-0.5">1.2 GB</span>
              </div>
              <Button
                onClick={() => handleQuickSearch('Autechre', 'Architectural Silence')}
                variant="primary"
                className="mt-6 w-max font-bold"
              >
                <Search size={14} />
                Explore Album
                <span className="font-data-mono text-[10px] border border-current px-1 ml-2 opacity-70">⏎</span>
              </Button>
            </div>
          </div>

          {/* Standard Album Card 1 */}
          <div className="border border-[#27272a] bg-[#1c1b1c] rounded-none p-4 flex flex-col justify-between hover:border-[#10b981] transition-colors group relative">
            <div className="relative w-full aspect-square bg-[#131314] overflow-hidden flex items-center justify-center">
              <span className="font-data-mono text-data-mono text-[#bbcabf]/10 uppercase text-3xl font-bold">BASS</span>
              <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                <Button
                  onClick={() => handleQuickSearch('Various Artists', 'Sub-Bass Frequencies')}
                  variant="secondary"
                  className="font-bold border-[#27272a]"
                >
                  <Search size={14} /> Explore
                </Button>
              </div>
            </div>
            <div className="flex flex-col mt-4">
              <h4 className="font-body-lg text-body-lg font-semibold text-[#e5e2e3] truncate">Sub-Bass Frequencies</h4>
              <p className="font-body-md text-body-md text-[#bbcabf]/75 truncate">Various Artists</p>
              <div className="flex items-center justify-between mt-3 border-t border-[#27272a] pt-2 select-none">
                <span className="font-data-mono text-data-mono text-[#e5e2e3] font-bold">FLAC</span>
                <span className="font-data-mono text-data-mono text-[#10b981] font-bold">842 Seeders</span>
              </div>
            </div>
          </div>

          {/* Standard Album Card 2 */}
          <div className="border border-[#27272a] bg-[#1c1b1c] rounded-none p-4 flex flex-col justify-between hover:border-[#10b981] transition-colors group relative">
            <div className="relative w-full aspect-square bg-[#131314] overflow-hidden flex items-center justify-center">
              <span className="font-data-mono text-data-mono text-[#bbcabf]/10 uppercase text-3xl font-bold">DECAY</span>
              <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                <Button
                  onClick={() => handleQuickSearch('Tape Loop Orchestra', 'Analog Decay Vol. 2')}
                  variant="secondary"
                  className="font-bold border-[#27272a]"
                >
                  <Search size={14} /> Explore
                </Button>
              </div>
            </div>
            <div className="flex flex-col mt-4">
              <h4 className="font-body-lg text-body-lg font-semibold text-[#e5e2e3] truncate">Analog Decay Vol. 2</h4>
              <p className="font-body-md text-body-md text-[#bbcabf]/75 truncate">Tape Loop Orchestra</p>
              <div className="flex items-center justify-between mt-3 border-t border-[#27272a] pt-2 select-none">
                <span className="font-data-mono text-data-mono text-[#e5e2e3] font-bold">V0 MP3</span>
                <span className="font-data-mono text-data-mono text-[#10b981] font-bold">512 Seeders</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Trending Artists */}
      <section className="flex flex-col gap-4">
        <div className="flex items-center justify-between border-b border-[#27272a] pb-2">
          <div className="flex items-center gap-2">
            <Users className="text-[#10b981]" size={20} />
            <h2 className="font-headline-md text-headline-md font-bold text-[#e5e2e3] tracking-tight">
              Trending Artists
            </h2>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
          {[
            { name: 'Aphex Twin', match: '98% Match', hotkey: 'A 1' },
            { name: 'Boards of Canada', match: '92% Match', hotkey: 'A 2' },
            { name: 'Squarepusher', match: '89% Match', hotkey: 'A 3' },
          ].map((art) => (
            <Card key={art.name} onClick={() => handleQuickSearch(art.name, '')} className="flex flex-col gap-4">
              <div className="flex justify-between items-start">
                <div className="w-12 h-12 bg-[#201f20] border border-[#27272a] flex items-center justify-center font-bold font-data-mono text-md text-[#bbcabf]">
                  {art.name[0]}
                </div>
                <span className="font-data-mono text-data-mono text-[#003824] bg-[#10b981] px-2 py-0.5 border border-[#10b981] font-bold text-xs rounded-none">
                  {art.match}
                </span>
              </div>
              <div className="flex flex-col">
                <span className="font-body-lg font-bold text-[#e5e2e3] truncate">{art.name}</span>
                <div className="text-left font-label-caps text-label-caps text-[#bbcabf] hover:text-[#10b981] mt-3 flex items-center justify-between w-full transition-colors group/btn">
                  <span className="flex items-center gap-1.5"><Search size={14} /> Discography</span>
                  <span className="font-data-mono text-[10px] border border-[#27272a] px-1 opacity-0 group-hover/btn:opacity-100 transition-opacity">
                    {art.hotkey}
                  </span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* 3. Similar Artists Network */}
      <section className="flex flex-col gap-4">
        <div className="flex items-center justify-between border-b border-[#27272a] pb-2">
          <div className="flex items-center gap-2">
            <GitFork className="text-[#10b981]" size={20} />
            <h2 className="font-headline-md text-headline-md font-bold text-[#e5e2e3] tracking-tight">
              Similar Artists Network
            </h2>
          </div>
        </div>
        <div className="flex flex-wrap gap-4 select-none">
          {[
            { name: 'Plastikman', similarity: '85%' },
            { name: 'Alva Noto', similarity: '81%' },
            { name: 'Biosphere', similarity: '78%' },
            { name: 'Robert Henke', similarity: '75%' },
          ].map((node) => (
            <Card
              key={node.name}
              onClick={() => handleQuickSearch(node.name, '')}
              className="flex items-center gap-4 p-4 min-w-[220px] pr-12 relative group"
            >
              <div className="w-10 h-10 bg-[#1c1b1c] border border-[#27272a] flex items-center justify-center text-xs font-bold text-[#bbcabf]">
                {node.name.substr(0, 2).toUpperCase()}
              </div>
              <div className="flex flex-col">
                <span className="font-body-md font-bold text-[#e5e2e3]">{node.name}</span>
                <span className="font-data-mono text-data-mono text-[#10b981] font-bold text-xs">Match: {node.similarity}</span>
              </div>
              <Search size={14} className="absolute right-4 text-[#bbcabf] opacity-0 group-hover:opacity-100 transition-opacity" />
            </Card>
          ))}
        </div>
      </section>

      {/* 4. Rediscover Collection */}
      <section className="flex flex-col gap-4">
        <div className="flex items-center justify-between border-b border-[#27272a] pb-2">
          <div className="flex items-center gap-2">
            <Sparkles className="text-[#10b981]" size={20} />
            <h2 className="font-headline-md text-headline-md font-bold text-[#e5e2e3] tracking-tight">
              Rediscover Collection
            </h2>
          </div>
        </div>
        <Card className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-6">
            <div className="w-16 h-14 bg-[#201f20] border border-[#27272a] flex items-center justify-center font-bold text-[#e5e2e3]">SAW</div>
            <div className="flex flex-col">
              <span className="font-label-caps text-label-caps text-[#10b981] font-bold mb-1">RANDOM PICK FROM LIBRARY</span>
              <h3 className="font-headline-sm text-headline-sm text-[#e5e2e3] font-bold leading-tight">Selected Ambient Works 85-92</h3>
              <p className="font-body-md text-[#bbcabf] mt-1">Aphex Twin</p>
            </div>
          </div>
          <Button
            onClick={() => handleQuickSearch('Aphex Twin', 'Selected Ambient Works 85-92')}
            variant="secondary"
            className="font-bold border-[#27272a]"
          >
            <Search size={14} /> Search for missing tracks
          </Button>
        </Card>
      </section>

      {/* 5. Global Index Additions Table */}
      <section className="flex flex-col gap-4">
        <div className="flex items-center justify-between border-b border-[#27272a] pb-2">
          <div className="flex items-center gap-2">
            <FolderSync className="text-[#10b981]" size={20} />
            <h2 className="font-headline-md text-headline-md font-bold text-[#e5e2e3] tracking-tight">
              Global Index Additions
            </h2>
          </div>
        </div>
        <div className="border border-[#27272a] bg-[#131314] flex flex-col font-data-mono text-data-mono text-[#bbcabf]">
          <div className="flex items-center p-3 border-b border-[#27272a] bg-[#1c1b1c] font-label-caps text-label-caps text-[#bbcabf]/70 text-xs">
            <div className="flex-1 px-3">Path / Metadata</div>
            <div className="w-32 px-3 hidden md:block">Format</div>
            <div className="w-24 px-3 text-right hidden lg:block">Size</div>
            <div className="w-24 px-3 text-right">Seeders</div>
            <div className="w-24 text-right pr-4">Actions</div>
          </div>

          {[
            {
              path: '/mnt/audio/aphex_twin/saw8592/',
              title: 'Selected Ambient Works 85-92',
              fmt: 'FLAC 16/44.1',
              size: 428 * 1024 * 1024,
              seeders: '1,204',
            },
            {
              path: '/mnt/audio/boc/mhtrtc/',
              title: 'Music Has the Right to Children',
              fmt: 'MP3 320k',
              size: 164 * 1024 * 1024,
              seeders: '892',
            },
          ].map((item, idx) => (
            <div
              key={idx}
              className={`flex items-center p-3 border-b border-[#27272a]/40 last:border-0 hover:bg-[#1c1b1c] transition-colors group ${
                idx % 2 === 1 ? 'bg-[#0e0e0f]' : 'bg-[#131314]'
              }`}
            >
              <div className="flex-1 px-3 flex flex-col select-all">
                <span className="text-[#e5e2e3] font-body-md font-bold">{item.title}</span>
                <span className="text-xs opacity-60 text-[#bbcabf] font-light mt-0.5">{item.path}</span>
              </div>
              <div className="w-32 px-3 hidden md:block font-bold text-[#10b981]">{item.fmt}</div>
              <div className="w-24 px-3 text-right hidden lg:block text-[#e5e2e3]">{formatBytes(item.size)}</div>
              <div className="w-24 px-3 text-right font-bold text-[#10b981]">{item.seeders}</div>
              <div className="w-24 flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity pr-4">
                <button
                  onClick={() => handleQuickSearch(item.title, '')}
                  className="p-1 hover:text-[#10b981] cursor-pointer"
                  title="Search"
                >
                  <Search size={16} />
                </button>
                <button
                  onClick={() => handleQuickDownload(`${item.title}.zip`, 'peer_server', item.size)}
                  className="p-1 hover:text-[#10b981] cursor-pointer"
                  title="Download"
                >
                  <Download size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function formatBytes(bytes: number) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
