import { defineConfig } from 'vite';
const fplProxy={target:'https://fantasy.premierleague.com',changeOrigin:true,rewrite:path=>path.replace(/^\/api\/fpl/,'/api').replace(/\/?$/,'/')};
export default defineConfig({ root: 'web', build: { outDir: '../dist', emptyOutDir: true }, server: { port: 4173, strictPort: true,proxy:{'/api/fpl':fplProxy} }, preview: {port:4173,strictPort:true,proxy:{'/api/fpl':fplProxy}} });
