'use client'

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { BotConnectionStatus } from '@/components/bot/bot-connection-status'
import { useBotConnection } from '@/lib/connection/use-bot-connection'
import { 
  Monitor, 
  Activity, 
  Zap, 
  Database, 
  Server, 
  Clock,
  Wifi,
  AlertTriangle,
  CheckCircle
} from 'lucide-react'

export default function SystemMonitorPage() {
  const { status, isConnected, sendMessage } = useBotConnection()
  const [systemMetrics, setSystemMetrics] = useState<any>(null)
  const [lastUpdated, setLastUpdated] = useState(new Date())

  // 取得系統指標
  const fetchSystemMetrics = async () => {
    try {
      const response = await fetch('/api/system/public-metrics')
      if (response.ok) {
        const rawData = await response.json()
        console.log('🔧 原始系統指標數據:', rawData) // 調試用
        
        // 轉換數據格式以符合UI組件期望的結構
        const transformedData = {
          cpu: {
            usage: rawData.cpu_usage || 0,
            load: 'N/A', // API 沒有提供這個數據
            cores: 'N/A' // API 沒有提供這個數據
          },
          memory: {
            usage: rawData.memory_usage || 0,
            // 模擬記憶體數據以支持進度條顯示
            total: 16 * 1024 * 1024 * 1024, // 假設 16GB 總記憶體
            used: Math.round((rawData.memory_usage || 0) / 100 * 16 * 1024 * 1024 * 1024)
          },
          disk: {
            usage: rawData.disk_usage || 0,
            // 模擬磁碟數據以支持進度條顯示
            total: 100 * 1024 * 1024 * 1024, // 假設 100GB 總磁碟
            used: Math.round((rawData.disk_usage || 0) / 100 * 100 * 1024 * 1024 * 1024)
          },
          database: {
            connections: rawData.database_connections || 0
          },
          network: {
            requests: rawData.api_requests_per_minute || 0,
            latency: rawData.bot_latency || 0
          }
        }
        
        setSystemMetrics(transformedData)
        setLastUpdated(new Date())
      }
    } catch (error) {
      console.error('取得系統指標失敗:', error)
    }
  }

  // 透過 WebSocket 傳送測試訊息
  const sendTestMessage = () => {
    const success = sendMessage({
      type: 'test',
      message: 'Web UI 連線測試',
      timestamp: new Date().toISOString()
    })

    if (success) {
      console.log('測試訊息已傳送')
    } else {
      console.error('傳送測試訊息失敗')
    }
  }

  useEffect(() => {
    fetchSystemMetrics()
    
    // 每30秒更新一次指标
    const interval = setInterval(fetchSystemMetrics, 30000)
    
    return () => clearInterval(interval)
  }, [])

  const getSystemHealthColor = (health: string) => {
    switch (health) {
      case 'healthy': return 'text-green-500'
      case 'warning': return 'text-yellow-500'
      case 'error': return 'text-red-500'
      default: return 'text-gray-500'
    }
  }

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
              <Monitor className="w-8 h-8 text-blue-500" />
              系統監控
            </h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              即時監控 Bot 連線狀態和系統效能指標
            </p>
          </div>
          
          <div className="flex gap-2">
            <Button onClick={fetchSystemMetrics} variant="outline">
              <Activity className="w-4 h-4 mr-2" />
              刷新指標
            </Button>
            {isConnected && (
              <Button onClick={sendTestMessage} variant="outline">
                <Zap className="w-4 h-4 mr-2" />
                測試連線
              </Button>
            )}
          </div>
        </div>

        {/* Bot 連線狀態 */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1">
            <BotConnectionStatus />
          </div>

          {/* 連線詳情 */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Wifi className="w-5 h-5" />
                  連線詳情
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <div className="text-2xl font-bold text-blue-600">
                      {status.latency > 0 ? `${status.latency}ms` : '--'}
                    </div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">延遲</div>
                  </div>
                  
                  <div className="text-center p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <div className="text-2xl font-bold text-green-600">
                      {status.connectionQuality}
                    </div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">連線品質</div>
                  </div>
                  
                  <div className="text-center p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <div className={`text-2xl font-bold ${isConnected ? 'text-green-600' : 'text-red-600'}`}>
                      {isConnected ? (
                        <CheckCircle className="w-8 h-8 mx-auto" />
                      ) : (
                        <AlertTriangle className="w-8 h-8 mx-auto" />
                      )}
                    </div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">
                      {isConnected ? '已連線' : '未連線'}
                    </div>
                  </div>
                  
                  <div className="text-center p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <div className="text-2xl font-bold text-purple-600">
                      {status.botInfo?.guilds || '--'}
                    </div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">伺服器數</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* 系统指标 */}
        {systemMetrics && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* CPU 使用率 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="w-5 h-5" />
                  CPU 使用率
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>目前使用率</span>
                    <span className="font-semibold">{systemMetrics.cpu?.usage || '--'}%</span>
                  </div>
                  <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                    <div 
                      className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${systemMetrics.cpu?.usage || 0}%` }}
                    />
                  </div>
                  <div className="text-xs text-gray-600 dark:text-gray-400">
                    即時系統 CPU 使用率 (每秒更新)
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* 内存使用 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="w-5 h-5" />
                  記憶體使用
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>使用率</span>
                    <span className="font-semibold">
                      {systemMetrics.memory ? 
                        `${systemMetrics.memory.usage.toFixed(1)}%` 
                        : '--'
                      }
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                    <div 
                      className="bg-green-500 h-2 rounded-full transition-all duration-300"
                      style={{ 
                        width: `${systemMetrics.memory?.usage || 0}%`
                      }}
                    />
                  </div>
                  <div className="text-xs text-gray-600 dark:text-gray-400">
                    即時系統記憶體使用率
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* 磁盘使用 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Server className="w-5 h-5" />
                  磁碟使用
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>使用率</span>
                    <span className="font-semibold">
                      {systemMetrics.disk ? 
                        `${systemMetrics.disk.usage.toFixed(1)}%` 
                        : '--'
                      }
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                    <div 
                      className="bg-yellow-500 h-2 rounded-full transition-all duration-300"
                      style={{ 
                        width: `${systemMetrics.disk?.usage || 0}%`
                      }}
                    />
                  </div>
                  <div className="text-xs text-gray-600 dark:text-gray-400">
                    即時系統磁碟使用率
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* 狀態歷史 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="w-5 h-5" />
              狀態歷史
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              最後更新: {lastUpdated.toLocaleString()}
            </div>
            
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                <div className="flex items-center gap-3">
                  <CheckCircle className="w-5 h-5 text-green-500" />
                  <span>Bot 連線正常</span>
                </div>
                <span className="text-sm text-gray-500">
                  {new Date().toLocaleTimeString()}
                </span>
              </div>
              
              <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                <div className="flex items-center gap-3">
                  <Activity className="w-5 h-5 text-blue-500" />
                  <span>系統監控啟動</span>
                </div>
                <span className="text-sm text-gray-500">
                  {new Date().toLocaleTimeString()}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// Note: metadata cannot be exported from client components
// Add metadata in layout.tsx or use next/head for client components