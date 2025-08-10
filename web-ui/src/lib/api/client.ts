import axios from 'axios'
import toast from 'react-hot-toast'

// API 基礎 URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

// 創建 axios 實例
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 秒超時
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
})

// 請求攔截器
apiClient.interceptors.request.use(
  (config) => {
    // 在開發環境顯示請求日誌
    if (process.env.NODE_ENV === 'development') {
      console.log('🚀 API Request:', {
        method: config.method?.toUpperCase(),
        url: config.url,
        data: config.data,
      })
    }
    return config
  },
  (error) => {
    console.error('❌ Request Error:', error)
    return Promise.reject(error)
  }
)

// 響應攔截器
apiClient.interceptors.response.use(
  (response) => {
    // 在開發環境顯示響應日誌
    if (process.env.NODE_ENV === 'development') {
      console.log('✅ API Response:', {
        status: response.status,
        url: response.config.url,
        data: response.data,
      })
    }
    return response
  },
  (error) => {
    console.error('❌ Response Error:', error)

    // 處理不同的錯誤狀態碼
    if (error.response) {
      const { status, data } = error.response
      
      switch (status) {
        case 401:
          toast.error('認證失敗，請重新登入')
          // 可以在這裡觸發登出邏輯
          break
        case 403:
          toast.error('權限不足，無法執行此操作')
          break
        case 404:
          toast.error('請求的資源不存在')
          break
        case 429:
          toast.error('請求過於頻繁，請稍後再試')
          break
        case 500:
          toast.error('伺服器內部錯誤，請聯繫管理員')
          break
        default:
          const errorMessage = data?.error?.message || `請求失敗 (${status})`
          toast.error(errorMessage)
      }
    } else if (error.request) {
      // 網路錯誤
      toast.error('網路連接失敗，請檢查您的網路連接')
    } else {
      // 其他錯誤
      toast.error('發生未知錯誤，請重試')
    }

    return Promise.reject(error)
  }
)

// API 響應類型
export interface ApiResponse<T = any> {
  success: boolean
  message: string
  data?: T
  timestamp: string
}

export interface PaginatedResponse<T = any> extends ApiResponse<T[]> {
  pagination: {
    page: number
    page_size: number
    total: number
    total_pages: number
    has_next: boolean
    has_prev: boolean
  }
}

export interface ErrorResponse {
  success: false
  error: {
    code: number
    message: string
    timestamp: string
    path: string
  }
}

// API 客戶端類
export class ApiClient {
  // 票券相關 API
  static tickets = {
    // 獲取票券列表
    list: (params?: {
      guild_id?: number
      status?: string
      priority?: string
      page?: number
      page_size?: number
    }) => apiClient.get<PaginatedResponse>('/tickets', { params }),

    // 獲取票券詳情
    get: (id: number) => 
      apiClient.get<ApiResponse>(`/tickets/${id}`),

    // 創建票券
    create: (data: {
      type: string
      priority: string
      title?: string
      description?: string
      guild_id: number
      discord_id: string
      username: string
    }) => apiClient.post<ApiResponse>('/tickets', data),

    // 更新票券
    update: (id: number, data: {
      status?: string
      priority?: string
      assigned_to?: number
    }) => apiClient.put<ApiResponse>(`/tickets/${id}`, data),

    // 關閉票券
    close: (id: number, reason?: string) =>
      apiClient.post<ApiResponse>(`/tickets/${id}/close`, { reason }),

    // 指派票券
    assign: (id: number, assigned_to: number) =>
      apiClient.post<ApiResponse>(`/tickets/${id}/assign`, { assigned_to }),

    // 票券評分
    rate: (id: number, rating: number, feedback?: string) =>
      apiClient.post<ApiResponse>(`/tickets/${id}/rating`, { rating, feedback }),

    // 票券統計
    statistics: (guild_id?: number, days: number = 30) =>
      apiClient.get<ApiResponse>('/tickets/statistics/overview', {
        params: { guild_id, days }
      }),
  }

  // 分析統計 API
  static analytics = {
    // 儀表板數據
    dashboard: (params?: {
      guild_id?: number
      period?: string
    }) => apiClient.get<ApiResponse>('/analytics/dashboard', { params }),

    // 生成報告
    generateReport: (params: {
      report_type: string
      format: string
      guild_id?: number
      start_date?: string
      end_date?: string
    }) => apiClient.get<ApiResponse>('/analytics/reports', { params }),

    // 客服績效
    staffPerformance: (guild_id?: number, days: number = 30) =>
      apiClient.get<ApiResponse>('/analytics/staff-performance', {
        params: { guild_id, days }
      }),
  }

  // 自動化 API
  static automation = {
    // 獲取規則列表
    getRules: (params?: {
      guild_id?: number
      status?: string
      page?: number
      page_size?: number
    }) => apiClient.get<PaginatedResponse>('/automation/rules', { params }),

    // 創建規則
    createRule: (data: any) =>
      apiClient.post<ApiResponse>('/automation/rules', data),

    // 獲取執行記錄
    getExecutions: (params?: {
      rule_id?: string
      start_date?: string
      end_date?: string
      limit?: number
    }) => apiClient.get<ApiResponse>('/automation/executions', { params }),
  }

  // 安全 API
  static security = {
    // 安全總覽
    overview: (guild_id?: number) =>
      apiClient.get<ApiResponse>('/security/overview', {
        params: { guild_id }
      }),

    // 審計日誌
    auditLog: (params?: {
      guild_id?: number
      event_type?: string
      severity?: string
      page?: number
      page_size?: number
    }) => apiClient.get<PaginatedResponse>('/security/audit-log', { params }),

    // 合規報告
    complianceReport: (standard: string, format: string = 'json') =>
      apiClient.get<ApiResponse>(`/security/compliance/${standard}`, {
        params: { format }
      }),
  }

  // 系統 API
  static system = {
    // 健康檢查
    health: () => apiClient.get<ApiResponse>('/system/health'),

    // 系統指標
    metrics: () => apiClient.get<ApiResponse>('/system/metrics'),

    // 系統信息
    info: () => apiClient.get<ApiResponse>('/system/info'),

    // API 金鑰管理
    apiKeys: {
      list: () => apiClient.get<ApiResponse>('/system/api-keys'),
      create: (data: {
        name: string
        permission_level: string
        guild_id?: number
        expires_days?: number
      }) => apiClient.post<ApiResponse>('/system/api-keys', data),
      revoke: (keyId: string) =>
        apiClient.delete<ApiResponse>(`/system/api-keys/${keyId}`),
    },
  }
}

export default ApiClient