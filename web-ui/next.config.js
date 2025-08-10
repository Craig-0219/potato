/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  poweredByHeader: false,
  reactStrictMode: true,
  swcMinify: true,
  
  // API 代理配置
  async rewrites() {
    return [
      {
        source: '/api/proxy/:path*',
        destination: process.env.API_BASE_URL ? `${process.env.API_BASE_URL}/:path*` : 'http://localhost:8000/api/v1/:path*',
      },
    ]
  },

  // 環境變數配置
  env: {
    CUSTOM_KEY: process.env.CUSTOM_KEY,
    API_BASE_URL: process.env.API_BASE_URL || 'http://localhost:8000/api/v1',
    APP_NAME: 'Potato Bot Dashboard',
    APP_VERSION: '1.8.0',
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