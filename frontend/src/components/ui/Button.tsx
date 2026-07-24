import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger';
  children: React.ReactNode;
}

export default function Button({ variant = 'primary', children, className = '', ...props }: ButtonProps) {
  let variantClasses = '';
  switch (variant) {
    case 'primary':
      variantClasses = 'bg-[#10b981] text-[#003824] hover:bg-[#4edea3] border-[#10b981] font-bold';
      break;
    case 'secondary':
      variantClasses = 'bg-transparent text-[#bbcabf] hover:text-[#e5e2e3] border-[#27272a] hover:border-[#bbcabf]';
      break;
    case 'danger':
      variantClasses = 'bg-[#93000a] text-[#ffdad6] hover:bg-[#ffb4ab] border-[#93000a] font-bold';
      break;
  }

  return (
    <button
      className={`border px-6 py-2.5 font-label-caps text-label-caps rounded-none transition-all duration-150 active:scale-95 flex items-center justify-center gap-2 cursor-pointer ${variantClasses} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
