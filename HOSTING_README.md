# 🚀 Potato Discord Bot - Hosting Version

> **Pure production version optimized for hosting environments**

## 🎯 Hosting Features

This branch is specifically optimized for hosting platforms like:
- **Pterodactyl Panel**
- **Docker containers**
- **VPS deployments**
- **Cloud hosting services**

## ⚡ Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env

# Edit your configuration
nano .env

# Start the bot
python start.py
```

## 📦 What's Included

- ✅ **Core Bot Functionality** - All Discord features
- ✅ **Database Support** - MySQL/PostgreSQL ready
- ✅ **API Server** - RESTful API endpoints
- ✅ **Auto-scaling** - Memory and CPU optimized
- ✅ **Production Logging** - Structured log output

## 📋 Requirements

- **Python 3.10+**
- **Discord Bot Token**
- **Database** (MySQL/PostgreSQL/SQLite)
- **1GB RAM minimum**
- **2 CPU cores recommended**

## 🔧 Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# Discord Configuration
DISCORD_TOKEN=your_discord_bot_token_here
DISCORD_CLIENT_ID=your_client_id
DISCORD_CLIENT_SECRET=your_client_secret

# Database Configuration  
DB_HOST=localhost
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=potato_bot
DB_PORT=3306

# API Configuration
ENABLE_API_SERVER=true
API_PORT=8000
```

## 🚀 Deployment

### Pterodactyl Panel
1. Upload this branch to your server
2. Install Python 3.10+ egg
3. Set startup command: `python start.py`
4. Configure environment variables in panel

### Docker
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "start.py"]
```

### VPS/Cloud
```bash
# Clone this branch
git clone -b ptero https://github.com/your-repo/potato.git
cd potato

# Setup
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your settings

# Run
python start.py
```

## 🔍 Health Check

The bot includes built-in health monitoring:
- **HTTP Endpoint**: `GET /health`
- **Database Connection**: Auto-tested
- **Discord API**: Connection status
- **Memory Usage**: Real-time monitoring

## 📊 Resource Usage

**Recommended Specifications:**
- **RAM**: 1-2GB (scales with server count)
- **CPU**: 2 cores minimum
- **Storage**: 10GB for logs and database
- **Network**: Stable internet connection

## 🛠️ Support

This is the **production hosting version**. For:
- **Development**: Use `dev` branch
- **Documentation**: Use `main` branch
- **Issues**: Create GitHub issues

---

**🏗️ Optimized for hosting • 🚀 Production ready • ⚡ High performance**