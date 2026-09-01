'use client';

import React, { useId } from 'react';

interface SonicLogoProps {
  size?: number | string;
  className?: string;
  title?: string;
  'aria-label'?: string;
  animated?: boolean;
}

export default function SonicLogo({
  size = 34,
  className = '',
  title,
  'aria-label': ariaLabel,
  animated = false,
}: SonicLogoProps) {
  const rawId = useId().replace(/:/g, '');
  const shellId = `sonicLogoShell_${rawId}`;
  const coneId = `sonicLogoCone_${rawId}`;
  const capId = `sonicLogoCap_${rawId}`;
  const glowId = `sonicLogoGlow_${rawId}`;

  const hasLabel = Boolean(title || ariaLabel);

  return (
    <svg
      viewBox="0 0 44 44"
      width={size}
      height={size}
      className={`shrink-0 ${className}`}
      aria-hidden={!hasLabel}
      aria-label={ariaLabel || title}
      role={hasLabel ? 'img' : undefined}
    >
      {title && <title>{title}</title>}
      <defs>
        <radialGradient id={shellId} cx="36%" cy="30%" r="80%">
          <stop offset="0%" stopColor="#3b3b43" />
          <stop offset="55%" stopColor="#232328" />
          <stop offset="100%" stopColor="#141418" />
        </radialGradient>

        <radialGradient id={coneId} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#131316" />
          <stop offset="70%" stopColor="#1c1c21" />
          <stop offset="100%" stopColor="#2b2b33" />
        </radialGradient>

        <radialGradient id={capId} cx="34%" cy="28%" r="85%">
          <stop offset="0%" stopColor="#787884" />
          <stop offset="45%" stopColor="#41414a" />
          <stop offset="100%" stopColor="#222228" />
        </radialGradient>

        <filter id={glowId} x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="1.7" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <g transform="translate(22 22)">
        {animated && (
          <circle
            className="animate-ping"
            r="14"
            fill="none"
            stroke="#10B981"
            strokeWidth="1.6"
            opacity="0.35"
          />
        )}
        <circle
          r="17.5"
          fill={`url(#${shellId})`}
          stroke="#3F3F46"
          strokeWidth="1.1"
        />
        <circle
          r="15.4"
          fill="none"
          stroke="#0d0d10"
          strokeWidth="5"
        />
        <circle
          r="13.4"
          fill="none"
          stroke="#10B981"
          strokeWidth="2.4"
          filter={`url(#${glowId})`}
        />
        <path
          d="M -9.3 -9.3 A 13.2 13.2 0 0 1 9.3 -9.3"
          stroke="rgba(255,255,255,.1)"
          strokeWidth="2"
          fill="none"
          strokeLinecap="round"
        />
        <circle
          r="10.4"
          fill={`url(#${coneId})`}
          stroke="#0b0b0d"
          strokeWidth=".8"
        />
        <circle r="4.7" fill={`url(#${capId})`} />
        <ellipse
          cx="-.8"
          cy="-1.3"
          rx="2"
          ry="1.2"
          fill="#fff"
          opacity=".16"
        />
        <circle
          cx="11.4"
          cy="-11.4"
          r="1.7"
          fill="#FC7C78"
          filter={`url(#${glowId})`}
        />
      </g>
    </svg>
  );
}
