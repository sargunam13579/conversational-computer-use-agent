import React from 'react';

interface StatusBadgeProps {
  status: 'online' | 'offline' | 'busy' | 'active' | 'warning' | 'idle';
  label?: string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  label,
  size = 'md',
}) => {
  const getColors = () => {
    switch (status) {
      case 'online':
      case 'active':
        return {
          bg: 'rgba(16, 185, 129, 0.15)',
          border: 'rgba(16, 185, 129, 0.4)',
          text: '#34d399',
          dot: '#10b981',
        };
      case 'busy':
        return {
          bg: 'rgba(168, 85, 247, 0.15)',
          border: 'rgba(168, 85, 247, 0.4)',
          text: '#c084fc',
          dot: '#a855f7',
        };
      case 'warning':
        return {
          bg: 'rgba(245, 158, 11, 0.15)',
          border: 'rgba(245, 158, 11, 0.4)',
          text: '#fbbf24',
          dot: '#f59e0b',
        };
      case 'offline':
        return {
          bg: 'rgba(244, 63, 94, 0.15)',
          border: 'rgba(244, 63, 94, 0.4)',
          text: '#fb7185',
          dot: '#f43f5e',
        };
      case 'idle':
      default:
        return {
          bg: 'rgba(56, 189, 248, 0.12)',
          border: 'rgba(56, 189, 248, 0.3)',
          text: '#38bdf8',
          dot: '#00f0ff',
        };
    }
  };

  const c = getColors();

  return (
    <span
      style={{
        backgroundColor: c.bg,
        borderColor: c.border,
        color: c.text,
        borderWidth: '1px',
        borderStyle: 'solid',
        padding: size === 'sm' ? '2px 8px' : '4px 12px',
        fontSize: size === 'sm' ? '0.75rem' : '0.825rem',
      }}
      className="inline-flex items-center gap-2 rounded-full font-tech font-semibold uppercase tracking-wider select-none"
    >
      <span
        className="status-dot"
        style={{
          backgroundColor: c.dot,
          color: c.dot,
          width: size === 'sm' ? '6px' : '8px',
          height: size === 'sm' ? '6px' : '8px',
        }}
      />
      {label || status}
    </span>
  );
};
