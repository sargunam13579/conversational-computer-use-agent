import React from 'react';
import type { VoiceStateType } from '../../context/VoiceContext';

interface HolographicOrbProps {
  state?: VoiceStateType | 'idle';
  size?: number;
  label?: string;
  onClick?: () => void;
}

export const HolographicOrb: React.FC<HolographicOrbProps> = ({
  state = 'idle',
  size = 200,
  label,
  onClick,
}) => {
  const getOrbStyle = () => {
    switch (state) {
      case 'listening':
        return {
          core: 'radial-gradient(circle, #00f0ff 0%, #0284c7 50%, transparent 70%)',
          ring1: '#00f0ff',
          ring2: '#38bdf8',
          shadow: '0 0 45px rgba(0, 240, 255, 0.85)',
          speed: '3s',
        };
      case 'processing':
        return {
          core: 'radial-gradient(circle, #a855f7 0%, #6366f1 50%, transparent 70%)',
          ring1: '#a855f7',
          ring2: '#c084fc',
          shadow: '0 0 45px rgba(168, 85, 247, 0.85)',
          speed: '1.5s',
        };
      case 'speaking':
        return {
          core: 'radial-gradient(circle, #10b981 0%, #059669 50%, transparent 70%)',
          ring1: '#10b981',
          ring2: '#34d399',
          shadow: '0 0 45px rgba(16, 185, 129, 0.85)',
          speed: '2s',
        };
      case 'idle':
      default:
        return {
          core: 'radial-gradient(circle, #0ea5e9 0%, #1e293b 60%, transparent 75%)',
          ring1: 'rgba(56, 189, 248, 0.4)',
          ring2: 'rgba(14, 165, 233, 0.3)',
          shadow: '0 0 25px rgba(14, 165, 233, 0.35)',
          speed: '8s',
        };
    }
  };

  const style = getOrbStyle();

  return (
    <div
      onClick={onClick}
      className={`relative flex flex-col items-center justify-center select-none ${
        onClick ? 'cursor-pointer' : ''
      }`}
      style={{ width: size, height: size }}
    >
      {/* Outer Ring 1 */}
      <div
        className="absolute inset-0 rounded-full border border-dashed animate-spin-slow pointer-events-none"
        style={{
          borderColor: style.ring1,
          animationDuration: style.speed,
        }}
      />

      {/* Inner Ring 2 */}
      <div
        className="absolute inset-3 rounded-full border border-dotted animate-spin-reverse pointer-events-none"
        style={{
          borderColor: style.ring2,
          animationDuration: `calc(${style.speed} * 1.3)`,
        }}
      />

      {/* Outer Glow Halo */}
      <div
        className="absolute inset-6 rounded-full opacity-60 pointer-events-none animate-pulse-glow"
        style={{
          background: style.core,
          boxShadow: style.shadow,
        }}
      />

      {/* Central Core */}
      <div
        className="relative z-10 w-24 h-24 rounded-full flex items-center justify-center"
        style={{
          background: 'rgba(12, 18, 32, 0.85)',
          border: `2px solid ${style.ring1}`,
          boxShadow: style.shadow,
        }}
      >
        <div className="flex flex-col items-center justify-center">
          <span className="font-display font-black text-sm tracking-widest text-white">
            Seyal AI
          </span>
          <span
            className="font-tech text-xs tracking-wider uppercase font-semibold"
            style={{ color: style.ring1 }}
          >
            {state}
          </span>
        </div>
      </div>

      {/* Optional Label */}
      {label && (
        <span className="mt-4 font-tech text-xs tracking-widest uppercase text-slate-400">
          {label}
        </span>
      )}
    </div>
  );
};
