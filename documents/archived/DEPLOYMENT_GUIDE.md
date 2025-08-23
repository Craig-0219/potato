# 🚀 Potato Bot v3.0.1 - 企業級部署指南

> **🏛️ 多功能 GDPR 合規 Discord Bot 系統 - 生產環境部署手冊**

---

## 📋 部署概覽

Potato Bot v3.0.1 是一個企業級多功能 Discord Bot 系統，專為生產環境設計，支援無限數量的 Discord 伺服器，具備完整的 GDPR 合規性和零信任安全架構。

### 🎯 **部署特色**
- 🔒 **零信任安全模型** - 所有操作強制身份驗證
- 🏢 **多伺服器架構** - 完全數據隔離，支援無限伺服器  
- 🇪🇺 **100% GDPR 合規** - 完整數據保護法規支援
- 📊 **企業級監控** - 即時分析和智能警報
- 💾 **自動備份** - 多層次數據保護機制

---

## 🛠️ 系統需求

### 📊 **最低硬體需求**
```
CPU: 2 核心 (推薦 4 核心)
記憶體: 2GB RAM (推薦 4GB+)
儲存空間: 10GB SSD (推薦 50GB+)
網路: 100Mbps 上下行頻寬
```

### 💻 **軟體環境需求**
```
作業系統: Linux (Ubuntu 20.04+ / CentOS 8+ / Debian 11+)
Python: 3.10+ (推薦 3.11+)
MySQL: 8.0+ (企業版推薦)
Redis: 6.0+ (用於快取和會話管理)
Node.js: 18+ (用於 Web 管理界面)
Nginx: 1.18+ (用於反向代理，可選)
```

### 🌐 **網路需求**
- **Discord API 連接**: discord.com:443 (必須)
- **MySQL 連接**: 內網或外網 MySQL 伺服器
- **Redis 連接**: 內網 Redis 伺服器
- **Web 管理界面**: HTTP/HTTPS 埠 (3000, 8000)

---

## 🚀 快速部署 (生產環境)

### 1️⃣ **環境準備**

```bash
# 更新系統
sudo apt update && sudo apt upgrade -y

# 安裝必要依賴
sudo apt install -y python3.11 python3.11-pip python3.11-venv
sudo apt install -y mysql-server redis-server nginx git

# 安裝 Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# 創建專用用戶
sudo useradd -m -s /bin/bash potato-bot
sudo usermod -aG sudo potato-bot
```

### 2️⃣ **資料庫設置**

```bash
# MySQL 安全配置
sudo mysql_secure_installation

# 創建資料庫和用戶
sudo mysql -u root -p
```

```sql
-- 創建資料庫
CREATE DATABASE potato_enterprise CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 創建專用用戶
CREATE USER 'potato_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON potato_enterprise.* TO 'potato_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 3️⃣ **Redis 配置**

```bash
# 編輯 Redis 配置
sudo nano /etc/redis/redis.conf

# 重要配置項目
# bind 127.0.0.1 ::1
# requirepass your_redis_password
# maxmemory 256mb
# maxmemory-policy allkeys-lru

# 重啟 Redis
sudo systemctl restart redis-server
sudo systemctl enable redis-server
```

### 4️⃣ **Bot 部署**

```bash
# 切換到專用用戶
sudo -u potato-bot -i

# 下載專案
git clone https://github.com/Craig-0219/potato.git
cd potato

# 創建虛擬環境
python3.11 -m venv venv
source venv/bin/activate

# 安裝依賴
pip install --upgrade pip
pip install -r requirements.txt

# 創建配置文件
cp .env.example .env
nano .env
```

### 5️⃣ **環境配置**

編輯 `.env` 文件：

```env
# Discord Bot 配置
DISCORD_TOKEN=your_discord_bot_token

# 資料庫配置 (企業級)
DB_HOST=localhost
DB_PORT=3306
DB_NAME=potato_enterprise
DB_USER=potato_user
DB_PASSWORD=your_secure_password

# Redis 配置
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=your_redis_password

# Web 界面配置
WEB_PORT=3000
API_PORT=8000

# 安全配置
JWT_SECRET=your_jwt_secret_key_here
ENCRYPTION_KEY=your_encryption_key_here

