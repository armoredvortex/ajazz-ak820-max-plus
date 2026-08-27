import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [svelte()],
  base: './',          // relative paths so file:// serving works
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
