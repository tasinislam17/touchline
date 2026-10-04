import { defineConfig } from 'vite';
export default defineConfig({ root: 'web', build: { outDir: '../dist', emptyOutDir: true }, server: { port: 4173, strictPort: true }, preview: {port: 4173, strictPort: true} });
