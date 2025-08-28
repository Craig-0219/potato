# 🚀 Quick Start Guide

> ⚡ Get Potato Bot running in 5 minutes

## 📋 Prerequisites

- Python 3.10+
- Discord Bot Token
- Database (PostgreSQL recommended, SQLite supported)

## 🏃‍♂️ Quick Setup

### 1. Environment Configuration
```bash
# Copy configuration template
cp .env.example .env

# Edit with your settings
nano .env
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Launch Bot
```bash
# Recommended: Python launcher
python start.py

# Alternative: Platform-specific
./start.sh    # Linux/macOS
start.bat     # Windows
```

## ⚙️ Essential Configuration

Edit `.env` file with your settings:

```env
# Required
DISCORD_TOKEN=your_bot_token_here
DATABASE_URL=postgresql://user:pass@localhost:5432/potato

# Optional
REDIS_URL=redis://localhost:6379
ENABLE_API_SERVER=true
API_EXTERNAL_ACCESS=false
```

## 🎯 First Steps

1. **Invite Bot**: Generate invite link with admin permissions
2. **Setup Channels**: Bot will auto-create necessary channels
3. **Configure Permissions**: Use `/admin setup` command
4. **Test Features**: Try `/ticket create` or `/vote create`

## 🆘 Troubleshooting

- **Database Issues**: Check connection string in `.env`
- **Permission Errors**: Ensure bot has admin permissions
- **API Problems**: Set `ENABLE_API_SERVER=false` if not needed
- **Redis Optional**: Bot works without Redis (uses memory cache)

## 📚 Key Commands

- `/ticket create` - Create support ticket
- `/vote create` - Start a vote/poll
- `/admin setup` - Initial server configuration
- `/help` - Full command list

---

**Need help?** Check the main README.md for detailed documentation.