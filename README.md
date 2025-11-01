# Advanced Telegram Bot

Production-grade Telegram bot with DST-safe scheduling, multi-user FSM state management, RBAC security system, and comprehensive admin panel.

## 🚀 Features

### Core Features
- **DST-Safe Scheduling**: Timezone-aware job scheduling with automatic DST handling
- **Multi-User FSM**: Per-user finite state machine with session persistence  
- **RBAC Security**: Role-based access control with granular permissions
- **Admin Panel**: Interactive inline keyboard administration interface
- **Error Recovery**: Comprehensive error handling with retry mechanisms
- **Health Monitoring**: Built-in health checks and telemetry

### Bot Commands

#### Public Commands
- `/start` - Start the bot
- `/stop` - Stop the bot  
- `/info` - Display bot information
- `/kontakt` - Show contact information

#### Admin Commands
- `/pusher` - Open admin panel (configurable alias)
  - **Set Info**: Configure bot name, channel, group, welcome message
  - **Set Kontakt**: Update contact information
  - **Add/Del Groups**: Manage group subscriptions
  - **Set Time/Ex-Time**: Configure scheduling intervals
  - **Status**: View system health and statistics

## 🛠️ Installation

### Prerequisites
- Python 3.11+ 
- Windows 11 (optimized for, but works on Linux/macOS)

### Quick Start

1. **Clone Repository**
   ```bash
   git clone https://github.com/pizdziaty-garfild/telegram-bot-advanced.git
   cd telegram-bot-advanced
   ```

2. **Setup Environment**
   ```powershell
   # Create virtual environment
   python -m venv venv
   
   # Activate (Windows)
   .\venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Configuration**
   ```bash
   # Copy environment template
   copy config\config.example.env .env
   
   # Edit .env with your settings:
   # - BOT_TOKEN (get from @BotFather)
   # - ADMIN_USERS (your Telegram user ID)
   # - OWNER_USERS (your Telegram user ID)
   ```

4. **Run Bot**
   ```bash
   python main.py
   ```

### Production Setup (Webhook)

1. **Configure Webhook in .env**
   ```env
   BOT_MODE=webhook
   WEBHOOK_URL=https://yourdomain.com
   WEBHOOK_PORT=8443
   TLS_CERT_PATH=certs/cert.pem  
   TLS_KEY_PATH=certs/private.key
   ```

2. **Generate SSL Certificate**
   ```bash
   # Self-signed for testing
   openssl req -newkey rsa:2048 -sha256 -nodes -keyout certs/private.key -x509 -days 365 -out certs/cert.pem
   ```

## 📁 Project Structure

```
telegram-bot-advanced/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies  
├── config/
│   ├── settings.py        # Configuration management
│   └── config.example.env # Environment template
├── bot/
│   ├── core/              # Core business logic
│   │   ├── bot_manager.py # Main application manager
│   │   ├── user_manager.py# FSM session management
│   │   ├── rbac.py        # Role-based access control
│   │   └── command_bus.py # Command pattern implementation
│   ├── domain/            # Business entities
│   │   └── models.py      # SQLAlchemy models & DTOs
│   ├── handlers/          # Telegram command handlers  
│   │   ├── user_commands.py   # Public commands
│   │   └── admin_commands.py  # Admin panel
│   ├── infra/             # Infrastructure layer
│   │   ├── database.py    # Database management
│   │   ├── scheduler.py   # DST-safe scheduling
│   │   ├── logging.py     # Structured logging
│   │   └── telemetry.py   # Monitoring & metrics
│   └── utils/             # Utility functions
├── tests/                 # Test suites
├── logs/                  # Log files
├── data/                  # Database files
└── scripts/               # Deployment scripts
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|----------|
| `BOT_TOKEN` | Telegram bot token | **Required** |
| `BOT_MODE` | `polling` or `webhook` | `polling` |
| `ADMIN_USERS` | Comma-separated admin user IDs | `[]` |
| `OWNER_USERS` | Comma-separated owner user IDs | `[]` |
| `DB_URL` | Database connection URL | SQLite |
| `SCHEDULER_TIMEZONE` | Scheduler timezone | `Europe/Warsaw` |
| `ADMIN_COMMAND_ALIAS` | Admin panel command | `pusher` |

### Database Support
- **Development**: SQLite (default)
- **Production**: PostgreSQL with connection pooling

### Scheduling Features
- **DST Safety**: Automatic daylight saving time handling
- **Timezone Aware**: All times stored in UTC, displayed in local timezone
- **Retry Logic**: Failed jobs automatically retried with exponential backoff  
- **Idempotent Jobs**: Prevents duplicate executions
- **Graceful Recovery**: Handles system restarts and crashes

## 🛡️ Security

### Role-Based Access Control (RBAC)
- **Owner**: Full system access
- **Admin**: Admin panel access, group/job management
- **User**: Basic bot functions  
- **Banned**: No access

### Security Features
- Input validation and sanitization
- Rate limiting protection
- Encrypted sensitive data storage
- Audit logging for admin actions
- Session management with TTL

## 📊 Monitoring

### Built-in Monitoring
- Health check endpoint (`:8080/health`)
- Structured logging with rotation
- Performance metrics collection
- Error tracking with Sentry integration

### Telemetry Data
- Active sessions and users
- Job execution statistics
- System resource usage
- Error rates and patterns

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=bot

# Run specific test suite  
pytest tests/unit/
pytest tests/integration/
```

## 🚀 Deployment

### Docker Deployment
```bash
# Build image
docker build -t telegram-bot-advanced .

# Run container
docker run -d --name bot --env-file .env telegram-bot-advanced
```

### Systemd Service (Linux)
```ini
[Unit]
Description=Advanced Telegram Bot
After=network.target

[Service]
Type=simple
User=bot
WorkingDirectory=/opt/telegram-bot-advanced
ExecStart=/opt/telegram-bot-advanced/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## 🔍 Troubleshooting

### Common Issues

**Bot not responding**
- Check `BOT_TOKEN` in `.env`
- Verify bot is started with `/start` command
- Check logs in `logs/bot.log`

**Admin panel access denied**
- Add your Telegram user ID to `ADMIN_USERS` in `.env`
- Get your user ID from @userinfobot

**Database connection errors**
- Ensure database file permissions are correct
- For PostgreSQL, verify connection string format

**Scheduling issues**
- Check timezone configuration
- Verify system time is correct
- Review scheduler logs for errors

### Debug Mode
Enable debug logging:
```env
DEBUG_MODE=true
LOG_LEVEL=DEBUG
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)  
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

For support and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review logs for error details

---

**Built with ❤️ for production use**