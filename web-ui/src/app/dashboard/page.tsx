'use client'

import { useEffect, useState } from 'react'
import { Spinner } from '@/components/ui/spinner'

interface DashboardData {
  tickets: {
    total: number
    open: number
    closed: number
    high_priority: number
    response_time_avg: number
  }
  system: {
    uptime: number
    memory_usage: number
    cpu_usage: number
    active_connections: number
  }
  analytics: {
    daily_tickets: number
    resolution_rate: number
    satisfaction_score: number
  }
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async () => {
    console.log('🔄 開始獲取儀表板數據')
    try {
      setLoading(true)
      setError(null)

      // 並行獲取多個 API 數據
      const [ticketsRes, metricsRes, healthRes, analyticsRes] = await Promise.all([
        fetch('/api/v1/statistics/tickets'),
        fetch('/api/system/public-metrics'),
        fetch('/api/system/public-health'),
        fetch('/api/analytics/public-dashboard')
      ])

      console.log('✅ API 響應狀態:', {
        tickets: ticketsRes.status,
        metrics: metricsRes.status,
        health: healthRes.status,
        analytics: analyticsRes.status
      })

      const [ticketsData, metricsData, healthData, analyticsData] = await Promise.all([
        ticketsRes.json(),
        metricsRes.json(),
        healthRes.json(),
        analyticsRes.json()
      ])

      console.log('📊 原始數據:', { ticketsData, metricsData, healthData, analyticsData })

      const dashboardData: DashboardData = {
        tickets: {
          total: ticketsData.data?.total || 0,
          open: ticketsData.data?.open || 0,
          closed: ticketsData.data?.closed || 0,
          high_priority: ticketsData.data?.priority_breakdown?.high || 0,
          response_time_avg: ticketsData.data?.avg_resolution_time || 0
        },
        system: {
          uptime: healthData.uptime || 0,
          memory_usage: metricsData.memory_usage || 0,
          cpu_usage: metricsData.cpu_usage || 0,
          active_connections: metricsData.database_connections || 0
        },
        analytics: {
          daily_tickets: analyticsData.data?.daily_tickets || 0,
          resolution_rate: analyticsData.data?.resolution_rate || 0,
          satisfaction_score: analyticsData.data?.satisfaction_score || 0
        }
      }

      console.log('✅ 轉換後的數據:', dashboardData)
      setData(dashboardData)

    } catch (err: any) {
      console.error('❌ 獲取數據失敗:', err)
      setError('載入數據失敗')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    console.log('🚀 Dashboard useEffect 觸發')
    fetchData()
  }, [])

  // 確保數據獲取 - 如果 3秒後還沒有數據，再次嘗試
  useEffect(() => {
    const timer = setTimeout(() => {
      if (!data) {
        console.log('🔄 3秒後重試獲取數據')
        fetchData()
      }
    }, 3000)

    return () => clearTimeout(timer)
  }, [data])

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
          <p className="text-red-500 mb-4">{error}</p>
          <button onClick={fetchData} className="btn-primary">
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
                    {data.tickets.total.toLocaleString()}
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
                    {data.tickets.open.toLocaleString()}
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
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">高優先級</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">
                    {data.tickets.high_priority.toLocaleString()}
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
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">平均回應時間</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">
                    {data.tickets.response_time_avg}h
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 系統狀態 */}
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
                  <span className="text-gray-600 dark:text-gray-400">資料庫連線</span>
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
                  onClick={fetchData}
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
          <div className="mt-2 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
            <p className="text-yellow-800 dark:text-yellow-200 text-xs">
              ℹ️ Bot 即時連接功能暫時停用以避免瀏覽器阻擋問題。如需即時數據，請手動重新整理頁面。
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
