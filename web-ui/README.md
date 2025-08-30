# 🥔 Potato Bot Web UI

現代化的 Discord 機器人管理界面，提供企業級功能和響應式設計。

## ✨ 功能特色

- 🚀 **Next.js 14** - 基於最新的 React 框架
- 💪 **TypeScript** - 完整的類型安全
- 🎨 **Tailwind CSS** - 現代化的樣式框架
- 📱 **響應式設計** - 支援桌面、平板、手機
- 🔄 **PWA 支援** - 可安裝的 Web 應用
- 🌙 **深色模式** - 自動切換主題
- ⚡ **React Query** - 高效的狀態管理
- 🔐 **API 認證** - 安全的 API 金鑰認證

## 🛠️ 技術棧

### 核心框架
- **Next.js 14** - React 全端框架
- **React 18** - 用戶界面庫
- **TypeScript** - 類型安全的 JavaScript

### UI 和樣式
- **Tailwind CSS** - 實用程式優先的 CSS 框架
- **Headless UI** - 無樣式 UI 組件
- **Heroicons** - SVG 圖標庫
- **Framer Motion** - 動畫庫

### 狀態管理和 API
- **React Query (TanStack Query)** - 服務器狀態管理
- **Axios** - HTTP 客戶端
- **React Hook Form** - 表單處理
- **Zod** - 數據驗證

### 開發工具
- **ESLint** - 代碼檢查
- **Prettier** - 代碼格式化
- **TypeScript** - 靜態類型檢查

## 🚀 快速開始

### 1. 安裝依賴

```bash
cd web-ui
npm install
```

### 2. 環境設定

```bash
# 複製環境變數範本
cp .env.example .env.local

# 編輯環境變數
nano .env.local
```

### 3. 啟動開發伺服器

```bash
npm run dev
```

開啟瀏覽器訪問 [http://localhost:3000](http://localhost:3000)

### 4. 建置生產版本

```bash
# 建置
npm run build

# 啟動生產伺服器
npm start
```

## 📁 專案結構

```
web-ui/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── layout.tsx         # 根佈局
│   │   ├── page.tsx           # 首頁
│   │   ├── providers.tsx      # 全域提供者
│   │   └── globals.css        # 全域樣式
│   ├── components/            # React 組件
│   │   ├── ui/               # 基礎 UI 組件
│   │   ├── landing/          # 登陸頁面組件
│   │   └── layout/           # 佈局組件
│   ├── lib/                  # 工具庫
│   │   ├── api/              # API 客戶端
│   │   ├── auth/             # 認證系統
│   │   └── utils.ts          # 工具函數
│   ├── hooks/                # 自定義 React Hooks
│   ├── types/                # TypeScript 類型定義
│   └── styles/               # 額外樣式檔案
├── public/                    # 靜態資源
│   ├── manifest.json         # PWA 清單檔
│   └── icons/                # 應用圖標
├── next.config.js            # Next.js 配置
├── tailwind.config.js        # Tailwind CSS 配置
├── tsconfig.json             # TypeScript 配置
└── package.json              # 專案配置
```

## 🎯 主要頁面和功能

### 🏠 登陸頁面
- API 金鑰認證登入
- 功能特色展示
- 響應式設計

### 📊 儀表板（開發中）
- 系統總覽
- 關鍵性能指標
- 實時統計圖表

### 🎫 票券管理（開發中）
- 票券列表和篩選
- 票券詳情和編輯
- 批次操作

### 📈 分析統計（開發中）
- 互動式圖表
- 報告生成和導出
- 客服績效分析

## 🔧 開發指南

### 代碼風格
- 使用 **ESLint** 和 **Prettier** 保持代碼一致性
- 遵循 **TypeScript** 最佳實踐
- 組件使用 **PascalCase** 命名
- 檔案使用 **kebab-case** 命名

### 組件開發
```typescript
// 組件範例
interface ButtonProps {
  variant?: 'primary' | 'secondary'
  size?: 'sm' | 'md' | 'lg'
  children: React.ReactNode
}

export function Button({ variant = 'primary', size = 'md', children }: ButtonProps) {
  return (
    <button className={cn('btn', `btn-${variant}`, `btn-${size}`)}>
      {children}
    </button>
  )
}
```

### API 整合
```typescript
// API 調用範例
import { ApiClient } from '@/lib/api/client'

export function useTickets() {
  return useQuery({
    queryKey: ['tickets'],
    queryFn: () => ApiClient.tickets.list(),
  })
}
```

## 🚀 部署

### Vercel 部署
```bash
# 安裝 Vercel CLI
npm i -g vercel

# 部署
vercel
```

### Docker 部署
```bash
# 建置 Docker 映像
docker build -t potato-bot-web .

# 運行容器
docker run -p 3000:3000 potato-bot-web
```

### 靜態導出
```bash
# 生成靜態檔案
npm run build
npm run export
```

## 📱 PWA 功能

- ✅ **可安裝** - 用戶可將應用安裝到主螢幕
- ✅ **離線支援** - 基本功能可離線使用
- ✅ **推送通知** - 支援 Web Push 通知
- ✅ **響應式** - 適應各種螢幕尺寸
- ✅ **快速載入** - 優化的載入性能

## 🔒 安全性

- **API 金鑰認證** - 安全的身份驗證
- **HTTPS 強制** - 生產環境強制使用 HTTPS
- **CSP 頭** - 內容安全政策保護
- **XSS 防護** - 跨站腳本攻擊防護

## 📊 性能優化

- **代碼分割** - 按需載入組件
- **圖片優化** - Next.js 自動圖片優化
- **字體優化** - 自動字體載入優化
- **快取策略** - 智能快取管理

## 🛠️ 可用指令

```bash
# 開發
npm run dev          # 啟動開發伺服器
npm run build        # 建置生產版本
npm run start        # 啟動生產伺服器

# 代碼品質
npm run lint         # 執行 ESLint 檢查
npm run type-check   # 執行 TypeScript 檢查

# 維護
npm run clean        # 清理建置檔案
npm run analyze      # 分析打包大小
```

## 📈 開發狀態

### ✅ 已完成
- [x] 專案基礎架構
- [x] 認證系統
- [x] API 客戶端
- [x] UI 組件庫
- [x] 登陸頁面
- [x] PWA 配置

### 🚧 開發中
- [ ] 儀表板頁面
- [ ] 票券管理頁面
- [ ] 分析統計頁面
- [ ] 系統設定頁面

### 📅 計劃中
- [ ] 實時通知系統
- [ ] 離線數據同步
- [ ] 多語言支援
- [ ] 高級主題自定義

## 🤝 貢獻指南

1. Fork 專案
2. 創建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

## 📄 授權

本專案使用 MIT 授權條款 - 詳見 [LICENSE](LICENSE) 檔案

---

**🥔 Potato Bot Web UI - 讓 Discord 管理更簡單、更現代！**