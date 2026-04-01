import { defineConfig } from 'astro/config';

import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  site: 'https://megaboy81-boop.github.io',
  base: '/ddinair-site',
  output: 'static',

  vite: {
    plugins: [tailwindcss()],
  },
});