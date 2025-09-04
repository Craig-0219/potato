# GitHub Token 設置指南

## 🚨 修復 GitHub API 401 錯誤

當您看到 "GitHub API 請求失敗: 401" 錯誤時，這表示 GitHub API 認證失敗。以下是解決方法：

## 📝 問題原因

- 沒有配置 `GITHUB_TOKEN` 環境變數
- GitHub API 對未認證請求有嚴格的速率限制
- 私有倉庫需要認證才能訪問

## 🔧 解決步驟

### 1. 創建 GitHub Personal Access Token

1. 登入 GitHub
2. 前往 Settings → Developer settings → Personal access tokens → Tokens (classic)
3. 點擊 "Generate new token (classic)"
4. 填寫 Token 說明（如: "Potato Bot Auto Updater"）
5. 選擇權限範圍：
   - `repo` - 完整倉庫存取權限
   - `public_repo` - 只需要公開倉庫權限（如果倉庫是公開的）
6. 點擊 "Generate token"
7. **立即複製 token**（之後無法再查看）

### 2. 配置環境變數

將 token 添加到 `.env` 文件：

```env
# GitHub API 認證 (修復 401 錯誤)
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. 重新啟動 Bot

設置環境變數後，重新啟動 Bot 以生效。

## 🎯 驗證設置

重新啟動後，您應該看到：

✅ **成功**: 
```
📡 自動更新服務已啟動，使用認證的 GitHub API
```

❌ **仍有問題**:
```
⚠️ 未配置 GITHUB_TOKEN 環境變數，GitHub API 請求可能受速率限制影響
```

## 🔒 安全注意事項

- **不要** 將 token 提交到版本控制系統
- 定期更換 token (建議每 90 天)
- 只授予必要的最小權限
- 如果 token 洩露，立即在 GitHub 上撤銷

## 📊 API 速率限制

- **未認證**: 每小時 60 次請求
- **已認證**: 每小時 5000 次請求

## 🚀 額外功能

配置 GITHUB_TOKEN 後，您將獲得：

- 更高的 API 速率限制
- 私有倉庫存取能力
- 更穩定的自動更新功能
- 詳細的版本比較資訊

## 🆘 故障排除

### Token 無效
```
❌ GitHub API 認證失敗 (401)：請檢查 GITHUB_TOKEN 環境變數
```

**解決方法**: 檢查 token 是否正確，是否已過期

### 權限不足
```
❌ GitHub API 請求失敗: 403
```

**解決方法**: 檢查 token 權限是否包含 `repo` 或 `public_repo`

### 速率限制
```
❌ GitHub API 速率限制 (403)：請配置 GITHUB_TOKEN 以提高限制
```

**解決方法**: 配置有效的 GITHUB_TOKEN 以獲得更高限制

## 📞 需要協助？

如果仍然遇到問題，請檢查：
1. `.env` 文件是否正確配置
2. Bot 是否已重新啟動
3. Token 是否具有正確權限
4. Token 是否已過期