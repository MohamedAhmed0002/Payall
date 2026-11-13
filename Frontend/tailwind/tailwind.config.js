module.exports = {
  content: ["../index.html"],
  theme: {
    extend: {
      colors: {
        white: '#FFFFFF',
        alabaster: '#FAF9F5',
        cream: '#F3F1EA',
        obsidian: '#0B0B0B',
        charcoal: '#1A1A1A',
        stone: '#686763',
        gold: {
          DEFAULT: '#C8A96E',
          light: '#DFC593',
          dark: '#9E7E43',
          muted: 'rgba(200, 169, 110, 0.14)',
          border: 'rgba(200, 169, 110, 0.38)'
        }
      },
      fontFamily: {
        display: ['Oswald', 'sans-serif'],
        sans: ['Plus Jakarta Sans', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace']
      },
      boxShadow: {
        'editorial': '0 20px 50px -15px rgba(11, 11, 11, 0.07)',
        'card': '0 4px 20px -2px rgba(11, 11, 11, 0.04)',
        'sticky-stack': '0 -12px 32px -6px rgba(11, 11, 11, 0.08), 0 10px 28px -6px rgba(11, 11, 11, 0.05)',
        'drawer': '-24px 0 80px rgba(11, 11, 11, 0.18)'
      }
    }
  }
};
