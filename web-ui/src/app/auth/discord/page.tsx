'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Spinner } from '@/components/ui/spinner'

export default function DiscordAuthPage() {
  const router = useRouter()

  useEffect(() => {
    // 暫時使用測試登入功能，避免 OAuth 配置問題
    const testLogin = async () => {
      try {
        const response = await fetch('http://36.50.249.118:8000/api/v1/auth/test-login', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            username: 'server_owner',
            role: 'owner'  // 使用 owner 角色來模擬伺服器擁有者
          })
        })

        const data = await response.json()

        if (data.success && data.token) {
          // 轉換用戶數據格式以匹配 User 接口
          const userData = {
            id: data.user.id,
            name: data.user.username, // 將 username 映射為 name
            email: data.user.email,
            avatar: data.user.avatar,
            role: 'owner' as const, // 測試模式下設為伺服器擁有者
            permissions: ['讀取', '寫入', '刪除', '管理員', '擁有者'], // 擁有者權限
            isOwner: true, // 標記為擁有者
            ownerPrivileges: true // 擁有者特權
          }

          // 儲存 token 和轉換後的用戶數據到 localStorage
          localStorage.setItem('auth_token', data.token)
          localStorage.setItem('user_data', JSON.stringify(userData))

          // 重定向到成功頁面
          router.push('/auth/success?temp=true')
        } else {
          throw new Error('測試登入失敗')
        }
      } catch (error) {
        console.error('登入錯誤:', error)
        router.push('/auth/error?error=test_login_failed')
      }
    }

    // 延遲 1 秒執行，讓用戶看到載入畫面
    const timer = setTimeout(testLogin, 1000)
    return () => clearTimeout(timer)
  }, [router])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
      <div className="text-center">
        <div className="mb-6">
          <div className="w-16 h-16 mx-auto mb-4 bg-discord-500 rounded-full flex items-center justify-center">
            <span className="text-2xl">🔗</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
            伺服器擁有者登入
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            正在進行伺服器擁有者身份驗證...
          </p>
        </div>

        <Spinner size="lg" className="mb-4" />

        <div className="max-w-md mx-auto">
          <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
            <p className="text-sm text-yellow-800 dark:text-yellow-200">
              🔧 暫時使用伺服器擁有者測試模式。Discord OAuth 配置完成後會自動檢測伺服器擁有者身份。
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
