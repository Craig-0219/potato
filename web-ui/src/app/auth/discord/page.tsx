'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Spinner } from '@/components/ui/spinner'

export default function DiscordAuthPage() {
  const router = useRouter()

  useEffect(() => {
    // 重定向到後端的 Discord OAuth 端點
    window.location.href = 'http://36.50.249.118:8000/api/v1/auth/discord/login'
  }, [])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
      <div className="text-center">
        <div className="mb-6">
          <div className="w-16 h-16 mx-auto mb-4 bg-discord-500 rounded-full flex items-center justify-center">
            <span className="text-2xl">🔗</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
            連接到 Discord
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            正在重定向到 Discord 進行身份驗證...
          </p>
        </div>
        
        <Spinner size="lg" className="mb-4" />
        
        <div className="max-w-md mx-auto">
          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <p className="text-sm text-blue-800 dark:text-blue-200">
              💡 您將被重定向到 Discord 官方網站進行安全登入。完成後會自動返回到管理面板。
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}