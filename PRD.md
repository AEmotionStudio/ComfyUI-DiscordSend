# Product Requirements Document: ComfyUI-DiscordSend Companion Bot

## Overview

A Discord bot that enables users to trigger ComfyUI image generations, manage queues, save prompt templates, and browse generation history—all from within Discord.

**Project**: `comfyui-discordsend-bot`
**Parent Extension**: `comfyui-discordsend` (v1.1.0)
**License**: GPL-3.0 (matching parent)
**Repository**: Same repo (`bot/` folder)

---

## Problem Statement

Currently, users must:
1. Open ComfyUI's web interface to queue generations
2. Wait for completion with no mobile-friendly status updates
3. Manually manage prompts across sessions
4. Rely on webhooks for one-way delivery (no interaction)

The companion bot solves these by bringing full generation control into Discord.

---

## Target Users

| User Type | Use Case |
|-----------|----------|
| **Individual Creators** | Run personal ComfyUI instance, trigger generations from phone/Discord |
| **Community Servers** | Shared ComfyUI where multiple users queue generations |

---

## MVP Features

### 1. Generation Triggers (`/generate`)

```
/generate prompt:"cyberpunk cityscape" [negative:"blurry"] [template:my-style]
          [steps:30] [cfg:7.5] [seed:12345] [delivery:dm]
```

- Submit generation requests directly from Discord
- Support positive/negative prompts
- Optional parameter overrides (steps, CFG, seed, dimensions)
- Load from saved templates
- Choose delivery: channel or DM

### 2. Queue Management (`/queue`)

```
/queue view          # See current queue with positions
/queue status 42     # Detailed status of job #42
/queue cancel 42     # Cancel your job (or any with admin)
/queue clear         # Clear your pending jobs
```

- Real-time queue position updates
- Progress bars during generation
- Cancel pending/running jobs
- Per-user queue limits (configurable)

### 3. Prompt Templates (`/template`)

```
/template save name:"portrait-style" prompt:"cinematic lighting, 8k"
/template list
/template load name:"portrait-style"
/template delete name:"portrait-style"
```

- Save reusable prompt presets
- Private templates (user-only)
- Shared templates (server-wide, optional)
- Include negative prompts and parameters

### 4. Generation History (`/history`)

```
/history list [limit:10]
/history view 42
/history rerun 42 [delivery:dm]
```

- Browse past generations
- View prompts and parameters used
- Re-run with same or modified settings
- Filter by status (completed, failed)

### 5. DM Delivery

- Send completed images directly to user's DMs
- Per-request flag: `delivery:dm` or `delivery:channel`
- User preference for default delivery method

---

## Permission System

Role-based access control using Discord server roles:

| Level | Capabilities |
|-------|-------------|
| **user** | View queue, view own history |
| **generator** | Generate, templates, cancel own jobs |
| **admin** | All + manage roles, cancel any job, configure bot |

Configuration via `/admin setroles generator:@Role admin:@Role`

---

## Technical Architecture

### Integration Model

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Discord Users  │────►│  Companion Bot  │────►│    ComfyUI      │
│  (slash cmds)   │◄────│  (discord.py)   │◄────│  (localhost)    │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                        ┌────────▼────────┐
                        │     SQLite      │
                        │  (jobs, users,  │
                        │   templates)    │
                        └─────────────────┘
```

### Deployment Model

- **Same machine** as ComfyUI (localhost API)
- Shares Python environment with ComfyUI
- Reuses existing `utils/` modules from comfyui-discordsend

### ComfyUI Integration

| Method | Purpose |
|--------|---------|
| REST API | Submit workflows, get history, fetch images |
| WebSocket | Real-time progress updates, completion events |

Key endpoints: `/prompt`, `/queue`, `/history`, `/view`, `/interrupt`

### Data Storage (SQLite)

| Table | Purpose |
|-------|---------|
| `users` | Discord user preferences |
| `servers` | Guild configuration |
| `server_roles` | Permission mappings |
| `templates` | Saved prompt presets |
| `jobs` | Generation history and queue |
| `workflows` | Default workflow storage |

---

## Project Structure

```
comfyui-discordsend/
├── utils/                    # Existing shared utilities (reuse)
├── bot/                      # NEW: Discord bot package
│   ├── __main__.py           # Entry point
│   ├── bot.py                # Main bot class
│   ├── config.py             # Configuration
│   ├── database/
│   │   ├── models.py         # SQLAlchemy models
│   │   └── repository.py     # Data access
│   ├── comfyui/
│   │   ├── client.py         # REST client
│   │   └── websocket.py      # WebSocket client
│   ├── cogs/
│   │   ├── generate.py       # /generate
│   │   ├── queue.py          # /queue
│   │   ├── templates.py      # /template
│   │   ├── history.py        # /history
│   │   └── admin.py          # /admin
│   ├── services/
│   │   ├── job_manager.py    # Job lifecycle
│   │   ├── delivery.py       # Result delivery
│   │   └── permissions.py    # RBAC
│   └── embeds/
│       └── builders.py       # Discord embeds
└── requirements.txt          # Bot dependencies
```

---

## Code Sharing Strategy

Reuse from existing `utils/`:

| Module | Bot Usage |
|--------|-----------|
| `sanitizer.py` | Sanitize workflows before storage/display |
| `prompt_extractor.py` | Extract prompts for history/template views |
| `discord_api.py` | Retry patterns, rate limit handling |
| `logging_config.py` | Consistent logging |

New shared utility:
- `utils/workflow_builder.py` - Modify workflow JSON (set prompts, seed, steps, etc.)

---

## Dependencies

```
# Bot-specific
discord.py>=2.3.0
aiohttp>=3.9.0
sqlalchemy>=2.0.0
aiosqlite>=0.19.0
pydantic>=2.0.0
pyyaml>=6.0.0

