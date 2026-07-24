'use client';

import React from 'react';
import { useNavigationStore } from '../store/navigationStore';
import HomeView from '../components/HomeView';
import ExploreView from '../components/ExploreView';
import SearchResultsView from '../components/SearchResultsView';
import DownloadsView from '../components/DownloadsView';
import SettingsView from '../components/SettingsView';

export default function Page() {
  const { activeTab } = useNavigationStore();

  const renderActiveView = () => {
    switch (activeTab) {
      case 'home':
        return <HomeView />;
      case 'explore':
        return <ExploreView />;
      case 'search':
        return <SearchResultsView />;
      case 'downloads':
        return <DownloadsView />;
      case 'settings':
        return <SettingsView />;
      default:
        return <HomeView />;
    }
  };

  return <div className="w-full h-full">{renderActiveView()}</div>;
}
