import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig(({ command }) => {
  const config = {
    plugins: [react()],
    server: {
      port: 5173,
      host: '0.0.0.0',
      allowedHosts: ['nfl.taylorswayze.com']
    }
  };

  // Apply the '/static/' base path ONLY when building for production
  if (command === 'build') {
    config.base = '/static/';
  }

  return config;
});
