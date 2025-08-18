'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@/lib/auth/auth-context'
import { ApiClient } from '@/lib/api/client'
import { Spinner } from '@/components/ui/spinner'
import toast from 'react-hot-toast'

interface ApiKey {
  key_id: string
  name: string
  permission_level: string
  guild_id?: number
  created_at: string
  last_used_at?: string
  expires_at?: string
  is_active: boolean
  usage_count: number
}

interface SystemHealth {
  status: string
  timestamp: string
  uptime: number
  version: string
  components: Record<string, string>
  metrics: {
    cpu_usage: number
    memory_usage: number
    disk_usage: number
    database_connections: number
    active_tickets: number
    api_requests_per_minute: number
    bot_latency: number
  }
}

export default function ApiManagementPage() {
  const { isAuthenticated } = useAuth()
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([])
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)

  const [newKeyForm, setNewKeyForm] = useState({
    name: '',
    permission_level: 'read_only',
    guild_id: '',
    expires_days: '30'
  })

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)

      // 優先使用公開版本的系統 API，認證版本僅用於 API 金鑰管理
      let keysResponse, healthResponse, systemResponse
      
      try {
        // 並行獲取數據：API 金鑰需要認證，系統指標使用公開版本
        [keysResponse, healthResponse, systemResponse] = await Promise.all([
          ApiClient.system.apiKeys.list().catch(() => ({ data: { data: [] } })), // 如果失敗返回空數組
          ApiClient.system.publicHealth(),
          ApiClient.system.publicMetrics()
        ])
      } catch (error: any) {
        console.warn('API 調用失敗:', error)
        // 設置默認值
        keysResponse = { data: { data: [] } }
        healthResponse = { data: { data: { status: 'unknown', components: {}, metrics: {} } } }
        systemResponse = { data: { data: { cpu_usage: 0, memory_usage: 0, disk_usage: 0 } } }
      }

      setApiKeys(keysResponse.data.data || [])
      
      // 安全地合併系統健康數據和指標數據
      const healthData = healthResponse.data.data || healthResponse.data || {}
      const metricsData = systemResponse.data.data || systemResponse.data || {}
      
      setSystemHealth({
        status: healthData.status || 'unknown',
        timestamp: healthData.timestamp || new Date().toISOString(),
        uptime: healthData.uptime || 0,
        version: healthData.version || '1.8.0',
        components: healthData.components || {},
        metrics: {
          cpu_usage: metricsData.cpu_usage || 0,
          memory_usage: metricsData.memory_usage || 0,
          disk_usage: metricsData.disk_usage || 0,
          database_connections: metricsData.database_connections || 0,
          active_tickets: metricsData.active_tickets || 0,
          api_requests_per_minute: metricsData.api_requests_per_minute || 0,
          bot_latency: metricsData.bot_latency || 0
        }
      })

    } catch (err: any) {
      console.error('獲取 API 管理數據錯誤:', err)
      setError('無法載入 API 管理數據，請重試')
      toast.error('載入數據失敗')
    } finally {
      setLoading(false)
    }
  }

  const createApiKey = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newKeyForm.name.trim()) {
      toast.error('請輸入 API 金鑰名稱')
      return
    }

    try {
      setCreateLoading(true)

      const data: any = {
        name: newKeyForm.name,
        permission_level: newKeyForm.permission_level,
        expires_days: parseInt(newKeyForm.expires_days) || undefined
      }

      if (newKeyForm.guild_id) {
        data.guild_id = parseInt(newKeyForm.guild_id)
      }

      const response = await ApiClient.system.apiKeys.create(data)
      
      toast.success('API 金鑰創建成功')
      
      // 顯示新建的金鑰（只顯示一次）
      if (response.data.data.api_key) {
        toast(
          `新的 API 金鑰 (請保存): ${response.data.data.api_key}`,
          { duration: 10000 }
        )
      }

      setShowCreateForm(false)
      setNewKeyForm({ name: '', permission_level: 'read_only', guild_id: '', expires_days: '30' })
      fetchData()

    } catch (err) {
      toast.error('創建 API 金鑰失敗')
    } finally {
      setCreateLoading(false)
    }
  }

  const revokeApiKey = async (keyId: string) => {
    if (!confirm('確定要撤銷此 API 金鑰嗎？此操作無法復原。')) {
      return
    }

    try {
      await ApiClient.system.apiKeys.revoke(keyId)
      toast.success('API 金鑰已撤銷')
      fetchData()
    } catch (err) {
      toast.error('撤銷 API 金鑰失敗')
    }
  }

  const getPermissionBadge = (level: string) => {
    const configs = {
      'admin': { bg: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300', text: '管理員' },
      'write': { bg: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300', text: '讀寫' },
      'read_only': { bg: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300', text: '唯讀' }
    }

    const config = configs[level as keyof typeof configs] || configs.read_only
    return (
      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${config.bg}`}>
        {config.text}
      </span>
    )
  }

  const getStatusBadge = (status: string) => {
    return status === 'healthy' ? (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300">
        <span className="w-2 h-2 mr-1.5 bg-green-400 rounded-full"></span>
        正常運行
      </span>
    ) : (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300">
        <span className="w-2 h-2 mr-1.5 bg-red-400 rounded-full"></span>
        異常
      </span>
    )
  }

  useEffect(() => {
    if (isAuthenticated) {
      fetchData()
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
            您需要登入才能管理 API
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
            🔧 API 管理
          </h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            系統狀態監控和 API 金鑰管理
          </p>
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
            <button onClick={fetchData} className="btn-primary">
              重新載入
            </button>
          </div>
        )}

        {/* 主要內容 */}
        {systemHealth && !loading && (
          <div className="space-y-8">
            {/* 系統健康狀態 */}
            <div className="card p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                  🖥️ 系統狀態
                </h2>
                {getStatusBadge(systemHealth.status)}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <div className="space-y-2">
                  <p className="text-sm text-gray-500 dark:text-gray-400">系統版本</p>
                  <p className="text-lg font-semibold text-gray-900 dark:text-white">
                    {systemHealth.version}
                  </p>
                </div>
                <div className="space-y-2">
                  <p className="text-sm text-gray-500 dark:text-gray-400">運行時間</p>
                  <p className="text-lg font-semibold text-gray-900 dark:text-white">
                    {Math.floor(systemHealth.uptime / 3600)}h {Math.floor((systemHealth.uptime % 3600) / 60)}m
                  </p>
                </div>
                <div className="space-y-2">
                  <p className="text-sm text-gray-500 dark:text-gray-400">Bot 延遲</p>
                  <p className="text-lg font-semibold text-gray-900 dark:text-white">
                    {systemHealth.metrics.bot_latency.toFixed(0)}ms
                  </p>
                </div>
                <div className="space-y-2">
                  <p className="text-sm text-gray-500 dark:text-gray-400">API 請求/分鐘</p>
                  <p className="text-lg font-semibold text-gray-900 dark:text-white">
                    {systemHealth.metrics.api_requests_per_minute}
                  </p>
                </div>
              </div>

              {/* 系統資源使用率 */}
              <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6">
                <div>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-gray-600 dark:text-gray-400">CPU 使用率</span>
                    <span className="font-medium">{systemHealth.metrics.cpu_usage.toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2 dark:bg-gray-700">
                    <div 
                      className="bg-blue-600 h-2 rounded-full transition-all" 
                      style={{ width: `${systemHealth.metrics.cpu_usage}%` }}
                    ></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-gray-600 dark:text-gray-400">記憶體使用率</span>
                    <span className="font-medium">{systemHealth.metrics.memory_usage.toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2 dark:bg-gray-700">
                    <div 
                      className="bg-green-600 h-2 rounded-full transition-all" 
                      style={{ width: `${systemHealth.metrics.memory_usage}%` }}
                    ></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-gray-600 dark:text-gray-400">磁碟使用率</span>
                    <span className="font-medium">{systemHealth.metrics.disk_usage.toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2 dark:bg-gray-700">
                    <div 
                      className="bg-yellow-600 h-2 rounded-full transition-all" 
                      style={{ width: `${systemHealth.metrics.disk_usage}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            </div>

            {/* API 金鑰管理 */}
            <div className="card p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                  🔑 API 金鑰管理
                </h2>
                <button
                  onClick={() => setShowCreateForm(!showCreateForm)}
                  className="btn-primary"
                >
                  ➕ 創建新金鑰
                </button>
              </div>

              {/* 創建表單 */}
              {showCreateForm && (
                <form onSubmit={createApiKey} className="bg-gray-50 dark:bg-gray-800 p-4 rounded-lg mb-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div>
                      <label className="form-label">金鑰名稱 *</label>
                      <input
                        type="text"
                        value={newKeyForm.name}
                        onChange={(e) => setNewKeyForm({ ...newKeyForm, name: e.target.value })}
                        className="form-input"
                        placeholder="例: Web Dashboard"
                        required
                      />
                    </div>
                    
                    <div>
                      <label className="form-label">權限等級</label>
                      <select
                        value={newKeyForm.permission_level}
                        onChange={(e) => setNewKeyForm({ ...newKeyForm, permission_level: e.target.value })}
                        className="form-input"
                      >
                        <option value="read_only">唯讀</option>
                        <option value="write">讀寫</option>
                        <option value="admin">管理員</option>
                      </select>
                    </div>
                    
                    <div>
                      <label className="form-label">過期天數</label>
                      <input
                        type="number"
                        value={newKeyForm.expires_days}
                        onChange={(e) => setNewKeyForm({ ...newKeyForm, expires_days: e.target.value })}
                        className="form-input"
                        min="1"
                        max="365"
                      />
                    </div>
                    
                    <div>
                      <label className="form-label">限制伺服器 ID</label>
                      <input
                        type="text"
                        value={newKeyForm.guild_id}
                        onChange={(e) => setNewKeyForm({ ...newKeyForm, guild_id: e.target.value })}
                        className="form-input"
                        placeholder="選填"
                      />
                    </div>
                  </div>
                  
                  <div className="flex justify-end space-x-2 mt-4">
                    <button
                      type="button"
                      onClick={() => setShowCreateForm(false)}
                      className="btn-secondary"
                    >
                      取消
                    </button>
                    <button
                      type="submit"
                      disabled={createLoading}
                      className="btn-primary"
                    >
                      {createLoading ? <Spinner size="sm" className="mr-2" /> : ''}
                      創建金鑰
                    </button>
                  </div>
                </form>
              )}

              {/* API 金鑰列表 */}
              <div className="space-y-4">
                {apiKeys.length === 0 ? (
                  <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                    尚未創建任何 API 金鑰
                  </div>
                ) : (
                  apiKeys.map((apiKey) => (
                    <div key={apiKey.key_id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-3 mb-2">
                            <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                              {apiKey.name}
                            </h3>
                            {getPermissionBadge(apiKey.permission_level)}
                            {!apiKey.is_active && (
                              <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300">
                                已撤銷
                              </span>
                            )}
                          </div>
                          
                          <div className="flex flex-wrap items-center text-sm text-gray-500 dark:text-gray-400 space-x-4">
                            <span>🆔 {apiKey.key_id}</span>
                            <span>📅 創建: {new Date(apiKey.created_at).toLocaleDateString('zh-TW')}</span>
                            {apiKey.last_used_at && (
                              <span>🕒 最後使用: {new Date(apiKey.last_used_at).toLocaleDateString('zh-TW')}</span>
                            )}
                            <span>📊 使用次數: {apiKey.usage_count}</span>
                            {apiKey.expires_at && (
                              <span>⏰ 過期: {new Date(apiKey.expires_at).toLocaleDateString('zh-TW')}</span>
                            )}
                          </div>
                        </div>

                        {apiKey.is_active && (
                          <button
                            onClick={() => revokeApiKey(apiKey.key_id)}
                            className="ml-4 text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
                          >
                            ❌ 撤銷
                          </button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* 操作按鈕 */}
            <div className="flex justify-center">
              <button
                onClick={fetchData}
                className="btn-primary"
              >
                🔄 刷新數據
              </button>
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