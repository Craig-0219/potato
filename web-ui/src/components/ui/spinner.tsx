import { cn } from '@/lib/utils'

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export function Spinner({ size = 'md', className }: SpinnerProps) {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6',
    lg: 'h-8 w-8',
  }

  return (
    <div
      className={cn(
        'loading-spinner',
        sizeClasses[size],
        className
      )}
      role="status"
      aria-label="載入中"
    >
      <span className="sr-only">載入中...</span>
    </div>
  )
}
