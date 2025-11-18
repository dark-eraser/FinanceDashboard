# Data Isolation Architecture

## Overview Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Git Repository                          │
│  (Shared Code - NO USER DATA)                              │
│  ├── FinanceTracker/                                        │
│  ├── requirements.txt                                       │
│  ├── Dockerfile                                             │
│  ├── docker-compose.yml                                     │
│  └── .gitignore ← Excludes db.sqlite3                      │
└─────────────────────────────────────────────────────────────┘
                          ↓
                    (git clone)
                          ↓
    ┌───────────────────────────────────────────┐
    │         User A's Local Machine            │
    │  (FinanceTracker/)                        │
    │  ├── Source code (shared)                 │
    │  └── .env (local only)                    │
    │                                           │
    │  docker-compose up                        │
    └───────────────────────────────────────────┘
                  ↓                    ↓
        ┌─────────────────┐   ┌─────────────────┐
        │  Docker Image   │   │  Docker Image   │
        │  (financetracker)   (financetracker)   │
        │  Same code      │   │  Same code      │
        └────────┬────────┘   └────────┬────────┘
                 │                     │
        ┌────────▼────────┐   ┌────────▼────────┐
        │  Container 1    │   │  Container 2    │
        │  (User A runs   │   │  (User B runs   │
        │   it first)     │   │   it separately)│
        └────────┬────────┘   └────────┬────────┘
                 │                     │
        ┌────────▼────────┐   ┌────────▼────────┐
        │ Docker Volume   │   │ Docker Volume   │
        │ financetracker  │   │ financetracker  │
        │ _db_data        │   │ _db_data_2      │
        │ ┌────────────┐  │   │ ┌────────────┐  │
        │ │ db.sqlite3 │  │   │ │ db.sqlite3 │  │
        │ │ (User A    │  │   │ │ (User B    │  │
        │ │  data)     │  │   │ │  data)     │  │
        │ └────────────┘  │   │ └────────────┘  │
        │ ISOLATED        │   │ ISOLATED        │
        │ NO ACCESS       │   │ NO ACCESS       │
        │ FROM USER B     │   │ FROM USER A     │
        └─────────────────┘   └─────────────────┘
```

## File Protection Chain

```
┌─────────────────────────────────────────────────────────┐
│ Protection Layer 1: .gitignore                          │
│ Prevents db.sqlite3 from being committed to Git         │
│ Result: Database NOT in Git repository                  │
└────────────┬────────────────────────────────────────────┘
             ↓
┌─────────────────────────────────────────────────────────┐
│ Protection Layer 2: .dockerignore                       │
│ Prevents db.sqlite3 from being copied into Docker image │
│ Result: Database NOT in Docker image                    │
└────────────┬────────────────────────────────────────────┘
             ↓
┌─────────────────────────────────────────────────────────┐
│ Protection Layer 3: Docker Volumes                      │
│ Each container gets its own isolated volume             │
│ Result: Database isolated per container instance        │
└────────────┬────────────────────────────────────────────┘
             ↓
┌─────────────────────────────────────────────────────────┐
│ Protection Layer 4: entrypoint.sh                       │
│ Fresh migrations run on each container start            │
│ Result: Clean, isolated database per run                │
└─────────────────────────────────────────────────────────┘
```

## Data Flow Scenarios

### Scenario 1: User A Uploads Bank Statement

```
User A's Machine
    ↓
docker-compose up
    ↓
Container 1 starts
    ↓
Volume financetracker_db_data created (fresh)
    ↓
User A uploads CSV
    ↓
Transactions stored in db.sqlite3
    ↓
Data ONLY in Container 1's volume
✓ User B cannot access this data
✓ User C cannot access this data
```

### Scenario 2: User B Clones and Runs

```
User B clones repo
    ↓
git clone (no db.sqlite3 - excluded by .gitignore)
    ↓
docker-compose up
    ↓
Container 2 starts
    ↓
Volume financetracker_db_data_2 created (fresh, empty)
    ↓
Migrations run (empty schema created)
    ↓
User B's container ready
✓ Fresh, empty database
✓ Zero access to User A's data
✓ Zero access to any other user's data
```

### Scenario 3: Someone Commits Database by Mistake

```
Accidental: git add db.sqlite3
    ↓
Git Pre-Commit Hook (from .gitignore)
    ↓
✗ Commit BLOCKED by Git
"db.sqlite3 is ignored in .gitignore"
```

Even if commit somehow succeeded:

```
docker build -f Dockerfile
    ↓
COPY . . (copies repo files)
    ↓
.dockerignore check
    ↓
*.sqlite3 - SKIP (not copied to image)
    ↓
Docker image created (without database)
    ↓
docker-compose up
    ↓
Fresh volume created
    ↓
✓ Data isolation maintained
```

## Volume Isolation Details

### User A's Setup

```bash
$ docker-compose up
Creating network...
Creating volume financetracker_db_data...
Starting web service...
```

Volume location: `/var/lib/docker/volumes/financetracker_db_data/_data/`

### User B's Setup (Same Machine)

```bash
$ docker-compose up
Creating network...
Creating volume financetracker_db_data... (Creates NEW volume, not User A's)
Starting web service...
```

Volume location: `/var/lib/docker/volumes/financetracker_db_data_2/_data/`

Or with named project:
```bash
$ docker-compose -p userb up
→ Volume: financetracker_userb_db_data
```

### Docker Compose Isolation

By default, Docker Compose creates isolated networks and volumes per directory:

```
/home/userA/FinanceTracker/
  └── docker-compose up
      └── Network: financetracker_default
      └── Volume: financetracker_db_data

/home/userB/FinanceTracker/
  └── docker-compose up
      └── Network: financetracker_default (DIFFERENT)
      └── Volume: financetracker_db_data (DIFFERENT)
```

## Security Verification

To verify data isolation on your machine:

```bash
# See volumes created
docker volume ls

# See volume details
docker volume inspect financetracker_db_data

# See what's inside
docker volume inspect financetracker_db_data --format='{{.Mountpoint}}'

# List volumes by size
docker volume ls --format='table {{.Name}}\t{{.Size}}'
```

## Best Practices

1. ✅ Always use `.gitignore` for sensitive files
2. ✅ Always use `.dockerignore` to prevent accidental data inclusion
3. ✅ Use Docker volumes for persistent data (not shared folders)
4. ✅ For production: Use environment-specific compose files
5. ✅ For production: Consider PostgreSQL for better access control
6. ⚠️ Never commit `.env` files with real secrets
7. ⚠️ Never bind volumes to shared directories

## Migration Path: SQLite to PostgreSQL

For production with multiple users, consider:

```yaml
# docker-compose.prod.yml
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: financetracker
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  web:
    depends_on:
      - db
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/financetracker

volumes:
  postgres_data:
```

This provides:
- Better security with user roles
- Easier backups
- Multi-user support
- Better performance at scale
```
