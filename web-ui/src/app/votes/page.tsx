'use client'

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, LineChart, Line, ResponsiveContainer } from 'recharts'
import { 
  Calendar, 
  Users, 
  BarChart3, 
  TrendingUp, 
  Clock, 
  Vote,
  Search,
  Filter,
  Download,
  RefreshCw,
  Eye,
  EyeOff,
  Star,
  FileText,
  Plus,
  Wifi,
  WifiOff,
  Loader2
} from 'lucide-react'
import { formatDate, calculateTimeLeft } from '@/lib/utils'

interface VoteStat {
  id: number
  title: string
  start_time: string
  end_time: string
  is_multiple: boolean
  is_anonymous: boolean
  total_participants: number
  options: Array<{
    option_id: number
    text: string
    votes: number
  }>
}

interface RealTimeData {
  active_votes: VoteStat[]
  recent_completed: VoteStat[]
  today_statistics: {
    votes_created: number
    votes_completed: number
    total_participants: number
  }
  summary: {
    active_count: number
    total_active_participants: number
  }
  last_updated: string
}

interface VoteTrend {
  date: string
  votes: number
  activeVotes: number
}

const COLORS = ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899']

export default function VotesPage() {
  const [realTimeData, setRealTimeData] = useState<RealTimeData | null>(null)
  const [loading, setLoading] = useState(true)
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedTab, setSelectedTab] = useState('overview')
  const [autoRefresh, setAutoRefresh] = useState(true)
  
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 5

  // WebSocket 連接函數 - 暫時禁用以避免 ERR_BLOCKED_BY_CLIENT 錯誤
  const connectWebSocket = useCallback(() => {
    console.log('🚫 WebSocket 連接已禁用以避免瀏覽器阻擋問題')
    setConnectionStatus('disconnected')
    // 直接使用模擬數據
    fallbackToHttpMode()
    return
    
    // 暫時註解掉所有 WebSocket 連接邏輯
    // try {
    //   const guildId = 123456789 // 模擬公會ID，實際應從認證取得
    //   const clientId = `web_client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    //   const wsUrl = `ws://localhost:8000/api/realtime/ws/${guildId}/${clientId}`
    //   
    //   wsRef.current = new WebSocket(wsUrl)
    //   
    //   wsRef.current.onopen = () => {
    //     console.log('WebSocket 連接已建立')
    //     setConnectionStatus('connected')
    //     reconnectAttempts.current = 0
    //     
    //     // 發送心跳
    //     const heartbeat = setInterval(() => {
    //       if (wsRef.current?.readyState === WebSocket.OPEN) {
    //         wsRef.current.send(JSON.stringify({ type: 'ping' }))
    //       } else {
    //         clearInterval(heartbeat)
    //       }
    //     }, 25000)
    //   }
    //   
    //   wsRef.current.onmessage = (event) => {
    //     try {
    //       const message = JSON.parse(event.data)
    //       
    //       switch (message.type) {
    //         case 'initial_data':
    //         case 'data_update':
    //         case 'auto_update':
    //           setRealTimeData(message.data)
    //           setLoading(false)
    //           break
    //         case 'pong':
    //           // 心跳回應
    //           break
    //         default:
    //           console.log('收到未知訊息類型:', message.type)
    //       }
    //     } catch (error) {
    //       console.error('解析 WebSocket 訊息失敗:', error)
    //     }
    //   }
    //   
    //   wsRef.current.onclose = () => {
    //     console.log('WebSocket 連接已關閉')
    //     setConnectionStatus('disconnected')
    //     
    //     // 自動重連
    //     if (reconnectAttempts.current < maxReconnectAttempts && autoRefresh) {
    //       reconnectAttempts.current++
    //       const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
    //       
    //       reconnectTimeoutRef.current = setTimeout(() => {
    //         console.log(`嘗試重連 (${reconnectAttempts.current}/${maxReconnectAttempts})`)
    //         connectWebSocket()
    //       }, delay)
    //     }
    //   }
    //   
    //   wsRef.current.onerror = (error) => {
    //     console.error('WebSocket 錯誤:', error)
    //     setConnectionStatus('disconnected')
    //   }
    //   
    // } catch (error) {
    //   console.error('建立 WebSocket 連接失敗:', error)
    //   setConnectionStatus('disconnected')
    //   // 如果 WebSocket 不可用，使用 HTTP 模式
    //   fallbackToHttpMode()
    // }
  }, [autoRefresh])

  // HTTP 模式備援
  const fallbackToHttpMode = useCallback(async () => {
    console.log('切換到 HTTP 模式')
    try {
      const response = await fetch('/api/realtime/vote-stats/123456789')
      if (response.ok) {
        const data = await response.json()
        setRealTimeData(data)
        setLoading(false)
        setConnectionStatus('disconnected')
        
        // HTTP 模式下的定期更新
        if (autoRefresh) {
          setTimeout(fallbackToHttpMode, 30000)
        }
      }
    } catch (error) {
      console.error('HTTP 模式獲取數據失敗:', error)
      // 使用模擬數據
      setRealTimeData(getMockData())
      setLoading(false)
    }
  }, [autoRefresh])

  // 手動刷新
  const handleManualRefresh = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'request_update' }))
    } else {
      fallbackToHttpMode()
    }
  }, [fallbackToHttpMode])

  // 模擬數據
  const getMockData = (): RealTimeData => ({
    active_votes: [
      {
        id: 1,
        title: '今晚聚餐地點選擇',
        start_time: '2025-08-15T10:00:00Z',
        end_time: '2025-08-15T18:00:00Z',
        is_multiple: false,
        is_anonymous: false,
        total_participants: 45,
        options: [
          { option_id: 1, text: '火鍋店', votes: 20 },
          { option_id: 2, text: '燒肉店', votes: 15 },
          { option_id: 3, text: '日式料理', votes: 10 }
        ]
      },
      {
        id: 3,
        title: '新功能需求評分',
        start_time: '2025-08-13T14:00:00Z',
        end_time: '2025-08-16T14:00:00Z',
        is_multiple: false,
        is_anonymous: true,
        total_participants: 67,
        options: [
          { option_id: 7, text: '⭐⭐⭐⭐⭐ 非常需要', votes: 25 },
          { option_id: 8, text: '⭐⭐⭐⭐ 需要', votes: 20 },
          { option_id: 9, text: '⭐⭐⭐ 普通', votes: 15 },
          { option_id: 10, text: '⭐⭐ 不太需要', votes: 5 },
          { option_id: 11, text: '⭐ 不需要', votes: 2 }
        ]
      }
    ],
    recent_completed: [
      {
        id: 2,
        title: '週末團建活動安排',
        start_time: '2025-08-14T09:00:00Z',
        end_time: '2025-08-14T17:00:00Z',
        is_multiple: true,
        is_anonymous: true,
        total_participants: 32,
        options: [
          { option_id: 4, text: '爬山', votes: 18 },
          { option_id: 5, text: '唱KTV', votes: 8 },
          { option_id: 6, text: '看電影', votes: 6 }
        ]
      }
    ],
    today_statistics: {
      votes_created: 3,
      votes_completed: 1,
      total_participants: 144
    },
    summary: {
      active_count: 2,
      total_active_participants: 112
    },
    last_updated: new Date().toISOString()
  })

  // 初始化連接 - 暫時禁用 WebSocket
  useEffect(() => {
    // connectWebSocket() // 暫時禁用以避免 ERR_BLOCKED_BY_CLIENT
    fallbackToHttpMode() // 直接使用 HTTP 模式
    
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [connectWebSocket])

  // 計算統計數據
  const stats = realTimeData ? {
    totalVotes: realTimeData.today_statistics.total_participants,
    activeVotes: realTimeData.summary.active_count,
    completedVotes: realTimeData.recent_completed.length,
    averageParticipation: realTimeData.summary.active_count > 0 
      ? Math.round(realTimeData.summary.total_active_participants / realTimeData.summary.active_count)
      : 0
  } : { totalVotes: 0, activeVotes: 0, completedVotes: 0, averageParticipation: 0 }

  // 計算選項百分比
  const calculatePercentages = (options: Array<{option_id: number, text: string, votes: number}>) => {
    const total = options.reduce((sum, option) => sum + option.votes, 0)
    return options.map(option => ({
      ...option,
      percentage: total > 0 ? Math.round((option.votes / total) * 100) : 0
    }))
  }

  // 篩選投票
  const allVotes = realTimeData ? [...realTimeData.active_votes, ...realTimeData.recent_completed] : []
  const filteredVotes = allVotes.filter(vote => 
    vote.title.toLowerCase().includes(searchQuery.toLowerCase())
  )

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-brand-500" />
          <span className="text-gray-600 dark:text-gray-400">連接實時投票系統中...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
      {/* 頁面標題 */}
      <div className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700 sticky top-16 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="py-4 sm:py-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                  <Vote className="w-6 h-6 sm:w-8 sm:h-8 text-brand-500" />
                  實時投票統計
                  {connectionStatus === 'connected' && (
                    <span title="實時連接中">
                      <Wifi className="w-5 h-5 text-success-500" />
                    </span>
                  )}
                  {connectionStatus === 'disconnected' && (
                    <span title="離線模式">
                      <WifiOff className="w-5 h-5 text-warning-500" />
                    </span>
                  )}
                  {connectionStatus === 'connecting' && (
                    <span title="連接中">
                      <Loader2 className="w-5 h-5 animate-spin text-brand-500" />
                    </span>
                  )}
                </h1>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400 flex items-center gap-2">
                  即時追蹤投票活動與參與情況
                  {realTimeData?.last_updated && (
                    <span>• 最後更新: {formatDate(new Date(realTimeData.last_updated))}</span>
                  )}
                </p>
              </div>
              
              <div className="flex flex-col sm:flex-row gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleManualRefresh}
                  disabled={loading}
                >
                  <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                  刷新
                </Button>
                <Button size="sm" className="btn-primary">
                  <FileText className="w-4 h-4 mr-2" />
                  <span className="hidden sm:inline">投票模板</span>
                  <span className="sm:hidden">模板</span>
                </Button>
                <Button size="sm" className="btn-secondary">
                  <Plus className="w-4 h-4 mr-2" />
                  <span className="hidden sm:inline">新增投票</span>
                  <span className="sm:hidden">新增</span>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* 統計卡片 */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <Card className="card">
            <CardContent className="p-4 sm:p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs sm:text-sm text-gray-600 dark:text-gray-400">今日參與數</p>
                  <p className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">
                    {stats.totalVotes}
                  </p>
                </div>
                <div className="p-2 bg-brand-50 dark:bg-brand-900/20 rounded-lg">
                  <BarChart3 className="w-5 h-5 sm:w-6 sm:h-6 text-brand-500" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="card">
            <CardContent className="p-4 sm:p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs sm:text-sm text-gray-600 dark:text-gray-400">進行中</p>
                  <p className="text-xl sm:text-2xl font-bold text-success-600 dark:text-success-400">
                    {stats.activeVotes}
                  </p>
                </div>
                <div className="p-2 bg-success-50 dark:bg-success-900/20 rounded-lg">
                  <Clock className="w-5 h-5 sm:w-6 sm:h-6 text-success-500" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="card">
            <CardContent className="p-4 sm:p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs sm:text-sm text-gray-600 dark:text-gray-400">今日完成</p>
                  <p className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">
                    {realTimeData?.today_statistics.votes_completed || 0}
                  </p>
                </div>
                <div className="p-2 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <Vote className="w-5 h-5 sm:w-6 sm:h-6 text-gray-500" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="card">
            <CardContent className="p-4 sm:p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs sm:text-sm text-gray-600 dark:text-gray-400">平均參與</p>
                  <p className="text-xl sm:text-2xl font-bold text-brand-600 dark:text-brand-400">
                    {stats.averageParticipation}
                  </p>
                </div>
                <div className="p-2 bg-brand-50 dark:bg-brand-900/20 rounded-lg">
                  <Users className="w-5 h-5 sm:w-6 sm:h-6 text-brand-500" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 標籤頁 */}
        <Tabs defaultValue="active" className="space-y-4">
          <div className="overflow-x-auto">
            <TabsList className="grid w-full grid-cols-3 min-w-max">
              <TabsTrigger value="active" className="flex items-center gap-2 whitespace-nowrap">
                <Clock className="w-4 h-4" />
                <span>進行中投票</span>
                {(realTimeData?.active_votes?.length ?? 0) > 0 && (
                  <Badge variant="success" className="ml-1">
                    {realTimeData?.active_votes?.length}
                  </Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="completed" className="flex items-center gap-2 whitespace-nowrap">
                <Vote className="w-4 h-4" />
                <span>最近完成</span>
              </TabsTrigger>
              <TabsTrigger value="all" className="flex items-center gap-2 whitespace-nowrap">
                <BarChart3 className="w-4 h-4" />
                <span>全部投票</span>
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="active" className="space-y-6">
            <Card className="card">
              <CardHeader className="card-header">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <Clock className="w-5 h-5 text-success-500" />
                  進行中的投票
                  {connectionStatus === 'connected' && (
                    <Badge variant="success" className="text-xs">即時更新</Badge>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="card-body">
                <div className="space-y-4">
                  {realTimeData?.active_votes.map((vote) => (
                    <div
                      key={vote.id}
                      className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <h3 className="text-base sm:text-lg font-semibold text-gray-900 dark:text-gray-100">
                            #{vote.id} - {vote.title}
                          </h3>
                          <div className="flex flex-wrap items-center gap-2 mt-2">
                            <Badge variant="success">進行中</Badge>
                            <Badge variant="outline">
                              {vote.is_multiple ? '多選' : '單選'}
                            </Badge>
                            {vote.is_anonymous && (
                              <Badge variant="outline" className="flex items-center gap-1">
                                <EyeOff className="w-3 h-3" />
                                匿名
                              </Badge>
                            )}
                            <span className="text-xs text-gray-500">
                              剩餘時間: {calculateTimeLeft(vote.end_time)}
                            </span>
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-4 flex-shrink-0">
                          <div className="text-center">
                            <div className="text-xl sm:text-2xl font-bold text-success-600 dark:text-success-400">
                              {vote.total_participants}
                            </div>
                            <div className="text-xs text-gray-500">參與者</div>
                          </div>
                          <Button size="sm" variant="outline">
                            <Eye className="w-4 h-4 mr-1" />
                            詳情
                          </Button>
                        </div>
                      </div>
                      
                      {/* 實時結果條形圖 */}
                      <div className="mt-4 space-y-2">
                        {calculatePercentages(vote.options).slice(0, 5).map((option) => (
                          <div key={option.option_id} className="flex items-center gap-3">
                            <div className="w-20 sm:w-24 text-xs sm:text-sm text-gray-600 dark:text-gray-400 truncate">
                              {option.text}
                            </div>
                            <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                              <div
                                className="h-2 bg-success-500 rounded-full transition-all duration-500"
                                style={{ width: `${option.percentage}%` }}
                              />
                            </div>
                            <div className="w-12 text-xs sm:text-sm text-right text-gray-600 dark:text-gray-400">
                              {option.votes}票
                            </div>
                            <div className="w-12 text-xs sm:text-sm text-right text-gray-600 dark:text-gray-400">
                              {option.percentage}%
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                  
                  {(!realTimeData?.active_votes || realTimeData.active_votes.length === 0) && (
                    <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                      <Clock className="w-12 h-12 mx-auto mb-4 opacity-50" />
                      <p>目前沒有進行中的投票</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="completed" className="space-y-6">
            <Card className="card">
              <CardHeader className="card-header">
                <CardTitle className="text-lg font-semibold">最近完成的投票</CardTitle>
              </CardHeader>
              <CardContent className="card-body">
                <div className="space-y-4">
                  {realTimeData?.recent_completed.map((vote) => (
                    <div
                      key={vote.id}
                      className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <h3 className="text-base sm:text-lg font-semibold text-gray-900 dark:text-gray-100">
                            #{vote.id} - {vote.title}
                          </h3>
                          <div className="flex flex-wrap items-center gap-2 mt-2">
                            <Badge variant="secondary">已結束</Badge>
                            <Badge variant="outline">
                              {vote.is_multiple ? '多選' : '單選'}
                            </Badge>
                            {vote.is_anonymous && (
                              <Badge variant="outline" className="flex items-center gap-1">
                                <EyeOff className="w-3 h-3" />
                                匿名
                              </Badge>
                            )}
                            <span className="text-xs text-gray-500">
                              結束於: {formatDate(new Date(vote.end_time))}
                            </span>
                          </div>
                        </div>
                        
                        <div className="text-center">
                          <div className="text-xl sm:text-2xl font-bold text-gray-600 dark:text-gray-400">
                            {vote.total_participants}
                          </div>
                          <div className="text-xs text-gray-500">參與者</div>
                        </div>
                      </div>
                      
                      {/* 最終結果 */}
                      <div className="mt-4 space-y-2">
                        {calculatePercentages(vote.options).map((option) => (
                          <div key={option.option_id} className="flex items-center gap-3">
                            <div className="w-20 sm:w-24 text-xs sm:text-sm text-gray-600 dark:text-gray-400 truncate">
                              {option.text}
                            </div>
                            <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                              <div
                                className="h-2 bg-gray-500 rounded-full"
                                style={{ width: `${option.percentage}%` }}
                              />
                            </div>
                            <div className="w-12 text-xs sm:text-sm text-right text-gray-600 dark:text-gray-400">
                              {option.votes}票
                            </div>
                            <div className="w-12 text-xs sm:text-sm text-right text-gray-600 dark:text-gray-400">
                              {option.percentage}%
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                  
                  {(!realTimeData?.recent_completed || realTimeData.recent_completed.length === 0) && (
                    <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                      <Vote className="w-12 h-12 mx-auto mb-4 opacity-50" />
                      <p>沒有最近完成的投票</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="all" className="space-y-6">
            <Card className="card">
              <CardHeader className="card-header">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                  <CardTitle className="text-lg font-semibold">所有投票</CardTitle>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder="搜尋投票..."
                      className="form-input pl-10 w-full sm:w-64"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                  </div>
                </div>
              </CardHeader>
              <CardContent className="card-body">
                <div className="space-y-4">
                  {filteredVotes.map((vote) => {
                    const isActive = new Date(vote.end_time) > new Date()
                    return (
                      <div
                        key={vote.id}
                        className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
                      >
                        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                          <div className="flex-1 min-w-0">
                            <h3 className="text-base sm:text-lg font-semibold text-gray-900 dark:text-gray-100">
                              #{vote.id} - {vote.title}
                            </h3>
                            <div className="flex flex-wrap items-center gap-2 mt-2">
                              <Badge variant={isActive ? 'success' : 'secondary'}>
                                {isActive ? '進行中' : '已結束'}
                              </Badge>
                              <Badge variant="outline">
                                {vote.is_multiple ? '多選' : '單選'}
                              </Badge>
                              {vote.is_anonymous && (
                                <Badge variant="outline" className="flex items-center gap-1">
                                  <EyeOff className="w-3 h-3" />
                                  匿名
                                </Badge>
                              )}
                            </div>
                          </div>
                          
                          <div className="flex items-center gap-4 flex-shrink-0">
                            <div className="text-center">
                              <div className="text-xl sm:text-2xl font-bold text-brand-600 dark:text-brand-400">
                                {vote.total_participants}
                              </div>
                              <div className="text-xs text-gray-500">參與者</div>
                            </div>
                            <Button size="sm" variant="outline">
                              <Eye className="w-4 h-4 mr-1" />
                              詳情
                            </Button>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                  
                  {filteredVotes.length === 0 && (
                    <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                      <Vote className="w-12 h-12 mx-auto mb-4 opacity-50" />
                      <p>沒有找到符合條件的投票</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}