# 監控配置
SENTRY_DSN=your_sentry_dsn_optional
LOG_LEVEL=INFO

# 備份配置
BACKUP_ENABLED=true
BACKUP_RETENTION_DAYS=30
```

### 6️⃣ **初始化系統**

```bash
# 初始化資料庫 (自動建立所有表格)
python bot/main.py --init-only

# 測試連接
python -c "
from bot.db.pool import db_pool
import asyncio
async def test():
    await db_pool.initialize('localhost', 3306, 'potato_user', 'password', 'potato_enterprise')
    print('✅ 資料庫連接成功')
asyncio.run(test())
"
```

### 7️⃣ **Web 界面部署**

```bash
# 安裝 Web 依賴
cd web-ui
npm install

# 建置生產版本
npm run build

# 返回主目錄
cd ..
```

---

## 🎛️ 系統服務配置

### 📝 **Systemd 服務設定**

創建 Bot 服務：
```bash
sudo nano /etc/systemd/system/potato-bot.service
```

```ini
[Unit]
Description=Potato Bot v3.0.1 - Enterprise Discord Management System
After=network.target mysql.service redis.service

[Service]
Type=simple
User=potato-bot
Group=potato-bot
WorkingDirectory=/home/potato-bot/potato
Environment=PATH=/home/potato-bot/potato/venv/bin
ExecStart=/home/potato-bot/potato/venv/bin/python bot/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=potato-bot

# 安全設置
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/potato-bot/potato
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

創建 Web 服務：
```bash
sudo nano /etc/systemd/system/potato-web.service
```

```ini
[Unit]
Description=Potato Bot Web Interface
After=network.target potato-bot.service

[Service]
Type=simple
User=potato-bot
Group=potato-bot
WorkingDirectory=/home/potato-bot/potato/web-ui
Environment=NODE_ENV=production
Environment=PORT=3000
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 🔄 **啟動服務**

```bash
# 重新載入 systemd
sudo systemctl daemon-reload

# 啟動服務
sudo systemctl start potato-bot
sudo systemctl start potato-web

# 設定開機自啟
sudo systemctl enable potato-bot
sudo systemctl enable potato-web

# 檢查狀態
sudo systemctl status potato-bot
sudo systemctl status potato-web
```

---

## 🌐 Nginx 反向代理設定

### 📝 **Nginx 配置**

```bash
sudo nano /etc/nginx/sites-available/potato-bot
```

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    
    # 重定向到 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;
    
    # SSL 配置 (使用 Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # 安全標頭
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Web 管理界面
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
    
    # API 端點
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket 支援
    location /ws/ {
        proxy_pass http://localhost:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 🔒 **SSL 憑證設定**

```bash
# 安裝 Certbot
sudo apt install certbot python3-certbot-nginx -y

# 取得 SSL 憑證
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# 設定自動續期
sudo crontab -e
# 新增：0 12 * * * /usr/bin/certbot renew --quiet
```

### ✅ **啟用網站**

```bash
# 啟用網站
sudo ln -s /etc/nginx/sites-available/potato-bot /etc/nginx/sites-enabled/

# 測試配置
sudo nginx -t

# 重新載入 Nginx
sudo systemctl reload nginx
```

---

## 📊 監控與日誌

### 📈 **系統監控設定**

```bash
# 安裝監控工具
sudo apt install -y htop iotop nethogs

# 設定日誌輪轉
sudo nano /etc/logrotate.d/potato-bot
```

```
/var/log/potato-bot/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 potato-bot potato-bot
    postrotate
        systemctl reload potato-bot
    endscript
}
```

### 📋 **日誌檢查指令**

```bash
# 查看 Bot 日誌
sudo journalctl -u potato-bot -f

# 查看 Web 服務日誌
sudo journalctl -u potato-web -f

