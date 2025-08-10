'use client'

import { useState } from 'react'
import { useAuth } from '@/lib/auth/auth-context'
import { Spinner } from '@/components/ui/spinner'
import toast from 'react-hot-toast'

export function LandingPage() {
  const [apiKey, setApiKey] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const { login } = useAuth()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!apiKey.trim()) {
      toast.error('請輸入 API 金鑰')
      return
    }

    setIsLoading(true)
    try {
      await login(apiKey.trim())
    } catch (error) {
      // 錯誤處理已在 login 函數中完成
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-50 via-white to-discord-50 dark:from-gray-900 dark:via-gray-900 dark:to-gray-800">
      {/* 背景裝飾 */}
      <div className="absolute inset-0 bg-grid-slate-100 [mask-image:linear-gradient(0deg,white,rgba(255,255,255,0.6))] dark:bg-grid-slate-700/25 dark:[mask-image:linear-gradient(0deg,rgba(255,255,255,0.1),rgba(255,255,255,0.5))]" />
      
      <div className="relative flex min-h-screen flex-col justify-center">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            {/* Logo 和標題 */}
            <div className="mb-8">
              <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-discord-600 text-white shadow-xl">
                <span className="text-3xl font-bold">🥔</span>
              </div>
              
              <h1 className="mt-6 text-4xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-6xl">
                <span className="text-gradient">Potato Bot</span>
                <br />
                <span className="text-2xl font-medium text-gray-600 dark:text-gray-400 sm:text-3xl">
                  企業級管理面板
                </span>
              </h1>
              
              <p className="mt-6 text-lg leading-8 text-gray-600 dark:text-gray-400">
                現代化的 Discord 機器人管理界面，提供票券系統、分析統計、自動化工作流程等企業級功能。
                使用您的 API 金鑰登入以開始管理您的 Discord 伺服器。
              </p>
            </div>

            {/* 功能特色 */}
            <div className="mb-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {[
                { icon: '🎫', title: '票券系統', desc: '完整的工單管理' },
                { icon: '📊', title: '分析統計', desc: '實時數據洞察' },
                { icon: '🤖', title: '自動化', desc: '智能工作流程' },
                { icon: '🔐', title: '企業安全', desc: '多層次權限控制' },
              ].map((feature) => (
                <div
                  key={feature.title}
                  className="group rounded-xl bg-white/70 p-6 shadow-soft backdrop-blur-sm transition-all hover:bg-white hover:shadow-medium dark:bg-gray-800/70 dark:hover:bg-gray-800"
                >
                  <div className="text-3xl">{feature.icon}</div>
                  <h3 className="mt-3 font-semibold text-gray-900 dark:text-white">
                    {feature.title}
                  </h3>
                  <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                    {feature.desc}
                  </p>
                </div>
              ))}
            </div>

            {/* 登入表單 */}
            <div className="mx-auto max-w-md">
              <div className="card p-6">
                <h2 className="mb-4 text-xl font-semibold text-gray-900 dark:text-white">
                  使用 API 金鑰登入
                </h2>
                
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <label htmlFor="apiKey" className="form-label">
                      API 金鑰
                    </label>
                    <input
                      id="apiKey"
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      className="form-input"
                      placeholder="pk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                      disabled={isLoading}
                    />
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      請輸入您的 Potato Bot API 金鑰
                    </p>
                  </div>
                  
                  <button
                    type="submit"
                    disabled={isLoading || !apiKey.trim()}
                    className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isLoading ? (
                      <>
                        <Spinner size="sm" className="mr-2" />
                        登入中...
                      </>
                    ) : (
                      '登入管理面板'
                    )}
                  </button>
                </form>

                <div className="mt-4 border-t border-gray-200 pt-4 dark:border-gray-700">
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    還沒有 API 金鑰？
                    <br />
                    請聯繫系統管理員或使用 Discord 機器人的{' '}
                    <code className="rounded bg-gray-100 px-1 text-xs dark:bg-gray-800">
                      /api_key
                    </code>{' '}
                    指令生成。
                  </p>
                </div>
              </div>
            </div>

            {/* 版本信息 */}
            <div className="mt-8 text-sm text-gray-500 dark:text-gray-400">
              Potato Bot Dashboard v1.8.0
              <br />
              現代化企業級 Discord 管理系統
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}