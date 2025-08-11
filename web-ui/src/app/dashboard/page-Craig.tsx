'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@/lib/auth/auth-context'
import { TicketsAPI, TicketStatsResponse } from '@/lib/api/tickets'
import { Spinner } from '@/components/ui/spinner'
import toast from 'react-hot-toast'

interface DashboardData {
  tickets: TicketStatsResponse
  system: {
    uptime: number
    memory_usage: number
    cpu_usage: number
    active_connections: number
  }
  analytics: {
    daily_tickets: Array<{
      date: string
      created: number
      closed: number
      pending: number
    }>
    resolution_rate: number
    satisfaction_score: number
  }
}

export default function DashboardPage() {
  const { isAuthenticated, user } = useAuth()
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchDashboardData = async () => {
    try {
      setLoading(true)
      setError(null)

      // 並行獲取多個 API 數據
      const [ticketsStats, dailyStats] = await Promise.all([
        TicketsAPI.getStats(),
        TicketsAPI.getDailyStats(30)
      ])

      // 模擬系統數據（實際應該從 API 獲取）
      const systemData = {
        uptime: Math.floor(Math.random() * 86400) + 3600, // 1-24小時
        memory_usage: Math.random() * 80 + 10, // 10-90%
        cpu_usage: Math.random() * 50 + 5, // 5-55%
        active_connections: Math.floor(Math.random() * 100) + 10 // 10-110
      }

      setData({
        tickets: ticketsStats,
        system: systemData,
        analytics: {
          daily_tickets: dailyStats.data,
          resolution_rate: ticketsStats.closed_tickets / Math.max(ticketsStats.total_tickets, 1) * 100,
          satisfaction_score: ticketsStats.avg_rating || 0
        }
      })

    } catch (err: any) {
      console.error('獲取儀表板數據錯誤:', err)
      setError('無法載入儀表板數據，請重試')
      toast.error('載入數據失敗')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isAuthenticated) {
      fetchDashboardData()
    }
  }, [isAuthenticated])

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            請先登入
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            您需要登入才能查看儀表板
          </p>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Spinner size="lg" className="mb-4" />
          <p className="text-gray-600 dark:text-gray-400">載入儀表板數據中...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-500 mb-4">
            <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            載入錯誤
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            {error}
          </p>
          <button
            onClick={fetchDashboardData}
            className="btn-primary"
          >
            重新載入
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {/* 頁面標題 */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            📊 管理儀表板
          </h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            系統總覽和關鍵性能指標
          </p>
        </div>

        {/* 統計卡片 */}
        {data && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {/* 總票券數 */}
            <div className="card p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
                    <span className="text-white text-sm font-bold">🎫</span>
                  </div>
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">總票券數</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">
                    {data.tickets.total_tickets.toLocaleString()}
                  </p>
                </div>
              </div>
            </div>

            {/* 開放票券 */}
            <div className="card p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 bg-green-500 rounded-lg flex items-center justify-center">
                    <span className="text-white text-sm font-bold">🟢</span>
                  </div>
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">開放票券</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">
                    {data.tickets.open_tickets.toLocaleString()}
                  </p>
                </div>
              </div>
            </div>

            {/* 高優先級票券 */}
            <div className="card p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 bg-red-500 rounded-lg flex items-center justify-center">
                    <span className="text-white text-sm font-bold">🔴</span>
                  </div>
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">處理中票券</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">
                    {data.tickets.in_progress_tickets.toLocaleString()}
                  </p>
                </div>
              </div>
            </div>

            {/* 平均回應時間 */}
            <div className="card p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 bg-purple-500 rounded-lg flex items-center justify-center">
                    <span className="text-white text-sm font-bold">⏱️</span>
                  </div>
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">平均解決時間</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">
                    {data.tickets.avg_resolution_time ? `${data.tickets.avg_resolution_time.toFixed(1)}h` : 'N/A'}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 系統狀態和快速操作 */}
        {data && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* 系統狀態 */}
            <div className="card p-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                🖥️ 系統狀態
              </h3>
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-gray-600 dark:text-gray-400">系統運行時間</span>
                  <span className="font-semibold text-gray-900 dark:text-white">
                    {Math.floor(data.system.uptime / 3600)}h
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600 dark:text-gray-400">記憶體使用率</span>
                  <div className="flex items-center space-x-2">
                    <div className="w-20 bg-gray-200 rounded-full h-2 dark:bg-gray-700">
                      <div 
                        className="bg-blue-600 h-2 rounded-full" 
                        style={{ width: `${data.system.memory_usage}%` }}
                      ></div>
                    </div>
                    <span className="font-semibold text-gray-900 dark:text-white">
                      {data.system.memory_usage.toFixed(1)}%
                    </span>
                  </div>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600 dark:text-gray-400">CPU 使用率</span>
                  <div className="flex items-center space-x-2">
                    <div className="w-20 bg-gray-200 rounded-full h-2 dark:bg-gray-700">
                      <div 
                        className="bg-green-600 h-2 rounded-full" 
                        style={{ width: `${data.system.cpu_usage}%` }}
                      ></div>
                    </div>
                    <span className="font-semibold text-gray-900 dark:text-white">
                      {data.system.cpu_usage.toFixed(1)}%
                    </span>
                  </div>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600 dark:text-gray-400">活躍連線</span>
                  <span className="font-semibold text-gray-900 dark:text-white">
                    {data.system.active_connections}
                  </span>
                </div>
              </div>
            </div>

            {/* 快速操作 */}
            <div className="card p-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                ⚡ 快速操作
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <button className="btn-secondary text-left p-4">
                  <div className="font-semibold">🎫 票券管理</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    查看和管理票券
                  </div>
                </button>
                <button className="btn-secondary text-left p-4">
                  <div className="font-semibold">📊 分析報告</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    生成統計報告
                  </div>
                </button>
                <button className="btn-secondary text-left p-4">
                  <div className="font-semibold">🔧 系統設定</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    管理系統配置
                  </div>
                </button>
                <button 
                  onClick={fetchDashboardData}
                  className="btn-secondary text-left p-4"
                >
                  <div className="font-semibold">🔄 刷新數據</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    重新載入數據
                  </div>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 底部資訊 */}
        <div className="mt-8 text-center text-sm text-gray-500 dark:text-gray-400">
          <p>最後更新：{new Date().toLocaleString('zh-TW')}</p>
        </div>
      </div>
    </div>
  )
}