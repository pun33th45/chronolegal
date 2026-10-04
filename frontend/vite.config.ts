import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiUrl = env.VITE_API_URL || env.VITE_API_BASE_URL || ''
  const backendOrigin = apiUrl.replace(/\/+$/, '').replace(/\/api\/v1$/, '') || 'http://localhost:8000'

  // A production bundle without an API URL silently calls itself (e.g. the
  // Vercel domain) instead of the backend. Fail the build instead.
  if (command === 'build' && mode === 'production' && !apiUrl) {
    throw new Error(
      'VITE_API_URL is not set. Set it to the backend origin, e.g. https://<service>.onrender.com',
    )
  }

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      host: true,
      proxy: {
        '/api': {
          target: backendOrigin,
          changeOrigin: true,
        },
        '/ws': {
          target: backendOrigin.replace(/^http/, 'ws'),
          ws: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom'],
            router: ['react-router-dom'],
            query: ['@tanstack/react-query'],
            motion: ['framer-motion'],
            radix: [
              '@radix-ui/react-dialog',
              '@radix-ui/react-dropdown-menu',
              '@radix-ui/react-select',
              '@radix-ui/react-tabs',
            ],
            // recharts is intentionally NOT forced into its own manual chunk
            // (unlike the groups above): it's used only by the lazy-loaded
            // AnalyticsPage, so Rollup's automatic per-dynamic-import
            // splitting already isolates it correctly. Forcing it into a
            // named chunk previously caused recharts' own `clsx` dependency
            // to be grouped there too — and since the app's own `cn()`
            // helper (used by nearly every component) also depends on
            // `clsx`, the main bundle ended up with a static import into
            // that chunk just to reach it, silently pulling in the whole
            // ~400KB recharts chunk on every page load.
          },
        },
      },
    },
  }
})
