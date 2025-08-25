'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useAuth } from '@/lib/auth/auth-context'
import { useTheme } from 'next-themes'
import { BotConnectionIndicator } from '@/components/bot/bot-connection-status'

export function Navbar() {
  const { isAuthenticated, user, logout, isLoading } = useAuth()
  const { theme, setTheme } = useTheme()
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [isMounted, setIsMounted] = useState(false)

  // 確保組件已掛載，避免水化錯誤
  useEffect(() => {
    setIsMounted(true)
  }, [])

  // 未掛載時不渲染，避免水化錯誤
  if (!isMounted) {
    return (
      <nav className="bg-white dark:bg-gray-800 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center space-x-2">
              <span className="text-2xl">🥔</span>
              <span className="text-xl font-bold text-gray-900 dark:text-white">Potato Bot</span>
            </div>
            <div className="text-sm text-gray-500">載入中...</div>
          </div>
        </div>
      </nav>
    )
  }

  // 如果正在載入，顯示簡單的載入狀態
  if (isLoading) {
    return (
      <nav className="bg-white dark:bg-gray-800 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center space-x-2">
              <span className="text-2xl">🥔</span>
              <span className="text-xl font-bold text-gray-900 dark:text-white">Potato Bot</span>
            </div>
            <div className="text-sm text-gray-500">載入中...</div>
          </div>
        </div>
      </nav>
    )
  }
  
  // 未認證時顯示簡單的導航欄（避免佈局跳躍）
  if (!isAuthenticated) {
    return (
      <nav className="bg-white dark:bg-gray-800 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center space-x-2">
              <span className="text-2xl">🥔</span>
              <span className="text-xl font-bold text-gray-900 dark:text-white">
                Potato Bot
              </span>
            </div>
          </div>
        </div>
      </nav>
    )
  }

  const navigation = [
    { name: '儀表板', href: '/dashboard', icon: '📊' },
    { name: '票券管理', href: '/tickets', icon: '🎫' },
    { name: '投票統計', href: '/votes', icon: '🗳️' },
    { name: 'Bot 管理', href: '/bot-management', icon: '🤖' },
    { name: '分析報告', href: '/analytics', icon: '📈' },
    { name: 'API 管理', href: '/api-management', icon: '🔧' },
    { name: '系統監控', href: '/system-monitor', icon: '🖥️' },
  ]

  return (
    <nav className="bg-white dark:bg-gray-800 shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 min-w-0">
          {/* 左側：Logo */}
          <div className="flex-shrink-0 flex items-center">
            <Link href="/dashboard" className="flex items-center space-x-2">
              <span className="text-2xl">🥔</span>
              <span className="hidden sm:block text-xl font-bold text-gray-900 dark:text-white">
                Potato Bot
              </span>
            </Link>
          </div>

          {/* 中間：桌面導航 */}
          <div className="hidden lg:flex flex-1 justify-center mx-1 min-w-0">
            <div className="flex space-x-0.5 lg:space-x-1 max-w-xl lg:max-w-2xl xl:max-w-4xl overflow-hidden">
              {/* 優先顯示前6個重要導航，系統監控最後顯示 */}
              {navigation.slice(0, 6).map((item) => (
                <Link
                  key={item.name}
                  href={item.href}
                  className="inline-flex items-center px-1.5 lg:px-2 xl:px-3 py-2 text-xs lg:text-sm font-medium text-gray-500 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white transition-colors rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 flex-shrink-0"
                  title={item.name}
                >
                  <span className="text-sm lg:text-base">{item.icon}</span>
                  <span className="hidden xl:inline ml-1 lg:ml-2">{item.name}</span>
                </Link>
              ))}
              {/* 最後一個導航項目（系統監控）在空間不足時隱藏 */}
              {navigation.slice(6).map((item) => (
                <Link
                  key={item.name}
                  href={item.href}
                  className="hidden xl:inline-flex items-center px-2 xl:px-3 py-2 text-sm font-medium text-gray-500 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white transition-colors rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 flex-shrink-0"
                  title={item.name}
                >
                  <span className="text-base">{item.icon}</span>
                  <span className="ml-2">{item.name}</span>
                </Link>
              ))}
            </div>
          </div>

          {/* 右側控制 */}
          <div className="flex items-center space-x-3 flex-shrink-0">
            {/* Bot 连接状态 - 只在大螢幕顯示 */}
            <div className="hidden 2xl:flex flex-shrink-0 w-24">
              <BotConnectionIndicator />
            </div>

            {/* 主題切換 */}
            <button
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              className="p-2 rounded-md text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white flex-shrink-0 hover:bg-gray-100 dark:hover:bg-gray-800"
              title="切換主題"
            >
              {theme === 'dark' ? '🌞' : '🌙'}
            </button>

            {/* 用戶菜單 */}
            <div className="relative flex-shrink-0">
              <button
                onClick={() => setIsMenuOpen(!isMenuOpen)}
                className="flex items-center space-x-2 text-sm rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-500"
                title={`用戶選單 - ${user?.name || 'User'}`}
              >
                <div className="w-8 h-8 bg-brand-500 rounded-full flex items-center justify-center">
                  <span className="text-white font-semibold">
                    {user?.name?.charAt(0) || 'U'}
                  </span>
                </div>
                <span className="hidden md:block text-gray-900 dark:text-white">
                  {user?.name || 'User'}
                </span>
              </button>

              {/* 下拉菜單 */}
              {isMenuOpen && (
                <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg py-1 z-50">
                  <div className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                    {user?.isOwner || user?.role === 'owner' ? '🏛️ 伺服器擁有者' : '已登入用戶'}
                  </div>
                  <Link
                    href="/profile"
                    className="block px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    個人設定
                  </Link>
                  <Link
                    href="/settings"
                    className="block px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    系統設定
                  </Link>
                  <button
                    onClick={() => {
                      setIsMenuOpen(false)
                      logout()
                    }}
                    className="block w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    登出
                  </button>
                </div>
              )}
            </div>

            {/* 菜單按鈕 - 在非LG螢幕顯示 */}
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="lg:hidden p-2 rounded-md text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white flex-shrink-0 hover:bg-gray-100 dark:hover:bg-gray-800"
              title="選單"
            >
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>
        </div>

        {/* 折疊菜單導航 */}
        {isMenuOpen && (
          <div className="lg:hidden border-t border-gray-200 dark:border-gray-700">
            <div className="pt-2 pb-3 space-y-1">
              {/* 確保所有導航項目都在折疊菜單中顯示 */}
              {navigation.map((item) => (
                <Link
                  key={item.name}
                  href={item.href}
                  className="flex items-center px-4 py-3 text-base font-medium text-gray-500 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                  onClick={() => setIsMenuOpen(false)}
                >
                  <span className="mr-3 text-lg">{item.icon}</span>
                  <span>{item.name}</span>
                </Link>
              ))}
              
              {/* 折疊菜單中顯示 Bot 連線狀態 */}
              <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50">
                <div className="text-sm text-gray-600 dark:text-gray-400 mb-2 font-medium">Bot 連線狀態</div>
                <BotConnectionIndicator />
              </div>
            </div>
          </div>
        )}
      </div>
    </nav>
  )
}