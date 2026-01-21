import path from 'path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file from project root (parent directory)
  const env = loadEnv(mode, '../', '')

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      host: true, // Listen on all interfaces (0.0.0.0) to support custom hostnames
      port: parseInt(env.ZOEA_FRONTEND_PORT || '5173'),
      strictPort: false, // If port is taken, automatically try next available port
      allowedHosts: ['local.zoea.studio', '.zoea.studio', 'yolk-echo.exe.xyz'], // Allow custom hostname
      proxy: {
        // Proxy /media/ requests to Django backend for serving generated images
        '/media': {
          target: env.VITE_API_BASE_URL || `http://localhost:${env.ZOEA_BACKEND_PORT || '8000'}`,
          changeOrigin: true,
        },
      },
    },
    // Expose ZOEA_BACKEND_PORT to the app via VITE_API_BASE_URL
    define: {
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify(
        env.VITE_API_BASE_URL || `http://localhost:${env.ZOEA_BACKEND_PORT || '8000'}`
      ),
    },
    optimizeDeps: {
      include: ['pdfjs-dist'],
    },
    build: {
      chunkSizeWarningLimit: 10000,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) return
            const pkgMatch = id.split('node_modules/')[1]?.split('/')[0]
            const pkg = pkgMatch?.startsWith('@') ? `${pkgMatch}/${id.split('node_modules/')[1].split('/')[1]}` : pkgMatch

            if (!pkg) return 'vendor'
            if (pkg.startsWith('react-router')) return 'router'
            if (pkg === 'react' || pkg === 'react-dom' || pkg === 'scheduler') return 'react'
            if (pkg.startsWith('@radix-ui')) return 'radix'
            if (pkg === 'lucide-react') return 'icons'
            if (pkg === '@xyflow/react') return 'xyflow'
            if (pkg === '@terrastruct/d2') return 'd2'
            if (pkg === 'pdfjs-dist' || pkg === 'react-pdf') return 'pdf'
            return 'vendor'
          },
        },
      },
    },
  }
})
