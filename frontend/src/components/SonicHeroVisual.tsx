'use client';

import React, { useEffect, useRef, useState, useId } from 'react';

interface Ripple {
  id: number;
  cx: number;
  cy: number;
  color: string;
  maxR: number;
  startTime: number;
  duration: number;
}

export default function SonicHeroVisual() {
  const rawId = useId().replace(/:/g, '');
  const shellGId = `spkShellG_${rawId}`;
  const coneGId = `spkConeG_${rawId}`;
  const capGId = `spkCapG_${rawId}`;
  const glowMainId = `spkGlowMain_${rawId}`;
  const glowSoftId = `spkGlowSoft_${rawId}`;
  const shadowGId = `spkShadow_${rawId}`;

  // EQ Column Heights state (28 columns, height 0 to 10)
  const [colHeights, setColHeights] = useState<number[]>(() => Array(28).fill(3));
  const [colPeaks, setColPeaks] = useState<number[]>(() => Array(28).fill(4));

  // Ripples state
  const [ripples, setRipples] = useState<Ripple[]>([]);
  const rippleIdCounter = useRef(0);

  // Animation refs
  const currentHeightsRef = useRef<number[]>(Array(28).fill(3));
  const targetHeightsRef = useRef<number[]>(Array(28).fill(3));
  const peaksRef = useRef<number[]>(Array(28).fill(4));
  const peakHoldCountersRef = useRef<number[]>(Array(28).fill(0));
  const animFrameRef = useRef<number | null>(null);
  const lastRippleTimeRef = useRef<number>(0);
  const isPageVisibleRef = useRef<boolean>(true);

  // Speaker pulse ref for subtle breathing effect
  const [speakerPulse, setSpeakerPulse] = useState(1);

  // Spawn a ripple
  const spawnRipple = (cx: number, cy: number, color = '#10B981', maxR = 120) => {
    if (!isPageVisibleRef.current) return;
    setRipples((prev) => {
      // Limit total simultaneous ripples to 8
      if (prev.length >= 8) return prev;
      const newId = ++rippleIdCounter.current;
      return [
        ...prev,
        {
          id: newId,
          cx,
          cy,
          color,
          maxR,
          startTime: performance.now(),
          duration: 1800,
        },
      ];
    });
  };

  // Main animation loop & Visibility listener
  useEffect(() => {
    let t = 0;

    const handleVisibilityChange = () => {
      isPageVisibleRef.current = !document.hidden;
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    const animate = (time: number) => {
      // Pause animation updates when document is hidden in background tab
      if (document.hidden || !isPageVisibleRef.current) {
        animFrameRef.current = requestAnimationFrame(animate);
        return;
      }

      t += 0.03;

      // Check prefers-reduced-motion
      const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (prefersReduced) {
        animFrameRef.current = requestAnimationFrame(animate);
        return;
      }

      // Compute synthetic spectral target for 28 columns
      const newCurrents = [...currentHeightsRef.current];
      const newTargets = [...targetHeightsRef.current];
      const newPeaks = [...peaksRef.current];
      const newHold = [...peakHoldCountersRef.current];

      for (let i = 0; i < 28; i++) {
        // Bell envelope centered around index 13.5
        const bell = Math.exp(-Math.pow((i - 13.5) / 7.5, 2));

        // Combined sine wave spectrum
        const wave1 = Math.sin(t * 1.8 + i * 0.35);
        const wave2 = Math.cos(t * 2.5 - i * 0.2);
        const wave3 = Math.sin(t * 0.9 + i * 0.15);

        const rawVal = ((wave1 + wave2 + wave3 + 3) / 6) * bell * 8.5 + 1.2;
        newTargets[i] = Math.min(10, Math.max(1, rawVal));

        // Smooth interpolation towards target (organic drift)
        newCurrents[i] += (newTargets[i] - newCurrents[i]) * 0.12;

        // Peak marker logic
        if (newCurrents[i] >= newPeaks[i]) {
          newPeaks[i] = newCurrents[i];
          newHold[i] = 12; // Hold frames
        } else {
          if (newHold[i] > 0) {
            newHold[i]--;
          } else {
            newPeaks[i] = Math.max(newCurrents[i], newPeaks[i] - 0.15);
          }
        }
      }

      currentHeightsRef.current = newCurrents;
      targetHeightsRef.current = newTargets;
      peaksRef.current = newPeaks;
      peakHoldCountersRef.current = newHold;

      setColHeights([...newCurrents]);
      setColPeaks([...newPeaks]);

      // Speaker subtle breathing scale
      setSpeakerPulse(1 + Math.sin(t * 2) * 0.02);

      // Periodic autonomous ripple trigger (~every 2.2 seconds)
      if (time - lastRippleTimeRef.current > 2200) {
        lastRippleTimeRef.current = time;
        // Pulse from center speaker
        spawnRipple(280, 240, '#10B981', 130);
        // Occasional pulse from side speaker
        if (Math.sin(t * 0.5) > 0.4) {
          setTimeout(() => spawnRipple(102, 254, '#FC7C78', 90), 300);
        }
      }

      // Update active ripples duration cleanup
      setRipples((prev) =>
        prev.filter((r) => time - r.startTime < r.duration)
      );

      animFrameRef.current = requestAnimationFrame(animate);
    };

    animFrameRef.current = requestAnimationFrame(animate);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, []);

  return (
    <div className="w-full max-w-[440px] mx-auto flex flex-col items-center select-none">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Michroma&display=swap');

        .sonic-wordmark {
          font-family: 'Michroma', sans-serif;
          letter-spacing: 0.42em;
        }

        @media (max-height: 660px) {
          .sonic-hero-container {
            transform: scale(0.82);
            margin-top: -10px;
            margin-bottom: -10px;
          }
        }
      `}</style>

      <div className="sonic-hero-container relative w-full aspect-[560/390] flex items-center justify-center">
        {/* Glow ambient background */}
        <div className="absolute inset-0 bg-[#10b981]/10 blur-3xl rounded-full pointer-events-none transform scale-75 opacity-40 animate-pulse"></div>

        <svg
          viewBox="0 0 560 410"
          className="w-full h-full overflow-visible relative z-10"
          aria-hidden="true"
        >
          <defs>
            {/* Speaker Metallic Shell Gradient */}
            <radialGradient id={shellGId} cx="36%" cy="30%" r="80%">
              <stop offset="0%" stopColor="#3b3b43" />
              <stop offset="55%" stopColor="#232328" />
              <stop offset="100%" stopColor="#141418" />
            </radialGradient>

            {/* Speaker Recessed Cone Gradient */}
            <radialGradient id={coneGId} cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#131316" />
              <stop offset="70%" stopColor="#1c1c21" />
              <stop offset="100%" stopColor="#2b2b33" />
            </radialGradient>

            {/* Center Cap/Dome Gradient */}
            <radialGradient id={capGId} cx="34%" cy="28%" r="85%">
              <stop offset="0%" stopColor="#787884" />
              <stop offset="45%" stopColor="#41414a" />
              <stop offset="100%" stopColor="#222228" />
            </radialGradient>

            {/* Main Green Glow Filter */}
            <filter id={glowMainId} x="-80%" y="-80%" width="260%" height="260%">
              <feGaussianBlur stdDeviation="4.2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            {/* Soft Glow Filter */}
            <filter id={glowSoftId} x="-60%" y="-60%" width="220%" height="220%">
              <feGaussianBlur stdDeviation="2.6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            {/* Ground Shadow Filter */}
            <filter id={shadowGId} x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="5" />
            </filter>
          </defs>

          {/* 1. BACKGROUND EQUALIZER (28 columns x 10 segments) */}
          <g id="gEQ" opacity="0.72">
            {Array.from({ length: 28 }).map((_, colIdx) => {
              // x calculation: 28 cols * 18px total width = 496px. Start offset x = 32
              const colX = 32 + colIdx * 18;
              const heightSegments = colHeights[colIdx] || 0;
              const peakSegment = colPeaks[colIdx] || 0;

              return (
                <g key={colIdx}>
                  {Array.from({ length: 10 }).map((_, segIdx) => {
                    const segY = 320 - (segIdx + 1) * 21;
                    const isActive = segIdx < Math.floor(heightSegments);
                    if (!isActive) return null;

                    const isTopCoral = segIdx >= 7;
                    const fillColor = isTopCoral ? '#FC7C78' : '#10B981';

                    return (
                      <rect
                        key={segIdx}
                        x={colX}
                        y={segY}
                        width={10}
                        height={16}
                        rx={2.5}
                        fill={fillColor}
                        opacity={isTopCoral ? 0.95 : 0.85}
                      />
                    );
                  })}

                  {/* Peak Marker above column */}
                  {peakSegment > 0.5 && (
                    <rect
                      x={colX}
                      y={Math.max(40, 320 - (peakSegment + 0.5) * 21)}
                      width={10}
                      height={3}
                      rx={1}
                      fill="#FC7C78"
                      filter={`url(#${glowSoftId})`}
                    />
                  )}
                </g>
              );
            })}
          </g>

          {/* Ground Line */}
          <line
            x1="20"
            y1="320"
            x2="540"
            y2="320"
            stroke="#27272A"
            strokeWidth="1.5"
            strokeDasharray="4 4"
            opacity="0.5"
          />

          {/* 2. PROPAGATED RIPPLES */}
          <g id="gRipples">
            {ripples.map((r) => {
              const elapsed = performance.now() - r.startTime;
              const progress = Math.min(1, elapsed / r.duration);
              const currentR = progress * r.maxR;
              const currentOpacity = (1 - progress) * 0.65;
              const currentStrokeWidth = Math.max(0.5, (1 - progress) * 3);

              return (
                <circle
                  key={r.id}
                  cx={r.cx}
                  cy={r.cy}
                  r={currentR}
                  fill="none"
                  stroke={r.color}
                  strokeWidth={currentStrokeWidth}
                  opacity={currentOpacity}
                  filter={`url(#${glowSoftId})`}
                />
              );
            })}
          </g>

          {/* 3. SPEAKERS GROUP */}

          {/* Ground Shadows */}
          <g id="gShadows" opacity="0.6">
            <ellipse cx="102" cy="322" rx="55" ry="10" fill="#000" filter={`url(#${shadowGId})`} />
            <ellipse cx="458" cy="322" rx="55" ry="10" fill="#000" filter={`url(#${shadowGId})`} />
            <ellipse cx="280" cy="324" rx="85" ry="14" fill="#000" filter={`url(#${shadowGId})`} />
          </g>

          {/* SPEAKER LEFT (Center x=102, y=254, r=66, Yaw ~40° -> horizontal cos(40°)=0.766) */}
          <g id="spkLeft" transform={`translate(102 254) scale(${speakerPulse}) translate(-102 -254)`}>
            {/* Inner cabinet depth projection */}
            <path
              d="M 102 188 C 122 188 138 217 138 254 C 138 291 122 320 102 320 L 114 320 C 134 320 150 291 150 254 C 150 217 134 188 114 188 Z"
              fill="#18181c"
              stroke="#27272a"
              strokeWidth="0.8"
            />

            {/* Outer Shell Flange */}
            <ellipse cx="102" cy="254" rx="50.5" ry="66" fill={`url(#${shellGId})`} stroke="#3F3F46" strokeWidth="1.2" />

            {/* Dark Outer Rim */}
            <ellipse cx="102" cy="254" rx="44.4" ry="58" fill="none" stroke="#0d0d10" strokeWidth="12" />

            {/* Neon Green Ring */}
            <ellipse cx="102" cy="254" rx="39" ry="51" fill="none" stroke="#10B981" strokeWidth="3" filter={`url(#${glowMainId})`} />

            {/* Metallic Highlight Arch */}
            <path d="M 68 215 A 38 50 0 0 1 136 215" stroke="rgba(255,255,255,0.15)" strokeWidth="2.5" fill="none" strokeLinecap="round" />

            {/* Dark Inner Opening (perspective cx shifted right towards center) */}
            <ellipse cx="106" cy="254" rx="30" ry="39" fill={`url(#${coneGId})`} stroke="#0b0b0d" strokeWidth="1" />

            {/* Center Dome (cx shifted further right) */}
            <ellipse cx="110" cy="254" rx="13.8" ry="18" fill={`url(#${capGId})`} />
            <ellipse cx="108" cy="251" rx="5.5" ry="4" fill="#fff" opacity="0.18" />

            {/* Coral LED Indicator */}
            <circle cx="132" cy="212" r="2.2" fill="#FC7C78" filter={`url(#${glowMainId})`} />
          </g>

          {/* SPEAKER RIGHT (Center x=458, y=254, r=66, Yaw ~40° -> horizontal cos(40°)=0.766) */}
          <g id="spkRight" transform={`translate(458 254) scale(${speakerPulse}) translate(-458 -254)`}>
            {/* Inner cabinet depth projection */}
            <path
              d="M 458 188 C 438 188 422 217 422 254 C 422 291 438 320 458 320 L 446 320 C 426 320 410 291 410 254 C 410 217 426 188 446 188 Z"
              fill="#18181c"
              stroke="#27272a"
              strokeWidth="0.8"
            />

            {/* Outer Shell Flange */}
            <ellipse cx="458" cy="254" rx="50.5" ry="66" fill={`url(#${shellGId})`} stroke="#3F3F46" strokeWidth="1.2" />

            {/* Dark Outer Rim */}
            <ellipse cx="458" cy="254" rx="44.4" ry="58" fill="none" stroke="#0d0d10" strokeWidth="12" />

            {/* Neon Green Ring */}
            <ellipse cx="458" cy="254" rx="39" ry="51" fill="none" stroke="#10B981" strokeWidth="3" filter={`url(#${glowMainId})`} />

            {/* Metallic Highlight Arch */}
            <path d="M 424 215 A 38 50 0 0 1 492 215" stroke="rgba(255,255,255,0.15)" strokeWidth="2.5" fill="none" strokeLinecap="round" />

            {/* Dark Inner Opening (perspective cx shifted left towards center) */}
            <ellipse cx="454" cy="254" rx="30" ry="39" fill={`url(#${coneGId})`} stroke="#0b0b0d" strokeWidth="1" />

            {/* Center Dome (cx shifted further left) */}
            <ellipse cx="450" cy="254" rx="13.8" ry="18" fill={`url(#${capGId})`} />
            <ellipse cx="448" cy="251" rx="5.5" ry="4" fill="#fff" opacity="0.18" />

            {/* Coral LED Indicator */}
            <circle cx="428" cy="212" r="2.2" fill="#FC7C78" filter={`url(#${glowMainId})`} />
          </g>

          {/* SPEAKER CENTER (Center x=280, y=240, r=80, Frontal) */}
          <g id="spkCenter" transform={`translate(280 240) scale(${speakerPulse}) translate(-280 -240)`}>
            {/* Outer Shell Flange */}
            <circle cx="280" cy="240" r="80" fill={`url(#${shellGId})`} stroke="#3F3F46" strokeWidth="1.5" />

            {/* Dark Outer Rim */}
            <circle cx="280" cy="240" r="70" fill="none" stroke="#0d0d10" strokeWidth="15" />

            {/* Neon Green Ring */}
            <circle cx="280" cy="240" r="61" fill="none" stroke="#10B981" strokeWidth="3.5" filter={`url(#${glowMainId})`} />

            {/* Metallic Highlight Arch */}
            <path d="M 238 198 A 60 60 0 0 1 322 198" stroke="rgba(255,255,255,0.18)" strokeWidth="3" fill="none" strokeLinecap="round" />

            {/* Dark Recessed Cone */}
            <circle cx="280" cy="240" r="47" fill={`url(#${coneGId})`} stroke="#0b0b0d" strokeWidth="1.2" />

            {/* Center Dome Cap */}
            <circle cx="280" cy="240" r="21.5" fill={`url(#${capGId})`} />
            <ellipse cx="276" cy="235" rx="8" ry="5" fill="#fff" opacity="0.2" />

            {/* Mounting Screws (3) */}
            <circle cx="212" cy="240" r="2.2" fill="#141418" stroke="#3F3F46" strokeWidth="0.8" />
            <circle cx="314" cy="182" r="2.2" fill="#141418" stroke="#3F3F46" strokeWidth="0.8" />
            <circle cx="314" cy="298" r="2.2" fill="#141418" stroke="#3F3F46" strokeWidth="0.8" />

            {/* Coral LED Indicator Top-Right */}
            <circle cx="332" cy="188" r="3" fill="#FC7C78" filter={`url(#${glowMainId})`} />
          </g>
        </svg>
      </div>

      {/* 4. WORDMARK "SONIC" WITH STYLIZED SPEAKER 'O' */}
      <div className="mt-2 flex items-center justify-center gap-3 text-[#E4E4E7] font-bold text-2xl tracking-[0.42em] sonic-wordmark uppercase select-none">
        <span>S</span>

        {/* Stylized Speaker 'O' (.oMark) */}
        <span className="relative inline-flex items-center justify-center w-7 h-7 mx-0.5 shrink-0">
          <span className="absolute inset-0 rounded-full bg-[#27272A] border border-[#3F3F46] shadow-inner"></span>
          <span className="absolute inset-1 rounded-full bg-[#141417] flex items-center justify-center">
            <span className="w-4 h-4 rounded-full border-2 border-[#10B981] shadow-[0_0_6px_#10B981] animate-pulse flex items-center justify-center">
              <span className="w-1.5 h-1.5 rounded-full bg-[#3F3F46]"></span>
            </span>
          </span>
        </span>

        <span>N</span>
        <span>I</span>
        <span>C</span>
      </div>
    </div>
  );
}
