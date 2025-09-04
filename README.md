# 🥔 Potato Bot - Production Hosting

> **Enterprise-grade Discord bot with modern architecture, AI integration, and comprehensive features**

## 🚀 Quick Deploy

```bash
# 1. Install dependencies (using modern package management)
pip install -e .

# 2. Configure environment
cp .env.example .env
nano .env  # Edit with your settings

# 3. Start bot
python start.py
```

## 🏗️ Project Architecture

This project follows a **Domain-Driven Design (DDD)** architecture with modern Python practices:

```
src/
├── potato_bot/           # Main bot application
│   ├── features/        # Feature-based modules
│   │   ├── tickets/     # Ticket system domain
│   │   ├── economy/     # Economy system domain
│   │   ├── security/    # Security & moderation
│   │   ├── ai/          # AI integration
│   │   └── ...         # Other domains
│   ├── core/           # Core infrastructure
│   └── main.py         # Application entry point
├── potato_shared/      # Shared utilities & config
└── tests/             # Comprehensive test suite
```

## 📦 Core Features

### 🎫 **Ticket System**
- Multi-category support with SLA monitoring
- Auto-assignment and smart routing  
- Rating system and advanced analytics
- Customizable workflows and templates

### 🤖 **AI Integration** 
- OpenAI, Anthropic, Gemini API support
- Content analysis and sentiment detection
- Smart conversation management
- Daily usage quotas and rate limiting

### 💰 **Economy System**
- Virtual currency with daily bonuses
- Service costs integration
- User balance tracking

### 🎵 **Music & Entertainment**
- YouTube integration with playlist support
- Gaming features and mini-games
- Content moderation tools

### ⚙️ **Management & Automation**
- Guild management workflows
- Auto-moderation and filtering
- Dashboard with real-time monitoring
- Comprehensive logging system

## 🔧 Configuration

Essential environment variables in `.env`:

```env
# Discord Bot
DISCORD_TOKEN=your_bot_token_here
DISCORD_CLIENT_ID=your_client_id

# Database  
DB_HOST=localhost
DB_USER=your_db_user  
DB_PASSWORD=your_db_password
DB_NAME=potato_bot

# AI Services (Optional)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GEMINI_API_KEY=your_gemini_key

# Features
TICKET_AUTO_ASSIGNMENT=true
ECONOMY_ENABLED=true
CONTENT_ANALYSIS_ENABLED=true
```

See `.env.example` for complete configuration options.

## 🚀 Deployment Options

### 🦕 Pterodactyl Panel
```bash
# Startup Command
python start.py

# Environment Variables  
# Configure in Pterodactyl environment tab
DISCORD_TOKEN=your_token_here
DB_HOST=database_host
```

### 🐳 Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e .
EXPOSE 8000
CMD ["python", "start.py"]
```

### 🖥️ VPS/Cloud
```bash
git clone -b ptero https://github.com/Craig-0219/potato.git
cd potato
pip install -e .
cp .env.example .env
python start.py
```

## 🔧 Development Setup

For contributors and developers:

```bash
# Clone with development dependencies
git clone https://github.com/Craig-0219/potato.git
cd potato

# Install with development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/ tests/
ruff check src/ tests/ --fix

# Security scan
bandit -r src/
semgrep src/
```

## 📊 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **Python** | 3.10+ | 3.11+ |
| **RAM** | 512MB | 1GB+ |  
| **CPU** | 1 Core | 2+ Cores |
| **Storage** | 2GB | 5GB+ |
| **Network** | Stable | High-speed |

## 🔍 Health Monitoring

Built-in health checks:
- **API Endpoint**: `GET /health` (Port 8000)
- **Database**: Connection status
- **Discord**: API connectivity  
- **Resources**: Memory/CPU usage

## 🛠️ Troubleshooting

**Common Issues:**
- `ModuleNotFoundError`: Run `pip install -r requirements.txt`
- `Database connection failed`: Check DB credentials in `.env`
- `Discord API error`: Verify bot token and permissions
- `Port already in use`: Change `API_PORT` in `.env`

## 📞 Support

- 🐛 **Bug Reports**: GitHub Issues
- 💬 **Discord Support**: [Join Server](https://discord.gg/your-server)
- 📖 **Documentation**: Check `.env.example` for all options

---
🥔 **Production Ready** • ⚡ **High Performance** • 🔧 **Easy Deploy**