# 查看 Nginx 日誌
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# 系統資源監控
htop
systemctl status potato-bot
systemctl status potato-web
```

---

## 🔧 維護與更新

### 🔄 **定期維護檢查表**

**每日檢查**:
- [ ] 檢查服務狀態 `systemctl status potato-bot potato-web`
- [ ] 檢查日誌是否有錯誤 `journalctl -u potato-bot --since today`
- [ ] 檢查系統資源使用 `htop`
- [ ] 檢查備份是否成功

**每週檢查**:
- [ ] 更新系統套件 `sudo apt update && sudo apt upgrade`
- [ ] 檢查 SSL 憑證狀態 `sudo certbot certificates`
- [ ] 檢查磁碟空間使用 `df -h`
- [ ] 檢查資料庫效能 `SHOW PROCESSLIST;`

**每月檢查**:
- [ ] 清理舊日誌檔案
- [ ] 檢查備份完整性
- [ ] 更新 Bot 到最新版本
- [ ] 檢查安全更新

### 📦 **Bot 更新流程**

```bash
# 1. 備份當前版本
sudo systemctl stop potato-bot potato-web
cp -r /home/potato-bot/potato /home/potato-bot/potato-backup-$(date +%Y%m%d)

# 2. 拉取最新代碼
cd /home/potato-bot/potato
git fetch origin
git checkout v3.0.1  # 或最新版本標籤

# 3. 更新依賴
source venv/bin/activate
pip install --upgrade -r requirements.txt

# 4. 更新 Web 界面
cd web-ui
npm install
npm run build
cd ..

# 5. 資料庫遷移 (如需要)
python bot/main.py --migrate

# 6. 重啟服務
sudo systemctl start potato-bot potato-web

# 7. 驗證更新
sudo systemctl status potato-bot potato-web
```

---

## 🛡️ 安全最佳實踐

### 🔒 **系統安全設定**

```bash
# 防火牆設定
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 禁用不必要的服務
sudo systemctl disable apache2 2>/dev/null || true
sudo systemctl stop apache2 2>/dev/null || true

# 設定自動安全更新
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure unattended-upgrades
```

### 🔐 **Discord Bot 安全**

1. **Token 安全**:
   - 使用環境變數儲存 Token
   - 定期輪換 Bot Token
   - 監控 Token 使用情況

2. **權限管理**:
   - 只授予 Bot 必要的權限
   - 定期檢查權限使用情況
   - 實施最小權限原則

3. **網路安全**:
   - 使用 HTTPS/WSS 加密通信
   - 實施速率限制
   - 監控異常 API 調用

---

## 🚨 故障排除

### ⚡ **常見問題解決**

**Bot 無法啟動**:
```bash
# 檢查日誌
sudo journalctl -u potato-bot -n 50

# 檢查配置文件
cat /home/potato-bot/potato/.env

# 檢查資料庫連接
mysql -h localhost -u potato_user -p potato_enterprise
```

**Web 界面無法訪問**:
```bash
# 檢查服務狀態
sudo systemctl status potato-web nginx

# 檢查端口占用
sudo netstat -tlnp | grep :3000
sudo netstat -tlnp | grep :443
```

**資料庫連接問題**:
```bash
# 檢查 MySQL 服務
sudo systemctl status mysql

# 檢查連接權限
mysql -u potato_user -p -e "SHOW GRANTS FOR CURRENT_USER;"
```

### 📞 **技術支援聯繫**

如遇到無法解決的問題，請聯繫技術支援：

- **📧 Email**: support@potato-bot.com
- **💬 Discord**: [官方支援伺服器](https://discord.gg/potato-support)
- **🐛 GitHub Issues**: [回報問題](https://github.com/Craig-0219/potato/issues)
- **📚 文檔中心**: [完整文檔](docs/README.md)

---

<div align="center">

## 🎉 **部署完成！**

### 🏛️ **Potato Bot v3.0.1 企業級系統已就緒**

[![系統狀態](https://img.shields.io/badge/系統狀態-運行中-success?style=for-the-badge)](https://your-domain.com)
[![安全等級](https://img.shields.io/badge/安全等級-企業級-green?style=for-the-badge)](PHASE_6_COMPLETION_REPORT.md)
[![GDPR合規](https://img.shields.io/badge/GDPR-合規-blue?style=for-the-badge)](https://gdpr.eu/)

**🌟 您的企業級多租戶 Discord Bot 系統已準備好為全球用戶提供服務！🌟**

**[🌐 管理界面](https://your-domain.com) • [📚 用戶手冊](docs/user-guides/USER_MANUAL.md) • [📊 系統監控](https://your-domain.com/system)**

---

*🛡️ 零信任安全 • 🇪🇺 GDPR 合規 • 🏢 多租戶支援 • 📊 企業級監控*

</div>