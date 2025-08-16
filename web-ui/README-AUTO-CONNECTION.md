# Bot 自动连接功能说明

## 概述

Web UI 现在支持自动与 Discord Bot 建立连接，提供实时的状态监控和双向通信能力。

## 功能特性

### 🔄 自动连接
- **自动发现**: 自动尝试多个可能的服务器地址
- **智能重试**: 指数退避重连机制
- **连接质量**: 实时延迟监控和连接质量评估
- **故障转移**: 网络恢复时自动重连

### 📡 实时通信
- **WebSocket 连接**: 双向实时通信
- **心跳检测**: 定期健康检查
- **事件监听**: 监听 Bot 状态变化和通知
- **消息传递**: 支持向 Bot 发送控制命令

### 🎯 状态监控
- **连接状态**: 实时显示连接状态
- **Bot 信息**: 显示 Bot 版本、服务器数量等
- **性能指标**: 延迟、连接质量等
- **系统监控**: CPU、内存、磁盘使用情况

## 配置说明

### 环境变量

复制 `.env.example` 到 `.env` 并配置以下变量：

```bash
# Bot API 地址
NEXT_PUBLIC_BOT_API_URL=http://localhost:8000

# WebSocket 地址
NEXT_PUBLIC_BOT_WS_URL=ws://localhost:8000/ws

# API 密钥（可选）
NEXT_PUBLIC_BOT_API_KEY=your_api_key_here
```

### 自动发现

如果未配置环境变量，系统会自动尝试以下地址：
- `http://localhost:8000`
- `http://127.0.0.1:8000`
- `http://potato-bot:8000`
- `http://bot:8000`
- `http://app:8000`

### 健康检查端点

系统会尝试以下健康检查端点：
- `/api/health`
- `/health`
- `/status`
- `/ping`

## 使用方法

### 1. 自动连接

系统启动时会自动尝试连接：

```typescript
// 在应用启动时自动执行
import { BotConnectionProvider } from '@/components/providers/bot-connection-provider'

function App() {
  return (
    <BotConnectionProvider autoConnect={true}>
      {/* 你的应用内容 */}
    </BotConnectionProvider>
  )
}
```

### 2. 手动控制连接

```typescript
import { useBotConnection } from '@/lib/connection/use-bot-connection'

function MyComponent() {
  const { 
    isConnected, 
    connectionStatus, 
    connect, 
    disconnect, 
    reconnect 
  } = useBotConnection()

  return (
    <div>
      <p>状态: {connectionStatus}</p>
      <button onClick={connect}>连接</button>
      <button onClick={disconnect}>断开</button>
      <button onClick={reconnect}>重连</button>
    </div>
  )
}
```

### 3. 发送消息到 Bot

```typescript
import { useBotConnection } from '@/lib/connection/use-bot-connection'

function ControlPanel() {
  const { sendMessage, isConnected } = useBotConnection()

  const sendCommand = () => {
    if (isConnected) {
      sendMessage({
        type: 'command',
        action: 'reload_config',
        data: { /* 额外数据 */ }
      })
    }
  }

  return (
    <button onClick={sendCommand} disabled={!isConnected}>
      重载配置
    </button>
  )
}
```

### 4. 监听 Bot 事件

```typescript
import { useEffect } from 'react'
import { botConnector } from '@/lib/connection/bot-connector'

function EventListener() {
  useEffect(() => {
    const handleNotification = (notification: any) => {
      console.log('收到 Bot 通知:', notification)
    }

    const handleBotStatus = (status: any) => {
      console.log('Bot 状态更新:', status)
    }

    botConnector.on('notification', handleNotification)
    botConnector.on('botStatusUpdate', handleBotStatus)

    return () => {
      botConnector.off('notification', handleNotification)
      botConnector.off('botStatusUpdate', handleBotStatus)
    }
  }, [])

  return null
}
```

## 组件说明

### BotConnectionStatus
完整的连接状态显示组件：
```typescript
import { BotConnectionStatus } from '@/components/bot/bot-connection-status'

<BotConnectionStatus />
```

### BotConnectionIndicator
精简的连接状态指示器：
```typescript
import { BotConnectionIndicator } from '@/components/bot/bot-connection-status'

<BotConnectionIndicator />
```

## 页面导航

- **系统监控**: `/system-monitor` - 查看详细的连接状态和系统指标
- **仪表板**: `/dashboard` - 主要管理界面
- **其他页面**: 都会显示连接状态指示器

## WebSocket 事件类型

支持的 WebSocket 事件：

```typescript
export const WS_EVENTS = {
  AUTH: 'auth',           // 认证
  HEARTBEAT: 'heartbeat', // 心跳
  BOT_STATUS: 'bot_status', // Bot 状态更新
  NOTIFICATION: 'notification', // 通知
  ERROR: 'error',         // 错误
  PING: 'ping',           // Ping
  PONG: 'pong',           // Pong
  TEST: 'test',           // 测试
}
```

## 连接质量等级

- **excellent** (< 100ms): 优秀
- **good** (< 300ms): 良好  
- **poor** (< 1000ms): 较差
- **disconnected** (≥ 1000ms): 断开

## 故障排除

### 1. 无法连接
- 检查 Bot 服务器是否运行
- 确认端口 8000 未被占用
- 检查防火墙设置

### 2. WebSocket 连接失败
- 确认 WebSocket 端点可访问
- 检查代理服务器配置
- 验证 HTTPS/WSS 配置（生产环境）

### 3. 频繁重连
- 检查网络稳定性
- 调整重连参数
- 查看控制台错误日志

### 4. API 密钥认证失败
- 确认 API 密钥正确
- 检查 Bot 服务器认证配置
- 验证密钥权限

## 开发调试

启用调试日志：
```bash
# 开发模式会显示详细的连接日志
NODE_ENV=development npm run dev
```

查看连接状态：
1. 打开浏览器开发者工具
2. 查看 Console 标签页的连接日志
3. 访问 `/system-monitor` 页面查看详细状态

## 性能优化

- 连接状态缓存 1 秒
- 健康检查间隔 30 秒（开发）/ 60 秒（生产）
- 自动清理过期的监听器
- 智能重连避免过度重试

## 安全考虑

- API 密钥通过环境变量配置
- WebSocket 连接支持认证
- 自动发现仅限内网地址
- 生产环境建议使用 HTTPS/WSS