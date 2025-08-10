import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { format, formatDistanceToNow } from 'date-fns'
import { zhTW } from 'date-fns/locale'

// 合併 Tailwind CSS 類名
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// 格式化日期時間
export function formatDateTime(date: string | Date, formatStr: string = 'yyyy-MM-dd HH:mm:ss') {
  return format(new Date(date), formatStr, { locale: zhTW })
}

// 格式化相對時間（多久之前）
export function formatTimeAgo(date: string | Date) {
  return formatDistanceToNow(new Date(date), { 
    addSuffix: true, 
    locale: zhTW 
  })
}

// 格式化檔案大小
export function formatFileSize(bytes: number) {
  if (bytes === 0) return '0 Bytes'
  
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 格式化數字（添加千分位逗號）
export function formatNumber(num: number) {
  return new Intl.NumberFormat('zh-TW').format(num)
}

// 格式化百分比
export function formatPercentage(num: number, decimals: number = 1) {
  return `${(num * 100).toFixed(decimals)}%`
}

// 截斷文字
export function truncateText(text: string, maxLength: number) {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + '...'
}

// 生成隨機 ID
export function generateId(length: number = 8) {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  let result = ''
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return result
}

// 延遲函數
export function delay(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// 獲取優先級顏色
export function getPriorityColor(priority: string) {
  switch (priority.toLowerCase()) {
    case 'high':
      return 'text-error-600 bg-error-50 border-error-200 dark:text-error-400 dark:bg-error-900/20 dark:border-error-800'
    case 'medium':
      return 'text-warning-600 bg-warning-50 border-warning-200 dark:text-warning-400 dark:bg-warning-900/20 dark:border-warning-800'
    case 'low':
      return 'text-success-600 bg-success-50 border-success-200 dark:text-success-400 dark:bg-success-900/20 dark:border-success-800'
    default:
      return 'text-gray-600 bg-gray-50 border-gray-200 dark:text-gray-400 dark:bg-gray-800 dark:border-gray-700'
  }
}

// 獲取狀態顏色
export function getStatusColor(status: string) {
  switch (status.toLowerCase()) {
    case 'open':
    case 'active':
      return 'text-success-600 bg-success-50 dark:text-success-400 dark:bg-success-900/20'
    case 'closed':
    case 'completed':
      return 'text-gray-600 bg-gray-50 dark:text-gray-400 dark:bg-gray-800'
    case 'pending':
      return 'text-warning-600 bg-warning-50 dark:text-warning-400 dark:bg-warning-900/20'
    case 'archived':
      return 'text-gray-500 bg-gray-100 dark:text-gray-500 dark:bg-gray-700'
    default:
      return 'text-gray-600 bg-gray-50 dark:text-gray-400 dark:bg-gray-800'
  }
}

// 複製到剪貼板
export async function copyToClipboard(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch (err) {
    console.error('複製失敗:', err)
    return false
  }
}

// 下載檔案
export function downloadFile(data: any, filename: string, type: string = 'application/json') {
  const blob = new Blob([typeof data === 'string' ? data : JSON.stringify(data, null, 2)], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

// 驗證 Email 格式
export function isValidEmail(email: string) {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(email)
}

// 驗證 URL 格式
export function isValidUrl(url: string) {
  try {
    new URL(url)
    return true
  } catch {
    return false
  }
}

// 深度複製對象
export function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj))
}

// 防抖函數
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout
  return (...args: Parameters<T>) => {
    clearTimeout(timeout)
    timeout = setTimeout(() => func(...args), wait)
  }
}

// 節流函數
export function throttle<T extends (...args: any[]) => any>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle: boolean
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args)
      inThrottle = true
      setTimeout(() => inThrottle = false, limit)
    }
  }
}