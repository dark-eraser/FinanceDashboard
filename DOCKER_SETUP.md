# Docker Setup Guide for FinanceTracker

This guide explains how to run FinanceTracker using Docker.

## Prerequisites

- **Docker**: [Install Docker Desktop](https://www.docker.com/products/docker-desktop/)
- **Docker Compose**: Usually included with Docker Desktop

## Data Isolation & Privacy ⚠️

**Important**: Each user gets their own isolated database instance:
- The SQLite database (`db.sqlite3`) is stored in a Docker volume, **not** in the Git repository
- Your uploaded bank statements and transaction data stay **only in your container**
- Other users running the same code get a **fresh, empty database** with no access to your data
- `.gitignore` ensures database files are never committed
- `.dockerignore` prevents database files from being included in Docker images

**👉 Read `DATA_ISOLATION.md` for detailed diagrams and security verification steps**

**Security note**: For production use with sensitive financial data, consider:
- Using PostgreSQL instead of SQLite for better security and multi-user support
- Running containers with additional security policies
- Encrypting volumes at rest

## Quick Start

### 1. Build and Run with Docker Compose (Recommended)

```bash
# From the project root directory
docker-compose up --build
```

The application will start and be available at: **http://localhost:8000/transactions/dashboard/**

The first run will automatically:
- Build the Docker image
- Install all Python dependencies
- Create your isolated database
- Run Django migrations
- Start the development server

### 2. Subsequent Runs

Once built, you can simply run:

```bash
docker-compose up
```

No need to rebuild unless you modify `requirements.txt` or the `Dockerfile`.

## Common Commands

### Start the Application

```bash
docker-compose up
```

### Start in Background

```bash
docker-compose up -d
```

### Stop the Application

```bash
docker-compose down
```

### View Logs

```bash
docker-compose logs -f web
```

### Access Django Shell

```bash
docker-compose exec web python manage.py shell
```

### Run Django Commands

```bash
docker-compose exec web python manage.py <command>
```

Example - create superuser:

```bash
docker-compose exec web python manage.py createsuperuser
```

### Re-run Migrations

```bash
docker-compose exec web python manage.py migrate
```

## Manual Docker Commands (Without Compose)

If you prefer to use Docker directly:

### Build the Image

```bash
docker build -t financetracker:latest .
```

### Run the Container

```bash
docker run -it \
  -p 8000:8000 \
  -v $(pwd):/app \
  --name financetracker \
  financetracker:latest
```

### Stop the Container

```bash
docker stop financetracker
```

### Remove the Container

```bash
docker rm financetracker
```

## Development Workflow

The `docker-compose.yml` mounts your local code as a volume, so:
- **Code changes are reflected immediately** - no need to rebuild
- **Database persists** in a Docker volume (`db_data`)
- **Interactive mode** allows you to see real-time output

### Upload CSV Files

1. Navigate to http://localhost:8000/transactions/dashboard/
2. Use the upload form to upload ZKB or Revolut bank statements
3. Transactions are processed and stored in the SQLite database

## Troubleshooting

### Port Already in Use

If port 8000 is already in use, modify `docker-compose.yml`:

```yaml
ports:
  - "8001:8000"  # Access on http://localhost:8001
```

### Database Issues

To reset the database:

```bash
docker-compose down -v  # Remove volumes
docker-compose up       # Fresh database
```

### View All Containers

```bash
docker ps -a
```

### View Container Logs

```bash
docker logs financetracker
```

## Production Deployment

**Note**: Current setup is for development. For production:

1. Set `DEBUG=False` in settings
2. Generate a secure `SECRET_KEY`
3. Set `ALLOWED_HOSTS` appropriately
4. Use a production database (PostgreSQL recommended)
5. Configure static/media file handling
6. Use a production WSGI server (Gunicorn, uWSGI)

See Django deployment documentation for details.

## Next Steps

- Visit http://localhost:8000/transactions/dashboard/ to upload bank statements
- Check logs with: `docker-compose logs -f web`
- Explore the Django admin at http://localhost:8000/admin (create a superuser first)

## Cleanup

To completely remove Docker artifacts:

```bash
docker-compose down -v              # Remove containers and volumes
docker rmi financetracker:latest    # Remove image
```
