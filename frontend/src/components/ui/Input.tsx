import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ComponentType<any>;
}

export default function Input({ icon: Icon, className = '', ...props }: InputProps) {
  return (
    <div className="relative flex items-center w-full border border-[#27272a] focus-within:border-[#10b981] bg-[#0a0a0b] transition-colors rounded-none">
      {Icon && <Icon size={16} className="absolute left-3 text-[#bbcabf]" />}
      <input
        className={`w-full bg-transparent border-none text-[#e5e2e3] font-data-mono text-data-mono py-3 focus:outline-none ${
          Icon ? 'pl-10' : 'px-3.5'
        } ${className}`}
        {...props}
      />
    </div>
  );
}
