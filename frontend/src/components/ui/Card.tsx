import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

export default function Card({ children, className = '', onClick }: CardProps) {
  return (
    <div
      onClick={onClick}
      className={`bg-[#131314] border border-[#27272a] rounded-none p-6 ${
        onClick ? 'hover:border-[#10b981] cursor-pointer transition-colors' : ''
      } ${className}`}
    >
      {children}
    </div>
  );
}
