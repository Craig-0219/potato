'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@/lib/auth/auth-context'
import { systemHealth, SystemHealthReport } from '@/lib/utils/system-health'
import { performanceMonitor, networkMonitor } from '@/lib/utils/performance-monitor'
import { apiCache } from '@/lib/utils/cache-manager'
import { Spinner } from '@/components/ui/spinner'
import toast from 'react-hot-toast'

export default function SystemPage() {
  const { isAuthenticated, hasPermission } = useAuth()
  const [healthReport, setHealthReport] = useState<SystemHealthReport | null>(null)
  const [wsConnected, setWsConnected] = useState(false)
  const [wsState, setWsState] = useState('disconnected')
  const [loading, setLoading] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)

  const runHealthCheck = async () => {
    if (loading) return
    
    try {
      setLoading(true)
      const report = await systemHealth.runHealthCheck()
      setHealthReport(report)
      
      if (report.overall === 'error') {
        toast.error('檢測到系統問題')
      } else if (report.overall === 'warning') {
        toast('系統狀態需要關注', { icon: '⚠️' })
      }
    } catch (error) {
      toast.error('健康檢查失敗')
      console.error('健康檢查錯誤:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'text-green-600 bg-green-100 border-green-200'
      case 'warning':
        return 'text-yellow-600 bg-yellow-100 border-yellow-200'
      case 'error':
        return 'text-red-600 bg-red-100 border-red-200'
      default:
        return 'text-gray-600 bg-gray-100 border-gray-200'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return '✅'
      case 'warning':
        return '⚠️'
      case 'error':
        return '❌'
      default:
        return '❓'
    }
  }

  const clearAllCaches = () => {
    apiCache.clear()
    performanceMonitor.clearStats()
    toast.success('所有緩存已清除')
  }

  const exportSystemReport = () => {
    if (!healthReport) return

    const report = {
      healthReport,
      performanceStats: performanceMonitor.getStats,
      networkStats: networkMonitor.getNetworkStats(),
      cacheStats: apiCache.getStats(),
      timestamp: new Date().toISOString()
    }

    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: 'application/json'
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `system-report-${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    
    toast.success('系統報告已匯出')
  }

  // 自動刷新
  useEffect(() => {
    if (!autoRefresh || !isAuthenticated) return

    const interval = setInterval(() => {
      runHealthCheck()
    }, 30000) // 每 30 秒刷新一次

    return () => clearInterval(interval)
  }, [autoRefresh, isAuthenticated])

  // 初始健康檢查
  useEffect(() => {
    if (isAuthenticated) {
      runHealthCheck()
    }
  }, [isAuthenticated])

  // 檢查 WebSocket 連接狀態
  useEffect(() => {
    const checkWebSocketStatus = async () => {
      try {
        // 嘗試導入 WebSocket 提供者
        const { useWebSocket } = await import('@/lib/websocket/websocket-provider')
        // 在客戶端環境中使用
        if (typeof window !== 'undefined') {
          // 模擬 WebSocket 狀態檢查
          setWsConnected(false)
          setWsState('checking')
        }
      } catch (error) {
        setWsConnected(false)
        setWsState('unavailable')
      }
    }

    if (typeof window !== 'undefined') {
      checkWebSocketStatus()
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
            您需要登入才能查看系統狀態
          </p>
        </div>
      </div>
    )
  }

  if (!hasPermission('admin')) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            權限不足
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            您需要管理員權限才能查看系統狀態
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {/* 頁面標題和控制項 */}
        <div className="mb-8">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                🖥️ 系統監控
              </h1>
              <p className="mt-2 text-gray-600 dark:text-gray-400">
                即時系統健康狀態和性能監控
              </p>
            </div>
            
            <div className="flex space-x-4">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="mr-2"
                />
                <span className="text-sm">自動刷新</span>
              </label>
              
              <button
                onClick={clearAllCaches}
                className="btn-secondary"
              >
                🗑️ 清除緩存
              </button>
              
              <button
                onClick={exportSystemReport}
                disabled={!healthReport}
                className="btn-secondary disabled:opacity-50"
              >
                📄 匯出報告
              </button>

              <button
                onClick={runHealthCheck}
                disabled={loading}
                className="btn-primary disabled:opacity-50"
              >
                {loading ? <Spinner size="sm" className="mr-2" /> : '🔄'}
                檢查健康狀態
              </button>
            </div>
          </div>
        </div>

        {/* 系統總覽 */}
        {healthReport && (
          <div className="mb-8">
            <div className="card p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                  系統總覽
                </h2>
                <div className={`px-4 py-2 rounded-full border ${getStatusColor(healthReport.overall)}`}>
                  <span className="font-semibold">
                    {getStatusIcon(healthReport.overall)} 
                    {healthReport.overall === 'healthy' ? '健康' :
                     healthReport.overall === 'warning' ? '警告' :
                     healthReport.overall === 'error' ? '錯誤' : '未知'}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <div className="text-center">
                  <div className="text-3xl font-bold text-blue-600 mb-2">
                    {healthReport.score}
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    健康分數
                  </div>
                </div>

                <div className="text-center">
                  <div className="text-3xl font-bold text-green-600 mb-2">
                    {healthReport.summary.healthy}
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    正常項目
                  </div>
                </div>

                <div className="text-center">
                  <div className="text-3xl font-bold text-yellow-600 mb-2">
                    {healthReport.summary.warning}
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    警告項目
                  </div>
                </div>

                <div className="text-center">
                  <div className="text-3xl font-bold text-red-600 mb-2">
                    {healthReport.summary.error}
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    錯誤項目
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 詳細健康檢查結果 */}
        {healthReport && (
          <div className="mb-8">
            <div className="card p-6">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
                詳細檢查結果
              </h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {healthReport.checks.map((check, index) => (
                  <div
                    key={index}
                    className={`p-4 rounded-lg border ${getStatusColor(check.status)}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-semibold">
                        {getStatusIcon(check.status)} {check.name}
                      </h3>
                      {check.responseTime && (
                        <span className="text-xs bg-white bg-opacity-50 px-2 py-1 rounded">
                          {check.responseTime.toFixed(0)}ms
                        </span>
                      )}
                    </div>
                    
                    <p className="text-sm mb-2">{check.message}</p>
                    
                    {check.details && (
                      <div className="text-xs space-y-1">
                        {Object.entries(check.details).map(([key, value]) => (
                          <div key={key} className="flex justify-between">
                            <span className="opacity-75">{key}:</span>
                            <span>{String(value)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    
                    <div className="text-xs opacity-50 mt-2">
                      {new Date(check.timestamp).toLocaleString('zh-TW')}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* WebSocket 狀態 */}
        <div className="mb-8">
          <div className="card p-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
              即時連接狀態
            </h2>
            
            <div className="flex items-center space-x-4">
              <div className={`w-4 h-4 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
              <span className="font-medium">
                WebSocket: {wsConnected ? '已連接' : '未連接'}
              </span>
              <span className="text-sm text-gray-600 dark:text-gray-400">
                狀態: {wsState}
              </span>
            </div>
          </div>
        </div>

        {/* 載入狀態 */}
        {loading && !healthReport && (
          <div className="flex justify-center py-16">
            <div className="text-center">
              <Spinner size="lg" className="mb-4" />
              <p className="text-gray-600 dark:text-gray-400">正在進行系統健康檢查...</p>
            </div>
          </div>
        )}

        {/* 底部資訊 */}
        {healthReport && (
          <div className="mt-8 text-center text-sm text-gray-500 dark:text-gray-400">
            <p>
              最後檢查: {new Date(healthReport.generatedAt).toLocaleString('zh-TW')}
              {autoRefresh && ' • 自動刷新: 每 30 秒'}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}