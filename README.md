# Advanced Telegram Bot - Production Ready

Production-grade Telegram bot with advanced scheduling, RBAC, FSM, and database migrations.

## Features

- **DST-Safe Scheduler**: Global and per-group intervals with timezone support
- **Enhanced RBAC**: Role-based access control with Owner/Admin/User/Banned roles  
- **FSM Sessions**: Per-user finite state machines with persistence and TTL
- **Config Persistence**: Bot info, contact, and settings stored in database
- **Groups Management**: CRUD operations with pagination and validation
- **Job Metrics**: Retry/backoff, execution statistics, and monitoring
- **Database Migrations**: Automatic schema management with Alembic
- **Comprehensive Logging**: Structured logging with rotation
- **Telemetry**: Optional Sentry integration for error tracking

## Quick Start

### Windows (Automated)

1. **Setup** (one-time):
   ```cmd
   scripts\setup.bat
   ```
   This will:
   - Create virtual environment
   - Install dependencies  
   - Create required directories
   - Copy .env template
   - Open .env for configuration

2. **Configure** `.env` file:
   ```env
   BOT_TOKEN=your_bot_token_from_botfather
   ADMIN_USERS=your_telegram_id
   OWNER_USERS=your_telegram_id
   ```

3. **Run**:
   ```cmd
   scripts\run_dev.bat
   ```

### Manual Setup

1. **Install Python 3.11+** and create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   .\venv\Scripts\activate  # Windows
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```bash
   cp config/config.example.env .env
   # Edit .env with your settings
   ```

4. **Run migrations** (optional):
   ```bash
   python migrations.py upgrade
   ```

5. **Start bot**:
   ```bash
   python main.py
   ```

## Configuration

### Core Settings (.env)

```env
# Required
BOT_TOKEN=your_bot_token_from_botfather
ADMIN_USERS=123456789,987654321  # Comma-separated Telegram user IDs
OWNER_USERS=123456789            # Super admin user IDs

# Optional
BOT_MODE=polling                 # polling or webhook
ADMIN_COMMAND_ALIAS=pusher       # Custom admin command name
DATABASE_URL=sqlite:///./data/bot.db

# Scheduler (advanced)
SCHEDULER_TIMEZONE=Europe/Warsaw
SCHEDULER_MAX_WORKERS=5
JOB_MAX_RETRIES=3

# Logging
LOG_LEVEL=INFO
DEBUG_MODE=false

# Telemetry (optional)
SENTRY_DSN=your_sentry_dsn
```

## Usage

### User Commands

- `/start` - Start bot (shows custom welcome message if configured)
- `/stop` - Stop bot  
- `/info` - Show bot information (name, channels, bio, etc.)
- `/kontakt` - Show contact information

### Admin Panel

Use `/{ADMIN_COMMAND_ALIAS}` (default: `/pusher`) to access the admin panel:

**Set Info Menu:**
- **Name** - Bot display name
- **Bio** - Bot description  
- **Channel** - Primary channel link
- **Channel 2** - Secondary channel link
- **Group** - Group link
- **Welcome** - Custom welcome message for /start

**Groups Management:**
- **Add Groups** - Bulk add groups (supports: `-100123456789, @username`)
- **Del Groups** - Bulk remove groups  
- **List Groups** - Paginated list with status indicators (50/page)

**Scheduling:**
- **Set Time** - Global interval for all groups (in minutes)
- **Set Ex-Time** - Special interval for excluded groups

**Monitoring:**
- **Status** - Comprehensive system statistics including:
  - Bot and database status
  - Groups statistics (active/inactive/custom/excluded)  
  - Session statistics with FSM state distribution
  - Job metrics (success rate, execution times, retries)
  - Background cleanup information

### Database Migrations

The bot supports migrations:

```bash
# Manual migration commands
python migrations.py current   # Show current revision
python migrations.py upgrade   # Upgrade to latest  
python migrations.py history   # Show migration history
python migrations.py revision  # Create new migration
```

## Architecture

```
bot/
├── core/
│   ├── command_bus.py
│   ├── enhanced_scheduler_service.py
│   └── enhanced_user_manager.py
├── domain/
│   └── models.py
├── handlers/
│   ├── user_commands.py
│   ├── admin_commands.py
│   ├── enhanced_admin_panel.py
│   ├── enhanced_admin_message_handlers.py
│   ├── groups_list_handler.py
│   └── enhanced_status_handler.py
├── services/
│   ├── config_service.py
│   └── groups_service.py
└── infra/
    ├── database.py
    ├── logging.py
    └── telemetry.py
```

## Scheduler Features

### Interval Types

1. **Global Interval** - Default for all active groups
2. **Custom Interval** - Per-group override  
3. **Excluded Interval** - For groups excluded from global

### Job Management

- **Retry Logic**: Exponential backoff
- **Metrics Tracking**: Success rate, execution times, retries
- **Dynamic Reconfiguration**: Jobs regenerate when intervals change
- **Collision Prevention**: Max 1 instance per job, coalesce missed runs
- **DST Safety**: Timezone-aware scheduling

## Database Schema

Core tables:
- `users`, `sessions`, `groups`, `config`, `jobs`, `audit_logs`

## Development

### Running Tests

```bash
python -m pytest tests/
```

### Code Quality

```bash
black bot/ tests/
isort bot/ tests/
mypy bot/
```

## License

MIT License
