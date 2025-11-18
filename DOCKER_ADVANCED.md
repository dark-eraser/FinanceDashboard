# Docker & Container Guide

This guide covers how to use Docker with FinanceTracker for both development and production environments.

## 🔒 Data Isolation & Privacy

### How Data is Protected

Each instance of FinanceTracker runs in **complete isolation**:

| Component | Storage Location | Who Has Access |
|-----------|-----------------|-----------------|
| Database (`db.sqlite3`) | Docker volume | Only the container that created it |
| Uploaded CSVs | Database | Only stored in your container's database |
| Transaction data | Database | Only accessible within your container |
| Source code | Git repository | Everyone (no data included) |
| Environment vars | `.env` file (local) | Only your local machine |

### Why Your Data is Safe

1. **Database in Docker Volume**: The SQLite database is stored in a Docker volume, not in the Git repository
   - Each user gets a fresh, empty volume when they first run the container
   - Volumes are isolated per container instance
   - No database file in the Git repo = no data shared

2. **`.gitignore` Protection**: Database files are in `.gitignore`
   ```
   db.sqlite3
   db.sqlite3-journal
   ```
   - If someone accidentally commits, Git prevents it
   - The repository only contains code, no user data

3. **`.dockerignore` Protection**: Database files excluded from Docker builds
   ```
   *.sqlite3
   *.sqlite3-journal
   ```
   - Even if a DB file existed locally, it won't be copied into the Docker image
   - Prevents accidental data leakage

4. **Separate Volumes**: Each running container has its own isolated volume
   - Running the container twice creates two separate databases
   - No data mixing between instances

### Example Scenario

```bash
# User A runs the app
docker-compose up

# Their data is in: financetracker_db_data (volume)
# User B clones the repo and runs:
docker-compose up

# User B gets a FRESH database - no access to User A's data
```

### For Production Use

If you're handling sensitive financial data, add these protections:

```yaml
# docker-compose.prod.yml
volumes:
  db_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /secure/path/to/data  # Encrypted volume
```

Or consider using PostgreSQL with proper access controls.

## Files Included

- **`Dockerfile`**: Development image with live code reloading
- **`Dockerfile.prod`**: Production image with Gunicorn and optimizations
- **`docker-compose.yml`**: Development orchestration with volume mounts
- **`docker-compose.prod.yml`**: Production orchestration (for reference)
- **`entrypoint.sh`**: Container startup script
- **`.dockerignore`**: Exclude unnecessary files from Docker build
- **`.env.example`**: Environment variables template

## Development Setup

### Prerequisites

- Docker Desktop installed and running
- No need to install Python, Django, or dependencies locally

### Quick Start

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd FinanceTracker
   ```

2. **Create environment file (optional for development):**
   ```bash
   cp .env.example .env
   ```

3. **Build and start the application:**
   ```bash
   docker-compose up --build
   ```

4. **Access the application:**
   - Dashboard: http://localhost:8000/transactions/dashboard/
   - Django Admin: http://localhost:8000/admin

5. **Stop the application:**
   ```bash
   docker-compose down
   ```

### Development Commands

#### Run Django management commands:
```bash
# Create a superuser
docker-compose exec web python manage.py createsuperuser

# Run migrations
docker-compose exec web python manage.py migrate

# Access Django shell
docker-compose exec web python manage.py shell

# Collect static files (optional)
docker-compose exec web python manage.py collectstatic --noinput
```

#### View logs:
```bash
# All services
docker-compose logs -f

# Only web service
docker-compose logs -f web
```

#### Restart the application:
```bash
docker-compose restart
```

#### Reset database (start fresh):
```bash
docker-compose down -v  # Remove volumes
docker-compose up       # Fresh database
```

### Development Workflow

- **Code changes are live**: The `docker-compose.yml` mounts your project directory as a volume, so changes are reflected immediately without rebuilding
- **Database persistence**: The SQLite database persists in a Docker volume
- **Interactive mode**: Terminal stays attached for easy logging and debugging

## Production Deployment

For production environments, use the optimized Dockerfile with Gunicorn.

### Build Production Image

```bash
docker build -f Dockerfile.prod -t financetracker:latest .
```

### Create Production Compose File

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  web:
    image: financetracker:latest
    container_name: financetracker
    ports:
      - "8000:8000"
    environment:
      - DEBUG=False
      - DJANGO_SETTINGS_MODULE=dashboard.settings
      - SECRET_KEY=${SECRET_KEY}
      - ALLOWED_HOSTS=${ALLOWED_HOSTS}
    volumes:
      - db_data:/app/faster
      - static_data:/app/faster/staticfiles
    restart: always

volumes:
  db_data:
  static_data:
```

### Environment Variables for Production

Create `.env.prod`:

```bash
DEBUG=False
SECRET_KEY=your-super-secret-key-generate-new-one
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

Generate a secure secret key:
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### Deploy Production Container

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Issue: Port 8000 already in use

**Solution**: Change the port in `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"  # Now access on http://localhost:8001
```

### Issue: Database migration errors

**Solution**: Check if migrations are up to date:
```bash
docker-compose exec web python manage.py migrate --check
```

### Issue: Can't upload CSV files

**Solution**: Ensure the volume is mounted correctly:
```bash
docker-compose exec web ls -la /app/faster
```

### Issue: Static files not loading

**Solution**: Collect static files:
```bash
docker-compose exec web python manage.py collectstatic --noinput
```

### Issue: Can't access from another machine

**Solution**: Update `ALLOWED_HOSTS` in `.env`:
```bash
ALLOWED_HOSTS=localhost,127.0.0.1,your-machine-ip
```

### View container logs for debugging

```bash
docker-compose logs -f web
```

## Docker Networking

### Access other services from the container

When using `docker-compose`, containers can reference each other by service name:
- Web service: `web`
- Database: `db` (if added to compose file)

### Expose the application to other machines

Update `docker-compose.yml` port mapping:
```yaml
ports:
  - "0.0.0.0:8000:8000"  # Accessible on all network interfaces
```

## Performance Tips

1. **Use `.dockerignore`**: Already configured to exclude unnecessary files
2. **Multi-stage builds**: `Dockerfile.prod` uses multi-stage builds for smaller images
3. **Layer caching**: Dependencies in separate layer for faster rebuilds
4. **Minimize base image**: Using `python:3.13-slim` instead of full Python image

## Advanced: Custom Docker Network

For more complex setups with multiple services:

```bash
docker network create financetracker-network
docker run --network financetracker-network --name web financetracker:latest
docker run --network financetracker-network --name db postgres:latest
```

## Cleanup

### Remove containers and images:
```bash
# Stop and remove containers
docker-compose down

# Remove volumes
docker-compose down -v

# Remove image
docker rmi financetracker:latest

# Clean up all Docker resources
docker system prune -a
```

## Next Steps

1. Check `DOCKER_SETUP.md` for detailed quick start guide
2. Review `.env.example` for available configuration options
3. Explore the [Django documentation](https://docs.djangoproject.com/) for further customization
4. Consider adding PostgreSQL for production use
