'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function HomePage() {
  const router = useRouter()

  useEffect(() => {
    // 直接重定向到儀表板
    router.push('/dashboard')
  }, [router])

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="loading-spinner h-8 w-8" role="status" aria-label="載入中">
        <span className="sr-only">載入中...</span>
      </div>
      <p className="ml-4 text-gray-600">正在重定向到儀表板...</p>
    </div>
  )
}