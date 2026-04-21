import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiPort = env.API_PORT || '3001';

  return {
    plugins: [react(), tailwindcss()],
    server: {
      allowedHosts: ['.cloudfront.net', 'all'],
      proxy: {
        '/api': `http://localhost:${apiPort}`,
      },
    },
    define: {
      __APP_MODE__: JSON.stringify(env.VITE_APP_MODE || 'with_metadata'),
    },
  };
});
