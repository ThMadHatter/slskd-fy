import { useEffect, useRef } from 'react';
import { useNavigationStore, TabType } from '../store/navigationStore';

export function useHotkeys() {
  const { setActiveTab, toggleCommandPalette, setCommandPaletteOpen } = useNavigationStore();
  const lastKeyRef = useRef<string | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isCmdOrCtrl = e.metaKey || e.ctrlKey;
      const key = e.key.toLowerCase();

      const activeElement = document.activeElement;
      const isTyping = activeElement && (
        activeElement.tagName === 'INPUT' ||
        activeElement.tagName === 'TEXTAREA' ||
        activeElement.getAttribute('contenteditable') === 'true'
      );

      if (isCmdOrCtrl && key === 'k') {
        e.preventDefault();
        toggleCommandPalette();
        return;
      }

      if (e.key === 'Escape') {
        setCommandPaletteOpen(false);
        return;
      }

      if (isCmdOrCtrl && ['1', '2', '3', '4', '5'].includes(e.key)) {
        e.preventDefault();
        const tabMap: Record<string, TabType> = {
          '1': 'home',
          '2': 'explore',
          '3': 'search',
          '4': 'downloads',
          '5': 'settings',
        };
        setActiveTab(tabMap[e.key]);
        return;
      }

      if (!isTyping && !isCmdOrCtrl) {
        if (lastKeyRef.current === 'g') {
          const sequenceTabMap: Record<string, TabType> = {
            'h': 'home',
            'e': 'explore',
            's': 'search',
            'd': 'downloads',
            ',': 'settings',
          };
          if (key in sequenceTabMap) {
            e.preventDefault();
            setActiveTab(sequenceTabMap[key]);
            lastKeyRef.current = null;
            return;
          }
        }

        if (key === 'g') {
          lastKeyRef.current = 'g';
          if (timeoutRef.current) clearTimeout(timeoutRef.current);
          timeoutRef.current = setTimeout(() => {
            lastKeyRef.current = null;
          }, 1000);
          return;
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [setActiveTab, toggleCommandPalette, setCommandPaletteOpen]);
}
