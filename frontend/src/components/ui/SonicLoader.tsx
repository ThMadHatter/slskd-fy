'use client';

import React from 'react';

export interface SonicLoaderProps {
  size?: 'small' | 'medium' | 'large';
  className?: string;
  label?: string;
  color?: string;
  accentColor?: string;
}

export default function SonicLoader({
  size = 'medium',
  className = '',
  label = 'Caricamento in corso',
  color,
  accentColor,
}: SonicLoaderProps) {
  // Dimensions per size
  const config = {
    small: { height: 16, barWidth: 2.5, gap: 2.5 },
    medium: { height: 24, barWidth: 4, gap: 4 },
    large: { height: 36, barWidth: 6, gap: 5 },
  }[size];

  const delays = [-0.4, -0.32, -0.24, -0.16, -0.08, 0, 0.08, 0.16, 0.24];

  return (
    <span
      role="status"
      aria-label={label}
      className={`inline-flex items-center justify-center shrink-0 ${className}`}
      style={{
        gap: `${config.gap}px`,
        height: `${config.height}px`,
      }}
    >
      <style>{`
        @keyframes sonic-loader-wave {
          0%, 100% {
            transform: scaleY(0.25);
            opacity: 0.45;
          }
          50% {
            transform: scaleY(1);
            opacity: 1;
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .sonic-loader-bar-anim {
            animation: none !important;
            transform: scaleY(0.55) !important;
            opacity: 0.85 !important;
          }
          .sonic-loader-bar-anim:nth-child(even) {
            transform: scaleY(0.9) !important;
          }
        }
      `}</style>

      {delays.map((delay, index) => {
        const isAccent = index >= 7;
        const barBg = isAccent
          ? accentColor || '#FC7C78'
          : color || '#10B981';
        const barShadow = isAccent
          ? '0 0 8px rgba(252, 124, 120, 0.22)'
          : '0 0 8px rgba(16, 185, 129, 0.25)';

        return (
          <span
            key={index}
            aria-hidden="true"
            className="sonic-loader-bar-anim inline-block rounded-full"
            style={{
              width: `${config.barWidth}px`,
              height: '100%',
              backgroundColor: barBg,
              boxShadow: barShadow,
              transform: 'scaleY(0.25)',
              transformOrigin: 'center',
              animation: 'sonic-loader-wave 1s ease-in-out infinite',
              animationDelay: `${delay}s`,
            }}
          />
        );
      })}
    </span>
  );
}
