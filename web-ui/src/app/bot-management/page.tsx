'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@/lib/auth/auth-context'
import { Spinner } from '@/components/ui/spinner'
import toast from 'react-hot-toast'

interface BotSettings {
  ticket_settings: {
    auto_assign: boolean
    max_tickets_per_user: number
    staff_notifications: boolean
  }
  welcome_settings: {
    enabled: boolean
    welcome_channel: string
    welcome_message: string
    auto_role: string
  }
  vote_settings: {
    default_duration: number
    allow_anonymous: boolean
    auto_close: boolean
  }
}

export default function BotManagementPage() {
  const { isAuthenticated, hasPermission } = useAuth()
  const [isLoading, setIsLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('tickets')
  const [settings, setSettings] = useState<BotSettings | null>(null)

  useEffect(() => {
    if (isAuthenticated) {
      loadBotSettings()
    }
  }, [isAuthenticated])

  const loadBotSettings = async () => {
    try {
      setIsLoading(true)
      // 這裡將調用 Bot API 獲取設定
      const response = await fetch('/api/v1/system/bot-settings')
      if (response.ok) {
        const data = await response.json()
        setSettings(data)
      }
    } catch (error) {
      console.error('載入 Bot 設定失敗:', error)
      toast.error('載入 Bot 設定失敗')
    } finally {
      setIsLoading(false)
    }
  }

  const saveBotSettings = async (section: string, newSettings: any) => {
    try {
      const response = await fetch(`/api/v1/system/bot-settings/${section}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSettings)
      })
      
      if (response.ok) {
        toast.success('設定已保存')
        loadBotSettings() // 重新載入設定
      } else {
        throw new Error('保存失敗')
      }
    } catch (error) {
      console.error('保存 Bot 設定失敗:', error)
      toast.error('保存設定失敗')
    }
  }

  if (!isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">請先登入</h1>
          <p>您需要登入才能訪問 Bot 管理功能</p>
        </div>
      </div>
    )
  }

  if (!hasPermission('管理員')) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">權限不足</h1>
          <p>您需要管理員權限才能訪問此頁面</p>
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Spinner size="lg" />
      </div>
    )
  }

  const tabs = [
    { id: 'tickets', name: '票券系統', icon: '🎫' },
    { id: 'votes', name: '投票系統', icon: '🗳️' },
    { id: 'welcome', name: '歡迎系統', icon: '👋' },
    { id: 'workflows', name: '工作流程', icon: '⚙️' },
    { id: 'webhooks', name: 'Webhooks', icon: '🔗' }
  ]

  const renderTabContent = () => {
    switch (activeTab) {
      case 'tickets':
        return <TicketSettingsTab settings={settings?.ticket_settings} onSave={(data) => saveBotSettings('tickets', data)} />
      case 'votes':
        return <VoteSettingsTab settings={settings?.vote_settings} onSave={(data) => saveBotSettings('votes', data)} />
      case 'welcome':
        return <WelcomeSettingsTab settings={settings?.welcome_settings} onSave={(data) => saveBotSettings('welcome', data)} />
      case 'workflows':
        return <WorkflowsTab />
      case 'webhooks':
        return <WebhooksTab />
      default:
        return <div>選擇一個標籤</div>
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {/* 頁面標題 */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            🤖 Discord Bot 管理 <span className="text-lg text-brand-600 dark:text-brand-400">v2.3.0</span>
          </h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            統一管理 Discord Bot 的各項功能設定 - 企業級 Web 管理界面
          </p>
        </div>

        {/* 標籤導航 */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm mb-6">
          <div className="border-b border-gray-200 dark:border-gray-700">
            <nav className="flex space-x-8 px-6" aria-label="Tabs">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`py-4 px-1 border-b-2 font-medium text-sm ${
                    activeTab === tab.id
                      ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                  }`}
                >
                  <span className="mr-2">{tab.icon}</span>
                  {tab.name}
                </button>
              ))}
            </nav>
          </div>
        </div>

        {/* 標籤內容 */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6">
          {renderTabContent()}
        </div>
      </div>
    </div>
  )
}

// 票券設定標籤
function TicketSettingsTab({ settings, onSave }: { settings: any, onSave: (data: any) => void }) {
  const [formData, setFormData] = useState(settings || {
    auto_assign: false,
    max_tickets_per_user: 3,
    staff_notifications: true
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSave(formData)
  }

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">🎫 票券系統設定</h2>
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="form-label">
              自動分配票券
            </label>
            <div className="mt-2">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={formData.auto_assign}
                  onChange={(e) => setFormData({ ...formData, auto_assign: e.target.checked })}
                  className="rounded border-gray-300 text-brand-600 focus:ring-brand-500"
                />
                <span className="ml-2 text-sm text-gray-600 dark:text-gray-400">
                  啟用自動分配給可用的客服人員
                </span>
              </label>
            </div>
          </div>

          <div>
            <label className="form-label">
              每位用戶最大票券數
            </label>
            <input
              type="number"
              min="1"
              max="10"
              value={formData.max_tickets_per_user}
              onChange={(e) => setFormData({ ...formData, max_tickets_per_user: parseInt(e.target.value) })}
              className="form-input"
            />
          </div>

          <div>
            <label className="form-label">
              客服通知
            </label>
            <div className="mt-2">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={formData.staff_notifications}
                  onChange={(e) => setFormData({ ...formData, staff_notifications: e.target.checked })}
                  className="rounded border-gray-300 text-brand-600 focus:ring-brand-500"
                />
                <span className="ml-2 text-sm text-gray-600 dark:text-gray-400">
                  新票券時通知客服人員
                </span>
              </label>
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <button type="submit" className="btn-primary">
            保存設定
          </button>
        </div>
      </form>
    </div>
  )
}

// 投票設定標籤
function VoteSettingsTab({ settings, onSave }: { settings: any, onSave: (data: any) => void }) {
  const [formData, setFormData] = useState(settings || {
    default_duration: 24,
    allow_anonymous: false,
    auto_close: true
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSave(formData)
  }

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">🗳️ 投票系統設定</h2>
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="form-label">
              預設投票時長 (小時)
            </label>
            <input
              type="number"
              min="1"
              max="168"
              value={formData.default_duration}
              onChange={(e) => setFormData({ ...formData, default_duration: parseInt(e.target.value) })}
              className="form-input"
            />
          </div>

          <div>
            <label className="form-label">
              匿名投票
            </label>
            <div className="mt-2">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={formData.allow_anonymous}
                  onChange={(e) => setFormData({ ...formData, allow_anonymous: e.target.checked })}
                  className="rounded border-gray-300 text-brand-600 focus:ring-brand-500"
                />
                <span className="ml-2 text-sm text-gray-600 dark:text-gray-400">
                  允許匿名投票
                </span>
              </label>
            </div>
          </div>

          <div>
            <label className="form-label">
              自動關閉
            </label>
            <div className="mt-2">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={formData.auto_close}
                  onChange={(e) => setFormData({ ...formData, auto_close: e.target.checked })}
                  className="rounded border-gray-300 text-brand-600 focus:ring-brand-500"
                />
                <span className="ml-2 text-sm text-gray-600 dark:text-gray-400">
                  投票結束後自動關閉
                </span>
              </label>
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <button type="submit" className="btn-primary">
            保存設定
          </button>
        </div>
      </form>
    </div>
  )
}

// 歡迎系統標籤
function WelcomeSettingsTab({ settings, onSave }: { settings: any, onSave: (data: any) => void }) {
  const [formData, setFormData] = useState(settings || {
    enabled: false,
    welcome_channel: '',
    welcome_message: '歡迎 {user} 加入我們的社群！',
    auto_role: ''
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSave(formData)
  }

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">👋 歡迎系統設定</h2>
      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="form-label">
            啟用歡迎系統
          </label>
          <div className="mt-2">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={formData.enabled}
                onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                className="rounded border-gray-300 text-brand-600 focus:ring-brand-500"
              />
              <span className="ml-2 text-sm text-gray-600 dark:text-gray-400">
                新成員加入時自動發送歡迎訊息
              </span>
            </label>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="form-label">
              歡迎頻道 ID
            </label>
            <input
              type="text"
              value={formData.welcome_channel}
              onChange={(e) => setFormData({ ...formData, welcome_channel: e.target.value })}
              placeholder="頻道 ID"
              className="form-input"
            />
          </div>

          <div>
            <label className="form-label">
              自動角色 ID
            </label>
            <input
              type="text"
              value={formData.auto_role}
              onChange={(e) => setFormData({ ...formData, auto_role: e.target.value })}
              placeholder="角色 ID (可選)"
              className="form-input"
            />
          </div>
        </div>

        <div>
          <label className="form-label">
            歡迎訊息
          </label>
          <textarea
            value={formData.welcome_message}
            onChange={(e) => setFormData({ ...formData, welcome_message: e.target.value })}
            rows={3}
            placeholder="使用 {user} 代表新成員"
            className="form-input"
          />
          <p className="mt-1 text-sm text-gray-500">
            可用變數：{'{user}'} - 新成員提及, {'{username}'} - 成員名稱, {'{server}'} - 伺服器名稱
          </p>
        </div>

        <div className="flex justify-end">
          <button type="submit" className="btn-primary">
            保存設定
          </button>
        </div>
      </form>
    </div>
  )
}

// 工作流程標籤
function WorkflowsTab() {
  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">⚙️ 工作流程管理</h2>
      <div className="text-center py-12">
        <p className="text-gray-500 dark:text-gray-400">工作流程管理功能開發中...</p>
        <p className="text-sm text-gray-400 mt-2">即將支援自動化規則配置</p>
      </div>
    </div>
  )
}

// Webhooks 標籤  
function WebhooksTab() {
  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">🔗 Webhook 整合</h2>
      <div className="text-center py-12">
        <p className="text-gray-500 dark:text-gray-400">Webhook 整合功能開發中...</p>
        <p className="text-sm text-gray-400 mt-2">即將支援外部服務整合</p>
      </div>
    </div>
  )
}