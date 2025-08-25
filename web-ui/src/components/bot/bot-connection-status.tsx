'use client'

import React from 'react'
import { useBotConnection } from '@/lib/connection/use-bot-connection'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { 
  Wifi, 
  WifiOff, 
  AlertCircle, 
  CheckCircle, 
  RefreshCw, 
  Zap,
  Clock,
  Users,
  Server
} from 'lucide-react'

export function BotConnectionStatus() {
  const { 
    status, 
    connectionStatus, 
    isConnected, 
    isConnecting, 
    connect, 
    disconnect, 
    reconnect 
  } = useBotConnection()

  const getStatusIcon = () => {
    try {
      switch (connectionStatus) {
        case 'connected':
          return <CheckCircle className="w-5 h-5 text-green-500" />
        case 'connecting':
          return <RefreshCw className="w-5 h-5 text-blue-500 animate-spin" />
        case 'error':
          return <AlertCircle className="w-5 h-5 text-red-500" />
        default:
          return <WifiOff className="w-5 h-5 text-gray-500" />
      }
    } catch (error) {
      console.error('Error rendering status icon:', error)
      return <WifiOff className="w-5 h-5 text-gray-500" />
    }
  }

  const getStatusText = () => {
    switch (connectionStatus) {
      case 'connected':
        return '已連線'
      case 'connecting':
        return '連線中...'
      case 'error':
        return '連線錯誤'
      default:
        return '未連線'
    }
  }

  const getStatusColor = () => {
    switch (connectionStatus) {
      case 'connected':
        return 'success'
      case 'connecting':
        return 'warning'
      case 'error':
        return 'destructive'
      default:
        return 'secondary'
    }
  }

  const getConnectionQualityColor = () => {
    switch (status.connectionQuality) {
      case 'excellent':
        return 'text-green-500'
      case 'good':
        return 'text-yellow-500'
      case 'poor':
        return 'text-orange-500'
      default:
        return 'text-red-500'
    }
  }

  const getConnectionQualityText = () => {
    switch (status.connectionQuality) {
      case 'excellent':
        return '優秀'
      case 'good':
        return '良好'
      case 'poor':
        return '較差'
      case 'disconnected':
        return '已斷線'
      default:
        return '未知'
    }
  }

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    
    if (days > 0) {
      return `${days}天 ${hours}小時`
    } else if (hours > 0) {
      return `${hours}小時 ${minutes}分鐘`
    } else {
      return `${minutes}分鐘`
    }
  }

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold flex items-center gap-2">
            {getStatusIcon()}
            Bot 連線狀態
          </CardTitle>
          <Badge variant={getStatusColor() as any}>
            {getStatusText()}
          </Badge>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* 連線訊息 */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <Wifi className="w-4 h-4" />
              <span className="text-gray-600 dark:text-gray-400">連線狀態:</span>
              <span className={isConnected ? 'text-green-600' : 'text-red-600'}>
                {isConnected ? '線上' : '離線'}
              </span>
            </div>
            
            {status.latency > 0 && (
              <div className="flex items-center gap-2 text-sm">
                <Zap className="w-4 h-4" />
                <span className="text-gray-600 dark:text-gray-400">延遲:</span>
                <span className={getConnectionQualityColor()}>
                  {status.latency}ms
                </span>
              </div>
            )}
          </div>

          <div className="space-y-2">
            {status.lastHeartbeat && (
              <div className="flex items-center gap-2 text-sm">
                <Clock className="w-4 h-4" />
                <span className="text-gray-600 dark:text-gray-400">最後心跳:</span>
                <span className="text-gray-900 dark:text-gray-100">
                  {status.lastHeartbeat.toLocaleTimeString()}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Bot 訊息 */}
        {status.botInfo && (
          <div className="border-t pt-4">
            <h4 className="font-medium mb-3 flex items-center gap-2">
              <Server className="w-4 h-4" />
              Bot 訊息
            </h4>
            
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-600 dark:text-gray-400">名稱:</span>
                <span className="ml-2 font-medium">{status.botInfo.name}</span>
              </div>
              
              <div>
                <span className="text-gray-600 dark:text-gray-400">版本:</span>
                <span className="ml-2 font-medium">{status.botInfo.version}</span>
              </div>
              
              <div>
                <span className="text-gray-600 dark:text-gray-400">伺服器數:</span>
                <span className="ml-2 flex items-center gap-1">
                  <Users className="w-3 h-3" />
                  {status.botInfo.guilds}
                </span>
              </div>
              
              <div>
                <span className="text-gray-600 dark:text-gray-400">運行時間:</span>
                <span className="ml-2">{formatUptime(status.botInfo.uptime)}</span>
              </div>
            </div>
          </div>
        )}

        {/* 操作按鈕 */}
        <div className="flex gap-2 pt-4 border-t">
          {!isConnected && !isConnecting && (
            <Button 
              onClick={connect} 
              size="sm" 
              className="flex-1"
            >
              <Wifi className="w-4 h-4 mr-2" />
              連線
            </Button>
          )}
          
          {isConnected && (
            <>
              <Button 
                onClick={disconnect} 
                variant="outline" 
                size="sm"
                className="flex-1"
              >
                <WifiOff className="w-4 h-4 mr-2" />
                斷開
              </Button>
              
              <Button 
                onClick={reconnect} 
                variant="outline" 
                size="sm"
                className="flex-1"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                重連
              </Button>
            </>
          )}
          
          {connectionStatus === 'error' && (
            <Button 
              onClick={reconnect} 
              variant="destructive" 
              size="sm"
              className="flex-1"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              重試連線
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

// 精簡版連線狀態指示器
export function BotConnectionIndicator() {
  const { status, connectionStatus, isConnected } = useBotConnection()

  const getIndicatorColor = () => {
    if (isConnected) return 'bg-green-500'
    if (connectionStatus === 'connecting') return 'bg-yellow-500'
    if (connectionStatus === 'error') return 'bg-red-500'
    return 'bg-gray-500'
  }

  return (
    <div className="flex items-center gap-1 min-w-0 max-w-32">
      <div className={`w-2 h-2 rounded-full flex-shrink-0 ${getIndicatorColor()}`} />
      <span className="text-xs text-gray-600 dark:text-gray-400 truncate">
        Bot {isConnected ? '線上' : '離線'}
      </span>
      {isConnected && status.latency > 0 && (
        <span className="text-xs text-gray-500 flex-shrink-0">
          {status.latency}ms
        </span>
      )}
    </div>
  )
}