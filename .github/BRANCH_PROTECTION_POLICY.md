# Branch Protection Policy

## 🛡️ 分支保護機制

為了維護代碼品質和防止意外的分支合併，本專案實施以下分支保護政策：

## 📋 分支架構

```
main (生產環境)
├── ptero (部署分支)
└── dev (開發分支)
    ├── feature/* (功能分支)
    ├── bugfix/* (修復分支)
    └── hotfix/* (緊急修復，可直接合併到 main)
```

## 🚫 禁止的操作

### 1. 直接合併 dev → main
- **原因**: 繞過自動化測試和品質檢查
- **替代方案**: 使用 smart-auto-merge workflow
- **觸發方式**: 推送到 dev 分支時自動執行

### 2. Feature/Bugfix 分支直接合併到 main
- **原因**: 應先經過 dev 分支的整合測試
- **正確流程**: feature/bugfix → dev → main

## ✅ 允許的操作

### 1. 自動合併流程 (推薦)
```bash
# 開發完成後推送到 dev
git push origin dev
# smart-auto-merge workflow 自動執行：
# 1. 風險評估
# 2. 完整測試
# 3. 自動合併到 main
# 4. 部署到 ptero
```

### 2. 功能開發流程
```bash
# 創建功能分支
git checkout -b feature/new-awesome-feature dev
# 開發完成後
git push origin feature/new-awesome-feature
# 創建 PR: feature/new-awesome-feature → dev
```

### 3. 緊急修復流程
```bash
# 創建熱修復分支
git checkout -b hotfix/critical-security-fix main
# 修復完成後
git push origin hotfix/critical-security-fix
# 創建 PR: hotfix/critical-security-fix → main (允許)
```

## 🔧 實施機制

### GitHub Actions 工作流程
- **branch-protection.yml**: 自動檢查和阻止違規合併
- **smart-auto-merge.yml**: 智能自動合併系統

### 檢查項目
1. **分支命名規範檢查**
2. **目標分支驗證**
3. **合併路徑驗證**
4. **風險評估**

## 📊 保護效果

| 源分支 | 目標分支 | 狀態 | 說明 |
|--------|----------|------|------|
| dev | main | ❌ 阻止 | 使用 smart-auto-merge |
| feature/* | main | ❌ 阻止 | 應合併到 dev |
| bugfix/* | main | ❌ 阻止 | 應合併到 dev |
| hotfix/* | main | ✅ 允許 | 緊急修復 |
| feature/* | dev | ✅ 允許 | 標準開發流程 |
| bugfix/* | dev | ✅ 允許 | 標準修復流程 |

## 🛠️ 繞過機制 (僅緊急情況)

如果必須繞過保護機制：

```bash
# 僅適用於緊急情況
git push origin dev --force-with-lease
# 或者
git push origin main --force-with-lease
```

**⚠️ 警告**: 僅在系統故障或其他緊急情況下使用

## 📞 支援

如果遇到分支保護相關問題：
1. 檢查分支命名是否符合規範
2. 確認合併目標分支是否正確
3. 查看 GitHub Actions 執行日誌
4. 聯繫專案維護者