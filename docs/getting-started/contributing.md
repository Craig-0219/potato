# 🤝 貢獻指南

> 歡迎參與 Potato Bot 專案！本指南將協助您順利開始貢獻。

## 🌟 參與方式

我們歡迎各種形式的貢獻：

- 🐛 **錯誤回報** - 發現問題並提交詳細報告
- 💡 **功能建議** - 提出新功能想法
- 🔧 **程式碼貢獻** - 修復錯誤或實現新功能
- 📖 **文檔改進** - 完善或更新文檔
- 🎨 **使用者體驗** - 改善介面和互動設計
- 🧪 **測試增強** - 編寫或改進測試案例

## 📋 開始之前

### 行為準則

參與本專案即表示您同意遵守我們的行為準則：

- **尊重他人** - 以禮貌和專業的態度對待所有參與者
- **包容性** - 歡迎不同背景和經驗水平的貢獻者
- **建設性** - 提供有助於專案改進的建設性回饋
- **協作精神** - 與團隊成員積極協作，共同改進專案

### 技術要求

- **Python** 3.10+
- **Git** 基礎操作
- **Discord** 開發基礎知識 (可選)
- **測試驅動開發** 概念 (推薦)

## 🚀 快速開始

### 1. 環境準備

```bash
# 1. Fork 專案到您的 GitHub 帳戶
# 2. 複製您的 Fork
git clone https://github.com/YOUR_USERNAME/potato.git
cd potato

# 3. 設置上游源
git remote add upstream https://github.com/Craig-0219/potato.git

# 4. 切換到開發分支
git checkout develop
git pull upstream develop

# 5. 設置開發環境
make dev-setup
```

### 2. 創建功能分支

```bash
# 基於 develop 創建新分支
git checkout -b feature/your-feature-name

# 分支命名慣例：
# feature/功能名稱     - 新功能
# fix/問題描述        - 錯誤修復
# docs/文檔主題       - 文檔更新
# refactor/重構範圍   - 程式碼重構
# test/測試範圍       - 測試改進
```

## 💻 開發流程

### 程式碼開發

1. **遵循程式碼風格**
   ```bash
   # 格式化程式碼
   make format
   
   # 檢查程式碼品質
   make lint
   ```

2. **編寫測試**
   ```bash
   # 為新功能編寫測試
   # 確保測試通過
   make test
   
   # 檢查測試覆蓋率
   make test-coverage
   ```

3. **安全檢查**
   ```bash
   # 執行安全掃描
   make security
   ```

### 提交規範

