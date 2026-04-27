import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiPort = env.API_PORT || '3001';
  const isLegacy = env.VITE_APP_MODE === 'legacy';
  const base = isLegacy ? '/app-legacy/' : '/app/';

  return {
    plugins: [react(), tailwindcss()],
    base,
    build: {
      outDir: isLegacy ? 'dist-legacy' : 'dist',
    },
    server: {
      allowedHosts: ['.cloudfront.net', 'all'],
      proxy: {
        '/api': `http://localhost:${apiPort}`,
      },
    },
    define: {
      __AUTH_DISABLED__: JSON.stringify(env.VITE_AUTH_DISABLED === 'true'),
      __APP_MODE__: JSON.stringify(env.VITE_APP_MODE || 'with_metadata'),
      __COGNITO_CONFIG__: JSON.stringify({
        userPoolId: env.VITE_COGNITO_USER_POOL_ID || '',
        clientId: env.VITE_COGNITO_CLIENT_ID || '',
        domain: env.VITE_COGNITO_DOMAIN || '',
        redirectUri: env.VITE_COGNITO_REDIRECT_URI || (isLegacy ? 'http://localhost:3000/app-legacy/' : 'http://localhost:3000/app/'),
      }),
    },
  };
});
