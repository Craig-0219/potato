'use client'

import React, { createContext, useContext, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Cookies from 'js-cookie'
import toast from 'react-hot-toast'
import { apiClient } from '@/lib/api/client'

interface User {
  id: string
  username: string
  email?: string
  permission_level: 'read_only' | 'write' | 'admin' | 'super_admin'
  guild_id?: number
  avatar?: string
}

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (apiKey: string) => Promise<void>
  logout: () => void
  hasPermission: (requiredLevel: string) => boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

const PERMISSION_LEVELS = {
  read_only: 0,
  write: 1,
  admin: 2,
  super_admin: 3,
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  const isAuthenticated = !!user

  // 檢查權限等級
  const hasPermission = (requiredLevel: string): boolean => {
    if (!user) return false
    
    const userLevel = PERMISSION_LEVELS[user.permission_level] || 0
    const required = PERMISSION_LEVELS[requiredLevel as keyof typeof PERMISSION_LEVELS] || 999
    
    return userLevel >= required
  }

  // 登入函數
  const login = async (apiKey: string) => {
    try {
      setIsLoading(true)
      
      // 設置 API 金鑰到 cookies
      Cookies.set('api_key', apiKey, { 
        expires: 7, // 7 天
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'strict'
      })

      // 更新 API 客戶端的認證頭
      apiClient.defaults.headers.common['Authorization'] = `Bearer ${apiKey}`

      // 驗證 API 金鑰並獲取用戶信息
      const response = await apiClient.get('/system/info')
      
      // 模擬用戶數據（實際應該從 API 獲取）
      const userData: User = {
        id: 'api_user',
        username: 'API User',
        permission_level: 'admin', // 這應該從 API 響應中獲取
        avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=32&h=32&fit=crop&crop=face&auto=format'
      }

      setUser(userData)
      toast.success('登入成功！歡迎使用 Potato Bot Dashboard')
      
    } catch (error: any) {
      console.error('登入失敗:', error)
      
      // 清除無效的 API 金鑰
      Cookies.remove('api_key')
      delete apiClient.defaults.headers.common['Authorization']
      
      const errorMessage = error.response?.data?.error?.message || '登入失敗，請檢查您的 API 金鑰'
      toast.error(errorMessage)
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  // 登出函數
  const logout = () => {
    setUser(null)
    Cookies.remove('api_key')
    delete apiClient.defaults.headers.common['Authorization']
    toast.success('已成功登出')
    router.push('/')
  }

  // 初始化認證狀態
  useEffect(() => {
    const initAuth = async () => {
      const apiKey = Cookies.get('api_key')
      
      if (!apiKey) {
        setIsLoading(false)
        return
      }

      try {
        // 設置 API 客戶端認證頭
        apiClient.defaults.headers.common['Authorization'] = `Bearer ${apiKey}`
        
        // 驗證現有 token
        const response = await apiClient.get('/system/health')
        
        if (response.data.status === 'healthy') {
          // Token 有效，設置用戶數據
          const userData: User = {
            id: 'api_user',
            username: 'API User',
            permission_level: 'admin',
            avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=32&h=32&fit=crop&crop=face&auto=format'
          }
          setUser(userData)
        }
      } catch (error) {
        console.error('Token 驗證失敗:', error)
        // Token 無效，清除
        Cookies.remove('api_key')
        delete apiClient.defaults.headers.common['Authorization']
      } finally {
        setIsLoading(false)
      }
    }

    initAuth()
  }, [])

  const value = {
    user,
    isAuthenticated,
    isLoading,
    login,
    logout,
    hasPermission,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}