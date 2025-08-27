'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@/lib/auth/auth-context'
import { ApiClient } from '@/lib/api/client'
import { Spinner } from '@/components/ui/spinner'
import toast from 'react-hot-toast'

interface AnalyticsData {
  overview: {
    total_tickets: number
    resolved_tickets: number
    resolution_rate: number
    avg_response_time: number
    satisfaction_score: number
  }
  daily_stats: {
    date: string
    tickets_created: number
    tickets_resolved: number
    response_time: number
  }[]
  staff_performance: {
    staff_id: number
    username: string
    total_assigned: number
    total_completed: number
    avg_completion_time: number
    avg_rating: number
  }[]
  priority_breakdown: {
    high: number
    medium: number
    low: number
  }
}

export default function AnalyticsPage() {
  const { isAuthenticated } = useAuth()
  const [data, setData] = useState<AnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [period, setPeriod] = useState('30d')
  const [reportGenerating, setReportGenerating] = useState(false)

  const fetchAnalytics = async () => {
    try {
      setLoading(true)
      setError(null)

      const [dashboardResponse, staffResponse] = await Promise.all([
        ApiClient.analytics.publicDashboard({ period }),
        // 使用模擬數據代替不存在的API
        Promise.resolve({ data: { data: { staff_count: 5, avg_rating: 4.2, total_tickets: 150 } } })
      ])

      // 確保所有必要的屬性都存在，如果沒有則使用預設值
      const responseData = dashboardResponse.data.data || {}
      const overview = responseData.overview || {
        total_tickets: 0,
        resolved_tickets: 0,
        resolution_rate: 0,
        avg_response_time: 0,
        satisfaction_score: 0
      }

      setData({
        overview,
        daily_stats: responseData.daily_stats || [],
        staff_performance: Array.isArray(staffResponse.data.data) ? staffResponse.data.data : [],
        priority_breakdown: responseData.priority_breakdown || { high: 0, medium: 0, low: 0 }
      })

    } catch (err: any) {
      console.error('獲取分析數據錯誤:', err)
      setError('無法載入分析數據，請重試')
      toast.error('載入數據失敗')
    } finally {
      setLoading(false)
    }
  }

  const generateReport = async (format: string) => {
    try {
      setReportGenerating(true)

      const response = await ApiClient.analytics.generateReport({
        report_type: 'comprehensive',
        format,
        start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        end_date: new Date().toISOString().split('T')[0]
      })

      // 處理文件下載
      if (response.data.data.download_url) {
        window.open(response.data.data.download_url, '_blank')
        toast.success('報告生成成功')
      } else {
        toast.success('報告生成請求已提交')
      }

    } catch (err) {
      toast.error('報告生成失敗')
    } finally {
      setReportGenerating(false)
    }
  }

  useEffect(() => {
    if (isAuthenticated) {
      fetchAnalytics()
    }
  }, [isAuthenticated, period])

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            請先登入
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            您需要登入才能查看分析報告
          </p>
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
            📊 分析報告
          </h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            系統性能分析和統計報告
          </p>
        </div>

        {/* 控制面板 */}
        <div className="card p-6 mb-6">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center space-y-4 md:space-y-0">
            <div className="flex items-center space-x-4">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                時間週期:
              </label>
              <select
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
                className="form-input"
              >
                <option value="7d">過去 7 天</option>
                <option value="30d">過去 30 天</option>
                <option value="90d">過去 90 天</option>
                <option value="1y">過去 1 年</option>
              </select>
            </div>

            <div className="flex space-x-2">
              <button
                onClick={() => generateReport('pdf')}
                disabled={reportGenerating}
                className="btn-secondary"
              >
                {reportGenerating ? <Spinner size="sm" className="mr-2" /> : '📄'}
                生成 PDF 報告
              </button>
              <button
                onClick={() => generateReport('excel')}
                disabled={reportGenerating}
                className="btn-secondary"
              >
                {reportGenerating ? <Spinner size="sm" className="mr-2" /> : '📊'}
                生成 Excel 報告
              </button>
              <button
                onClick={fetchAnalytics}
                className="btn-primary"
              >
                🔄 刷新數據
              </button>
            </div>
          </div>
        </div>

        {/* 載入狀態 */}
        {loading && (
          <div className="flex justify-center py-8">
            <Spinner size="lg" />
          </div>
        )}

        {/* 錯誤狀態 */}
        {error && (
          <div className="text-center py-8">
            <p className="text-red-500 mb-4">{error}</p>
            <button onClick={fetchAnalytics} className="btn-primary">
              重新載入
            </button>
          </div>
        )}

        {/* 分析數據 */}
        {data && !loading && (
          <div className="space-y-8">
            {/* 總覽統計 */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
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
                      {(data.overview?.total_tickets || 0).toLocaleString()}
                    </p>
                  </div>
                </div>
              </div>

              <div className="card p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="w-8 h-8 bg-green-500 rounded-lg flex items-center justify-center">
                      <span className="text-white text-sm font-bold">✅</span>
                    </div>
                  </div>
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-500 dark:text-gray-400">已解決</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {(data.overview?.resolved_tickets || 0).toLocaleString()}
                    </p>
                  </div>
                </div>
              </div>

              <div className="card p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="w-8 h-8 bg-purple-500 rounded-lg flex items-center justify-center">
                      <span className="text-white text-sm font-bold">📈</span>
                    </div>
                  </div>
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-500 dark:text-gray-400">解決率</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {(data.overview?.resolution_rate || 0).toFixed(1)}%
                    </p>
                  </div>
                </div>
              </div>

              <div className="card p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="w-8 h-8 bg-orange-500 rounded-lg flex items-center justify-center">
                      <span className="text-white text-sm font-bold">⏱️</span>
                    </div>
                  </div>
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-500 dark:text-gray-400">平均回應</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {(data.overview?.avg_response_time || 0).toFixed(1)}h
                    </p>
                  </div>
                </div>
              </div>

              <div className="card p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="w-8 h-8 bg-yellow-500 rounded-lg flex items-center justify-center">
                      <span className="text-white text-sm font-bold">⭐</span>
                    </div>
                  </div>
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-500 dark:text-gray-400">滿意度</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {(data.overview?.satisfaction_score || 0).toFixed(1)}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* 優先級分布 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <div className="card p-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                  🎯 優先級分布
                </h3>
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="text-red-600 font-medium">🔴 高優先級</span>
                    <span className="font-semibold">{data.priority_breakdown?.high || 0}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-3 dark:bg-gray-700">
                    <div
                      className="bg-red-600 h-3 rounded-full"
                      style={{
                        width: `${(data.priority_breakdown?.high || 0) / Math.max(data.overview?.total_tickets || 1, 1) * 100}%`
                      }}
                    ></div>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-yellow-600 font-medium">🟡 中優先級</span>
                    <span className="font-semibold">{data.priority_breakdown?.medium || 0}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-3 dark:bg-gray-700">
                    <div
                      className="bg-yellow-600 h-3 rounded-full"
                      style={{
                        width: `${(data.priority_breakdown?.medium || 0) / Math.max(data.overview?.total_tickets || 1, 1) * 100}%`
                      }}
                    ></div>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-green-600 font-medium">🟢 低優先級</span>
                    <span className="font-semibold">{data.priority_breakdown?.low || 0}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-3 dark:bg-gray-700">
                    <div
                      className="bg-green-600 h-3 rounded-full"
                      style={{
                        width: `${(data.priority_breakdown?.low || 0) / Math.max(data.overview?.total_tickets || 1, 1) * 100}%`
                      }}
                    ></div>
                  </div>
                </div>
              </div>

              {/* 客服績效 */}
              <div className="card p-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                  👥 客服績效排行
                </h3>
                <div className="space-y-4">
                  {(data.staff_performance || []).slice(0, 5).map((staff, index) => (
                    <div key={staff.staff_id} className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <span className="font-semibold text-gray-600 dark:text-gray-400">
                          #{index + 1}
                        </span>
                        <span className="font-medium text-gray-900 dark:text-white">
                          {staff.username}
                        </span>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">
                          {staff.total_completed} 已完成
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          ⭐ {staff.avg_rating?.toFixed(1) || 'N/A'}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 每日統計趨勢 */}
            {data.daily_stats && data.daily_stats.length > 0 && (
              <div className="card p-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                  📈 每日趨勢 (最近 7 天)
                </h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full">
                    <thead>
                      <tr className="border-b border-gray-200 dark:border-gray-700">
                        <th className="text-left py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                          日期
                        </th>
                        <th className="text-center py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                          新建票券
                        </th>
                        <th className="text-center py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                          解決票券
                        </th>
                        <th className="text-center py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                          回應時間
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.daily_stats.slice(-7).map((stat, index) => (
                        <tr key={index} className="border-b border-gray-100 dark:border-gray-800">
                          <td className="py-3 text-sm text-gray-900 dark:text-white">
                            {new Date(stat.date).toLocaleDateString('zh-TW')}
                          </td>
                          <td className="py-3 text-sm text-center text-gray-900 dark:text-white">
                            {stat.tickets_created}
                          </td>
                          <td className="py-3 text-sm text-center text-gray-900 dark:text-white">
                            {stat.tickets_resolved}
                          </td>
                          <td className="py-3 text-sm text-center text-gray-900 dark:text-white">
                            {stat.response_time.toFixed(1)}h
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 底部資訊 */}
        <div className="mt-8 text-center text-sm text-gray-500 dark:text-gray-400">
          <p>數據統計週期：{period === '7d' ? '過去 7 天' : period === '30d' ? '過去 30 天' : period === '90d' ? '過去 90 天' : '過去 1 年'}</p>
          <p>最後更新：{new Date().toLocaleString('zh-TW')}</p>
        </div>
      </div>
    </div>
  )
}
