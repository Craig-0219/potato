'use client'

import React, { createContext, useContext, useEffect, ReactNode } from 'react'
import { botConnector } from '@/lib/connection/bot-connector'
import { toast } from 'react-hot-toast'

interface BotConnectionContextType {
  connector: typeof botConnector
}

const BotConnectionContext = createContext<BotConnectionContextType | null>(null)

interface BotConnectionProviderProps {
  children: ReactNode
  autoConnect?: boolean
}

export function BotConnectionProvider({ 
  children, 
  autoConnect = true 
}: BotConnectionProviderProps) {
  
  useEffect(() => {
    // 設置全域事件監聽器
    const handleConnected = () => {
      console.log('🤖 Bot 連線已建立')
    }

    const handleDisconnected = () => {
      console.log('🤖 Bot 連線已斷開')
    }

    const handleError = (error: Error) => {
      console.error('🤖 Bot 連線錯誤:', error)
    }

    const handleNotification = (notification: any) => {
      // 處理來自 Bot 的通知
      if (notification.type === 'toast') {
        switch (notification.level) {
          case 'success':
            toast.success(notification.message)
            break
          case 'error':
            toast.error(notification.message)
            break
          case 'warning':
            toast(notification.message, { icon: '⚠️' })
            break
          default:
            toast(notification.message)
            break
        }
      }
    }

    // 註冊事件監聽器
    botConnector.on('connected', handleConnected)
    botConnector.on('disconnected', handleDisconnected)
    botConnector.on('error', handleError)
    botConnector.on('notification', handleNotification)

    // 如果啟用自動連線，則開始連線流程
    if (autoConnect) {
      console.log('🚀 啟動 Bot 自動連線...')
      // 延遲一點時間確保頁面載入完成
      setTimeout(() => {
        botConnector.startAutoConnection().catch(error => {
          console.error('自動連線失敗:', error)
        })
      }, 1000)
    }

    // 頁面可見性變化時的處理
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        // 頁面變為可見時，檢查連線狀態
        if (!botConnector.isConnected()) {
          console.log('頁面恢復可見，檢查 Bot 連線狀態')
          botConnector.startAutoConnection().catch(error => {
            console.error('重新連線失敗:', error)
          })
        }
      }
    }

    // 網路狀態變化時的處理
    const handleOnline = () => {
      console.log('網路恢復，嘗試重新連線 Bot')
      botConnector.reconnect().catch(error => {
        console.error('網路恢復後重連失敗:', error)
      })
    }

    const handleOffline = () => {
      console.log('網路斷開')
      toast.error('網路連線斷開，Bot 功能可能受影響')
    }

    // 添加事件監聽器
    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    // 清理函數
    return () => {
      botConnector.off('connected', handleConnected)
      botConnector.off('disconnected', handleDisconnected)
      botConnector.off('error', handleError)
      botConnector.off('notification', handleNotification)

      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [autoConnect])

  const value: BotConnectionContextType = {
    connector: botConnector
  }

  return (
    <BotConnectionContext.Provider value={value}>
      {children}
    </BotConnectionContext.Provider>
  )
}

// Hook 來使用連線上下文
export function useBotConnectionContext() {
  const context = useContext(BotConnectionContext)
  if (!context) {
    throw new Error('useBotConnectionContext must be used within a BotConnectionProvider')
  }
  return context
}