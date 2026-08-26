import React from 'react';
import type { VoiceStateType } from '../../context/VoiceContext';

interface SoundWaveProps {
  state: VoiceStateType;
  barCount?: number;
}

export const SoundWaveVisualizer: React.FC<SoundWaveProps> = ({ state, barCount = 12 }) => {
  const isAnimated = state === 'listening' || state === 'speaking' || state === 'processing';

  const getColor = () => {
    switch (state) {
      case 'listening':
        return '#00f0ff';
      case 'speaking':
        return '#10b981';
      case 'processing':
        return '#a855f7';
      case 'idle':
      default:
        return '#38bdf8';
    }
  };

  const color = getColor();

  return (
    <div className="flex items-center justify-center gap-1.5 h-10 px-4">
      {Array.from({ length: barCount }).map((_, idx) => {
        const waveClass = isAnimated ? `wave-bar-${(idx % 5) + 1}` : '';
        return (
          <span
            key={idx}
            className={`w-1 rounded-full transition-all duration-300 ${waveClass}`}
            style={{
              backgroundColor: color,
              height: isAnimated ? undefined : '6px',
              boxShadow: isAnimated ? `0 0 8px ${color}` : 'none',
              opacity: isAnimated ? 0.9 : 0.4,
            }}
          />
        );
      })}
    </div>
  );
};
