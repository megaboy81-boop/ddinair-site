import { defineConfig } from 'astro/config';

import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  site: 'https://ddaircon.co.kr',
  base: '/',
  output: 'static',

  vite: {
    plugins: [tailwindcss()],
  },
});