# Shared with extension
requests>=2.25.0
```

---

## Configuration

Environment variables (`.env`):
```
DISCORDBOT_DISCORD_TOKEN=your_bot_token
DISCORDBOT_COMFYUI_URL=http://127.0.0.1:8188
```

Bot config (`bot/config.yaml`):
```yaml
defaults:
  max_queue_per_user: 3
  progress_update_interval: 2.0
  workflow_path: workflows/default.json
```

---

## User Experience Flow

### Generation Flow

1. User runs `/generate prompt:"a robot"`
2. Bot validates permissions, checks queue limits
3. Bot submits workflow to ComfyUI
4. Bot posts "Queued" embed with position
5. WebSocket updates trigger progress bar edits
6. On completion, bot fetches images from ComfyUI
7. Bot delivers images to channel or DM (user's choice)

### Error Handling

| Scenario | Response |
|----------|----------|
| Permission denied | Ephemeral message explaining required role |
| Queue full | Ephemeral message with current limit |
| ComfyUI offline | Ephemeral message suggesting to check server |
| Generation failed | Update embed with error, log details |

---

## Implementation Phases

### Phase 1: Foundation
- Project structure and configuration
- Database schema and migrations
- ComfyUI REST client
- Basic bot lifecycle

### Phase 2: Core Generation
- `/generate` command
- WebSocket integration for progress
- Job manager and tracking
- Result delivery (channel/DM)

### Phase 3: Queue & Permissions
- `/queue` commands
- Role-based permission system
- `/admin` configuration commands
- Per-user queue limits

### Phase 4: Templates & History
- `/template` CRUD commands
- `/history` browsing and re-run
- Autocomplete for template names

### Phase 5: Polish
- Comprehensive error handling
- Progress embeds with previews
- Unit and integration tests
- Documentation and README

---

## Verification Plan

1. **Unit Tests**: Config, permissions, workflow builder
2. **Integration Tests**: Database ops, ComfyUI client (mocked)
3. **Manual E2E Testing**:
   - Generate image via `/generate`
   - Verify progress updates in Discord
   - Confirm delivery to channel and DM
   - Test queue cancellation
   - Test template save/load cycle
   - Test history re-run

---

## Files to Create

| File | Purpose |
|------|---------|
| `bot/__init__.py` | Package init with path setup |
| `bot/__main__.py` | Entry point (`python -m bot`) |
| `bot/bot.py` | Main bot class |
| `bot/config.py` | Configuration management |
| `bot/database/models.py` | SQLAlchemy models |
| `bot/database/repository.py` | Data access layer |
| `bot/comfyui/client.py` | REST API client |
| `bot/comfyui/websocket.py` | WebSocket client |
| `bot/cogs/generate.py` | /generate command |
| `bot/cogs/queue.py` | /queue commands |
| `bot/cogs/templates.py` | /template commands |
| `bot/cogs/history.py` | /history commands |
| `bot/cogs/admin.py` | /admin commands |
| `bot/services/job_manager.py` | Job lifecycle management |
| `bot/services/delivery.py` | Result delivery |
| `bot/services/permissions.py` | RBAC |
| `bot/embeds/builders.py` | Discord embed builders |
| `utils/workflow_builder.py` | Shared workflow manipulation |

---

## Database Schema

```sql
-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT UNIQUE NOT NULL,
    username TEXT NOT NULL,
    default_delivery TEXT DEFAULT 'channel',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Servers (guilds) table
CREATE TABLE servers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    default_channel_id TEXT,
    max_queue_per_user INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Server roles for permissions
CREATE TABLE server_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id INTEGER NOT NULL,
    role_discord_id TEXT NOT NULL,
    permission_level TEXT NOT NULL,
    FOREIGN KEY (server_id) REFERENCES servers(id)
);

-- Templates (user prompt presets)
CREATE TABLE templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    server_id INTEGER,
    name TEXT NOT NULL,
    positive_prompt TEXT NOT NULL,
    negative_prompt TEXT DEFAULT '',
    parameters TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Jobs (generation history)
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    server_id INTEGER,
    channel_id TEXT,
    status TEXT DEFAULT 'pending',
    positive_prompt TEXT,
    negative_prompt TEXT,
    parameters TEXT,
    output_images TEXT,
    error_message TEXT,
    delivery_type TEXT,
    message_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## Success Metrics

- Users can generate images without opening ComfyUI web UI
- Queue visibility reduces "is it working?" uncertainty
- Templates reduce repetitive prompt typing
- History enables easy iteration on generations
- DM delivery provides private results in shared servers
