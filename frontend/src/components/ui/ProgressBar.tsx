import React from 'react';

interface ProgressBarProps {
  progress: number; // 0 to 100
  className?: string;
  animateStripe?: boolean;
}

export default function ProgressBar({ progress, className = '', animateStripe = false }: ProgressBarProps) {
  return (
    <div className={`w-full h-1 bg-[#201f20] border border-[#27272a] overflow-hidden rounded-none ${className}`}>
      <div
        className={`h-full bg-[#10b981] transition-all duration-300 ${
          animateStripe ? 'progress-bar-stripe' : ''
        }`}
        style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
      ></div>
    </div>
  );
}