我們使用 [Conventional Commits](https://www.conventionalcommits.org/) 規範：

```
<類型>[可選範圍]: <描述>

[可選正文]

[可選頁腳]
```

**類型說明：**
- `feat` - 新功能
- `fix` - 錯誤修復
- `docs` - 文檔更新
- `style` - 程式碼格式調整
- `refactor` - 程式碼重構
- `test` - 測試相關
- `chore` - 維護性工作

**範例：**
```bash
git commit -m "feat(tickets): add auto-assignment feature

- Implement automatic ticket assignment based on keywords
- Add configuration options for assignment rules
- Include unit tests for assignment logic

Closes #123"
```

### Pull Request 流程

1. **確保品質**
   ```bash
   # 執行完整檢查
   make quality-check
   
   # 確保所有測試通過
   make test
   ```

2. **更新分支**
   ```bash
   # 同步最新的 develop
   git fetch upstream
   git rebase upstream/develop
   ```

3. **推送分支**
   ```bash
   git push origin feature/your-feature-name
   ```

4. **創建 Pull Request**
   - 使用描述性標題
   - 填寫詳細的 PR 描述
   - 連結相關 Issues
   - 添加適當的標籤

## 📝 Pull Request 模板

創建 PR 時，請包含以下資訊：

```markdown
## 📋 變更摘要
簡要描述此 PR 的主要變更

## 🎯 變更類型
- [ ] 新功能
- [ ] 錯誤修復
- [ ] 文檔更新
- [ ] 程式碼重構
- [ ] 效能改進
- [ ] 測試改進

## 🔗 相關 Issues
修復 #XXX

## 📸 截圖 (如適用)
如果涉及 UI 變更，請提供截圖

## ✅ 檢查清單
- [ ] 程式碼已通過所有測試
- [ ] 已添加必要的測試
- [ ] 文檔已更新 (如需要)
- [ ] 遵循程式碼風格指南
- [ ] 已執行安全檢查
- [ ] PR 標題遵循 Conventional Commits

## 🧪 測試說明
描述如何測試此變更
```

## 🔍 程式碼審查

### 審查原則

- **功能性** - 程式碼是否正確實現需求
- **可讀性** - 程式碼是否易於理解和維護
- **效能** - 是否有效能問題或改進空間
- **安全性** - 是否存在安全隱患
- **測試** - 測試是否充分且有效

### 回應審查

- **積極回應** - 及時回應審查意見
- **開放態度** - 接受建設性的改進建議
- **詳細說明** - 對複雜變更提供充分解釋
- **持續改進** - 根據意見持續完善程式碼

## 🐛 錯誤回報

### 回報模板

```markdown
## 🐛 錯誤描述
簡潔清楚地描述錯誤

## 🔄 重現步驟
1. 執行 '...'
2. 點擊 '...'
3. 觀察錯誤

## 🎯 預期行為
描述應該發生的正確行為

## 📸 截圖
如果適用，添加截圖幫助解釋問題

## 🖥️ 環境資訊
- OS: [例如 Ubuntu 22.04]
- Python: [例如 3.11.2]
- Bot Version: [例如 3.1.0]

## 📋 額外資訊
其他可能有助於解決問題的資訊
```

## 💡 功能建議

### 建議模板

```markdown
## 🚀 功能描述
清楚描述您想要的功能

## 💭 動機和背景
解釋為什麼需要這個功能

## 📋 詳細設計
詳細描述功能應該如何工作

## 🎯 接受標準
定義功能完成的標準

## 🔗 額外資訊
相關連結、參考資料等
```

## 🏷️ 分支保護規則

### Main 分支
- 🚫 **禁止直接推送**
- ✅ **需要 PR 審查**
- 🧪 **必須通過所有檢查**
- 📝 **需要線性歷史記錄**

### Develop 分支
- ✅ **允許快進合併**
- 🧪 **必須通過基本檢查**
- 📝 **推薦 PR 審查**

## 🎉 貢獻者認可

我們重視每一位貢獻者的努力：

- **Contributors 列表** - 自動更新到 README
- **Release Notes** - 重大貢獻會在發布說明中提及
- **Special Thanks** - 傑出貢獻者會獲得特別感謝

## 📚 開發資源

- 🛠️ [專案設置指南](project-setup.md)
- 🏗️ [系統架構文檔](../system-design/admin-permissions.md)
- 🔧 [API 參考](../developer-docs/api-reference.md)
- 🧪 [測試指南](../developer-docs/troubleshooting.md)

## 📞 取得協助

遇到問題？我們隨時為您提供協助：

- 💬 [Discord 社群](https://discord.gg/your-server)
- 🐛 [GitHub Issues](https://github.com/Craig-0219/potato/issues)
- 📧 [Email 支援](mailto:support@your-domain.com)

---

🎉 **感謝您的貢獻！**

每一個 PR、每一個 Issue、每一行程式碼都讓 Potato Bot 變得更好。我們期待與您一起打造最優秀的 Discord 機器人！

## 📋 快速檢查清單

開始貢獻前，請確認：

- [ ] 已閱讀並理解行為準則
- [ ] 已設置本地開發環境
- [ ] 了解 Git 工作流程
- [ ] 知道如何撰寫測試
- [ ] 理解程式碼風格要求
- [ ] 會使用專案的開發工具