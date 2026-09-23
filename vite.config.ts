import { defineConfig } from 'vite';
import { resolve } from 'node:path';

export default defineConfig({
  root: 'src/web',
  publicDir: '../../public',
  build: {
    outDir: '../../dist',
    emptyOutDir: true,
    target: 'es2022',
    rollupOptions: {
      input: {
        app: resolve('src/web/index.html'),
        lab: resolve('src/web/lab.html'),
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8787',
    },
  },
});
