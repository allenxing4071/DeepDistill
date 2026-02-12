/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        /* ── DeepDistill 色彩系统（与 KKline/FlowEdge 统一） ── */
        surface: {
          0: '#06070a',
          1: '#0b0d12',
          2: '#10131a',
          3: '#161a24',
        },
        /* 成功/完成 */
        success: {
          DEFAULT: '#00d68f',
          dim: 'rgba(0,214,143,0.10)',
          glow: 'rgba(0,214,143,0.35)',
        },
        /* 错误/失败 */
        error: {
          DEFAULT: '#ff5370',
          dim: 'rgba(255,83,112,0.10)',
          glow: 'rgba(255,83,112,0.35)',
        },
        /* 警告/处理中 */
        warn: {
          DEFAULT: '#ffb347',
          dim: 'rgba(255,179,71,0.10)',
          glow: 'rgba(255,179,71,0.35)',
        },
        /* 信息/链接 */
        info: {
          DEFAULT: '#4a90ff',
          dim: 'rgba(74,144,255,0.10)',
          glow: 'rgba(74,144,255,0.35)',
        },
        /* AI/智能 */
        ai: {
          DEFAULT: '#a78bfa',
          dim: 'rgba(167,139,250,0.10)',
        },
        /* 视频/视觉 */
        visual: {
          DEFAULT: '#22d3ee',
          dim: 'rgba(34,211,238,0.10)',
        },
        /* 文字层级 */
        text: {
          primary: '#eaecf0',
          secondary: '#8b90a3',
          tertiary: '#545870',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'spin-slow': 'spin 2s linear infinite',
        'slide-up': 'slideUp 0.3s ease-out',
        'fade-in': 'fadeIn 0.2s ease-out',
        'shimmer': 'shimmer 2s ease-in-out infinite',
      },
      keyframes: {
        slideUp: {
          '0%': { transform: 'translateY(8px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        shimmer: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
      },
    },
  },
  plugins: [],
}
