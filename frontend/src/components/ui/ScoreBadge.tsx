import React from 'react';

interface ScoreBadgeProps {
  score: number;
}

export default function ScoreBadge({ score }: ScoreBadgeProps) {
  let scoreColor = 'text-red-400';
  if (score >= 85) scoreColor = 'text-[#10b981]';
  else if (score >= 60) scoreColor = 'text-sky-400';
  else if (score >= 40) scoreColor = 'text-yellow-500';

  return (
    <div className="flex items-center gap-2 font-data-mono text-data-mono">
      <span className={`font-bold ${scoreColor}`}>{score}</span>
      <div className="w-8 h-1 bg-[#1c1b1c] overflow-hidden hidden md:block border border-[#27272a] rounded-none">
        <div
          className={`h-full ${score >= 85 ? 'bg-[#10b981]' : 'bg-yellow-500'}`}
          style={{ width: `${score}%` }}
        ></div>
      </div>
    </div>
  );
}
