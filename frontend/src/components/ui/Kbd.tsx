import React from 'react';

interface KbdProps {
  children: React.ReactNode;
  className?: string;
}

export default function Kbd({ children, className = '' }: KbdProps) {
  return (
    <kbd className={`font-data-mono text-[10px] text-[#bbcabf]/70 bg-[#131314] border border-[#27272a] px-1.5 py-0.5 select-none leading-none rounded-none shadow-sm ${className}`}>
      {children}
    </kbd>
  );
}
