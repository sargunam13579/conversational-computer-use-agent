import React from 'react';

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  glow?: boolean;
  corners?: boolean;
  onClick?: () => void;
  style?: React.CSSProperties;
}

export const GlassCard: React.FC<GlassCardProps> = ({
  children,
  className = '',
  glow = false,
  corners = false,
  onClick,
  style,
}) => {
  return (
    <div
      onClick={onClick}
      style={style}
      className={`glass-panel p-5 relative ${glow ? 'glass-panel-glow' : ''} ${
        corners ? 'tech-corners' : ''
      } ${onClick ? 'cursor-pointer hover:border-cyan-400/50' : ''} ${className}`}
    >
      {children}
    </div>
  );
};
