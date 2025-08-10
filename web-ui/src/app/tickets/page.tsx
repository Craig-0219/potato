'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@/lib/auth/auth-context'
import { TicketsAPI, Ticket, TicketListResponse } from '@/lib/api/tickets'
import { Spinner } from '@/components/ui/spinner'
import toast from 'react-hot-toast'

interface Ticket {
  id: number
  type: string
  status: string
  priority: string
  title?: string
  description?: string
  username: string
  created_at: string
  updated_at?: string
  assigned_to_username?: string
  rating?: number
  tags: string[]
}

interface TicketsData {
  tickets: Ticket[]
  pagination: {
    page: number
    page_size: number
    total: number
    total_pages: number
    has_next: boolean
    has_prev: boolean
  }
}

export default function TicketsPage() {
  const { isAuthenticated } = useAuth()
  const [data, setData] = useState<TicketsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [priorityFilter, setPriorityFilter] = useState<string>('')

  const fetchTickets = async (page: number = 1) => {
    try {
      setLoading(true)
      setError(null)

      const params: any = {
        page,
        page_size: 20
      }

      if (statusFilter) params.status = statusFilter
      if (priorityFilter) params.priority = priorityFilter

      const response = await ApiClient.tickets.list(params)
      setData(response.data)

    } catch (err: any) {
      console.error('獲取票券列表錯誤:', err)
      setError('無法載入票券列表，請重試')
      toast.error('載入票券失敗')
    } finally {
      setLoading(false)
    }
  }

  const handleStatusChange = async (ticketId: number, newStatus: string) => {
    try {
      await ApiClient.tickets.update(ticketId, { status: newStatus })
      toast.success('票券狀態已更新')
      fetchTickets(currentPage)
    } catch (err) {
      toast.error('更新票券狀態失敗')
    }
  }

  const handlePriorityChange = async (ticketId: number, newPriority: string) => {
    try {
      await ApiClient.tickets.update(ticketId, { priority: newPriority })
      toast.success('票券優先級已更新')
      fetchTickets(currentPage)
    } catch (err) {
      toast.error('更新票券優先級失敗')
    }
  }

  const getStatusBadge = (status: string) => {
    const statusConfig = {
      'open': { bg: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300', text: '開放中' },
      'in_progress': { bg: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300', text: '處理中' },
      'closed': { bg: 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300', text: '已關閉' },
      'resolved': { bg: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300', text: '已解決' }
    }

    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.open
    return (
      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${config.bg}`}>
        {config.text}
      </span>
    )
  }

  const getPriorityBadge = (priority: string) => {
    const priorityConfig = {
      'high': { bg: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300', text: '高', icon: '🔴' },
      'medium': { bg: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300', text: '中', icon: '🟡' },
      'low': { bg: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300', text: '低', icon: '🟢' }
    }

    const config = priorityConfig[priority as keyof typeof priorityConfig] || priorityConfig.medium
    return (
      <span className={`inline-flex items-center px-2 py-1 text-xs font-semibold rounded-full ${config.bg}`}>
        <span className="mr-1">{config.icon}</span>
        {config.text}
      </span>
    )
  }

  useEffect(() => {
    if (isAuthenticated) {
      fetchTickets()
    }
  }, [isAuthenticated, statusFilter, priorityFilter])

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            請先登入
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            您需要登入才能查看票券列表
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
            🎫 票券管理
          </h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            查看和管理所有支援票券
          </p>
        </div>

        {/* 篩選器 */}
        <div className="card p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            <div>
              <label className="form-label">狀態篩選</label>
              <select 
                value={statusFilter} 
                onChange={(e) => setStatusFilter(e.target.value)}
                className="form-input"
              >
                <option value="">所有狀態</option>
                <option value="open">開放中</option>
                <option value="in_progress">處理中</option>
                <option value="resolved">已解決</option>
                <option value="closed">已關閉</option>
              </select>
            </div>
            
            <div>
              <label className="form-label">優先級篩選</label>
              <select 
                value={priorityFilter} 
                onChange={(e) => setPriorityFilter(e.target.value)}
                className="form-input"
              >
                <option value="">所有優先級</option>
                <option value="high">高優先級</option>
                <option value="medium">中優先級</option>
                <option value="low">低優先級</option>
              </select>
            </div>

            <div>
              <button
                onClick={() => {
                  setStatusFilter('')
                  setPriorityFilter('')
                }}
                className="btn-secondary w-full"
              >
                清除篩選
              </button>
            </div>

            <div>
              <button
                onClick={() => fetchTickets(currentPage)}
                className="btn-primary w-full"
              >
                🔄 刷新
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
            <button onClick={() => fetchTickets(currentPage)} className="btn-primary">
              重新載入
            </button>
          </div>
        )}

        {/* 票券列表 */}
        {data && !loading && (
          <>
            <div className="space-y-4">
              {data.tickets.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-gray-500 dark:text-gray-400">沒有找到票券</p>
                </div>
              ) : (
                data.tickets.map((ticket) => (
                  <div key={ticket.id} className="card p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-2">
                          <span className="font-semibold text-lg text-gray-900 dark:text-white">
                            #{ticket.id}
                          </span>
                          {getStatusBadge(ticket.status)}
                          {getPriorityBadge(ticket.priority)}
                        </div>
                        
                        {ticket.title && (
                          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                            {ticket.title}
                          </h3>
                        )}
                        
                        {ticket.description && (
                          <p className="text-gray-600 dark:text-gray-400 mb-3">
                            {ticket.description.substring(0, 150)}
                            {ticket.description.length > 150 && '...'}
                          </p>
                        )}
                        
                        <div className="flex flex-wrap items-center text-sm text-gray-500 dark:text-gray-400 space-x-4">
                          <span>👤 {ticket.username}</span>
                          <span>📅 {new Date(ticket.created_at).toLocaleString('zh-TW')}</span>
                          {ticket.assigned_to_username && (
                            <span>👨‍💼 指派給: {ticket.assigned_to_username}</span>
                          )}
                          {ticket.rating && (
                            <span>⭐ 評分: {ticket.rating}/5</span>
                          )}
                        </div>

                        {/* 標籤 */}
                        {ticket.tags && ticket.tags.length > 0 && (
                          <div className="flex flex-wrap gap-2 mt-2">
                            {ticket.tags.map((tag, index) => (
                              <span
                                key={index}
                                className="inline-flex px-2 py-1 text-xs bg-gray-100 text-gray-800 rounded-full dark:bg-gray-800 dark:text-gray-300"
                              >
                                🏷️ {tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* 操作按鈕 */}
                      <div className="flex space-x-2 ml-4">
                        {ticket.status === 'open' && (
                          <button
                            onClick={() => handleStatusChange(ticket.id, 'in_progress')}
                            className="btn-secondary text-xs px-3 py-1"
                          >
                            開始處理
                          </button>
                        )}
                        {ticket.status === 'in_progress' && (
                          <button
                            onClick={() => handleStatusChange(ticket.id, 'resolved')}
                            className="btn-primary text-xs px-3 py-1"
                          >
                            標記解決
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* 分頁 */}
            {data.pagination.total_pages > 1 && (
              <div className="flex justify-between items-center mt-8">
                <div className="text-sm text-gray-700 dark:text-gray-300">
                  顯示 {((currentPage - 1) * data.pagination.page_size) + 1} 到{' '}
                  {Math.min(currentPage * data.pagination.page_size, data.pagination.total)} 項，
                  共 {data.pagination.total} 項
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => {
                      setCurrentPage(currentPage - 1)
                      fetchTickets(currentPage - 1)
                    }}
                    disabled={!data.pagination.has_prev}
                    className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    上一頁
                  </button>
                  <button
                    onClick={() => {
                      setCurrentPage(currentPage + 1)
                      fetchTickets(currentPage + 1)
                    }}
                    disabled={!data.pagination.has_next}
                    className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    下一頁
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}