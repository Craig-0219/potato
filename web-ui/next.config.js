/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  poweredByHeader: false,
  reactStrictMode: false, // 暫時禁用以解決認證狀態問題
  swcMinify: true,
  
  // 允許跨域開發請求
  allowedDevOrigins: ['36.50.249.118'],
  
  // API 代理配置
  async rewrites() {
    const botApiUrl = process.env.NEXT_PUBLIC_BOT_API_URL || 'http://localhost:8000'
    return [
      // 代理到 Discord Bot API - 沒有 /v1 前綴的端點
      {
        source: '/api/system/:path*',
        destination: `${botApiUrl}/api/v1/system/:path*`,
      },
      {
        source: '/api/tickets/:path*',
        destination: `${botApiUrl}/api/v1/tickets/:path*`,
      },
      {
        source: '/api/analytics/:path*',
        destination: `${botApiUrl}/api/v1/analytics/:path*`,
      },
      {
        source: '/api/realtime/:path*',
        destination: `${botApiUrl}/api/realtime/:path*`,
      },
      // 代理到 Discord Bot API - 有 /v1 前綴的端點
      {
        source: '/api/v1/tickets/:path*',
        destination: `${botApiUrl}/api/v1/tickets/:path*`,
      },
      {
        source: '/api/v1/system/:path*',
        destination: `${botApiUrl}/api/v1/system/:path*`,
      },
      {
        source: '/api/v1/analytics/:path*',
        destination: `${botApiUrl}/api/v1/analytics/:path*`,
      },
      {
        source: '/api/v1/:path*',
        destination: `${botApiUrl}/api/v1/:path*`,
      },
      // Discord OAuth 回調代理
      {
        source: '/auth/discord/callback',
        destination: `${botApiUrl}/api/v1/auth/discord/callback`,
      },
      // 原有的代理配置
      {
        source: '/api/proxy/:path*',
        destination: process.env.API_BASE_URL ? `${process.env.API_BASE_URL}/:path*` : `${botApiUrl}/api/v1/:path*`,
      },
    ]
  },

  // 環境變數配置
  env: {
    CUSTOM_KEY: process.env.CUSTOM_KEY,
    API_BASE_URL: process.env.API_BASE_URL || 'http://localhost:8000/api/v1',
    APP_NAME: 'Potato Bot Dashboard',
    APP_VERSION: '2.3.0',
  },

  // PWA 相關設置
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff'
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY'
          },
          {
            key: 'X-XSS-Protection',
            value: '1; mode=block'
          }
        ]
      }
    ]
  },

  // 圖片優化
  images: {
    domains: ['cdn.discordapp.com', 'images.unsplash.com'],
    formats: ['image/webp', 'image/avif'],
  },

  // 實驗性功能
  experimental: {
    serverComponentsExternalPackages: ['@prisma/client'],
  },
}

module.exports = nextConfig