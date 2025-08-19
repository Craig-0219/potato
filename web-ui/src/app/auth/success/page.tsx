'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useAuth } from '@/lib/auth/auth-context'
import { Spinner } from '@/components/ui/spinner'

export default function AuthSuccessPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { loginWithToken } = useAuth()
  const [status, setStatus] = useState<'processing' | 'success' | 'error'>('processing')
  const [message, setMessage] = useState('處理認證結果...')

  useEffect(() => {
    const token = searchParams.get('token')
    
    if (!token) {
      setStatus('error')
      setMessage('未收到認證 token')
      return
    }

    // 使用 token 登入
    const handleLogin = async () => {
      try {
        const success = await loginWithToken(token)
        
        if (success) {
          setStatus('success')
          setMessage('登入成功！正在跳轉到儀表板...')
          
          // 延遲跳轉給用戶看到成功訊息
          setTimeout(() => {
            router.push('/dashboard')
          }, 2000)
        } else {
          setStatus('error')
          setMessage('登入失敗，token 無效')
        }
      } catch (error) {
        console.error('登入錯誤:', error)
        setStatus('error')
        setMessage('登入過程發生錯誤')
      }
    }

    handleLogin()
  }, [searchParams, loginWithToken, router])

  const getStatusIcon = () => {
    switch (status) {
      case 'processing':
        return '🔄'
      case 'success':
        return '✅'
      case 'error':
        return '❌'
      default:
        return '🔄'
    }
  }

  const getStatusColor = () => {
    switch (status) {
      case 'success':
        return 'text-green-600 dark:text-green-400'
      case 'error':
        return 'text-red-600 dark:text-red-400'
      default:
        return 'text-blue-600 dark:text-blue-400'
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
      <div className="text-center max-w-md mx-auto px-4">
        <div className="mb-6">
          <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-br from-discord-500 to-brand-600 rounded-full flex items-center justify-center text-2xl">
            {getStatusIcon()}
          </div>
          
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
            Discord 認證
          </h1>
          
          <p className={`text-lg ${getStatusColor()}`}>
            {message}
          </p>
        </div>
        
        {status === 'processing' && (
          <Spinner size="lg" className="mb-4" />
        )}
        
        {status === 'success' && (
          <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 mb-4">
            <p className="text-sm text-green-800 dark:text-green-200">
              🎉 歡迎回來！您已成功通過 Discord 身份驗證。
            </p>
          </div>
        )}
        
        {status === 'error' && (
          <div className="space-y-4">
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
              <p className="text-sm text-red-800 dark:text-red-200 mb-2">
                😔 認證過程出現問題
              </p>
              <p className="text-xs text-red-600 dark:text-red-400">
                {message}
              </p>
            </div>
            
            <div className="space-x-2">
              <button
                onClick={() => router.push('/auth/discord')}
                className="btn-primary"
              >
                重新登入
              </button>
              <button
                onClick={() => router.push('/')}
                className="btn-secondary"
              >
                返回首頁
              </button>
            </div>
          </div>
        )}
        
        {status === 'processing' && (
          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <p className="text-sm text-blue-800 dark:text-blue-200">
              ⏳ 正在驗證您的 Discord 帳戶並設置權限...
            </p>
          </div>
        )}
      </div>
    </div>
  )
}