'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense } from 'react'

function AuthErrorContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const error = searchParams.get('error') || 'unknown_error'

  const getErrorMessage = (errorCode: string) => {
    const errorMessages: Record<string, string> = {
      'access_denied': '您取消了 Discord 授權',
      'invalid_request': '認證請求無效',
      'unauthorized_client': '應用程式未獲授權',
      'unsupported_response_type': '不支援的回應類型',
      'invalid_scope': '無效的權限範圍',
      'server_error': 'Discord 伺服器錯誤',
      'temporarily_unavailable': 'Discord 服務暫時不可用',
      'callback_failed': '認證回調處理失敗',
      'token_exchange_failed': '權杖交換失敗',
      'unknown_error': '未知錯誤'
    }

    return errorMessages[errorCode] || errorMessages['unknown_error']
  }

  const getErrorAdvice = (errorCode: string) => {
    const advice: Record<string, string> = {
      'access_denied': '請重新嘗試並同意必要的權限以使用管理面板',
      'invalid_request': '請重新開始登入流程',
      'unauthorized_client': '請聯繫系統管理員檢查應用程式設定',
      'server_error': '請稍後再試，或聯繫 Discord 技術支援',
      'temporarily_unavailable': '請稍後再試',
      'callback_failed': '請檢查網路連接並重新嘗試',
      'token_exchange_failed': '請重新嘗試登入',
      'unknown_error': '請重新嘗試，如果問題持續請聯繫技術支援'
    }

    return advice[errorCode] || advice['unknown_error']
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
      <div className="text-center max-w-md mx-auto px-4">
        <div className="mb-6">
          <div className="w-16 h-16 mx-auto mb-4 bg-red-500 rounded-full flex items-center justify-center text-2xl">
            ❌
          </div>

          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
            認證失敗
          </h1>

          <p className="text-red-600 dark:text-red-400 mb-4">
            {getErrorMessage(error)}
          </p>
        </div>

        <div className="space-y-4">
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
            <p className="text-sm text-red-800 dark:text-red-200 mb-2">
              💡 建議解決方案：
            </p>
            <p className="text-xs text-red-600 dark:text-red-400">
              {getErrorAdvice(error)}
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

          <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
            <details className="text-left">
              <summary className="text-sm text-gray-500 dark:text-gray-400 cursor-pointer">
                技術詳情
              </summary>
              <div className="mt-2 p-3 bg-gray-100 dark:bg-gray-800 rounded text-xs font-mono">
                錯誤代碼: {error}
              </div>
            </details>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function AuthErrorPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-2">載入中...</h1>
        </div>
      </div>
    }>
      <AuthErrorContent />
    </Suspense>
  )
}
