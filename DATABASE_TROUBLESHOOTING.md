# Database & File Upload Troubleshooting Guide

## Issue: File Upload Not Working or Database Not Persisting

### Quick Diagnosis

First, check the Docker logs to see what error is occurring:

```bash
docker-compose logs -f web
```

Look for error messages when you upload a file.

---

## Common Issues & Solutions

### 1. **Database Doesn't Persist After Container Restart**

**Problem**: You upload a file, but when you restart the container, the data is gone.

**Root Cause**: The SQLite database file needs to be stored in a Docker volume to persist data.

**Solution**: Ensure `docker-compose.yml` has volume mounts configured:

```yaml
services:
  web:
    volumes:
      - .:/app                    # Live code changes
      - db_data:/app/faster       # Database persistence
      
volumes:
  db_data:
```

**Verify it's working**:
```bash
docker volume ls | grep financetracker
```

**To reset the database and start fresh**:
```bash
docker-compose down -v    # Remove all volumes
docker-compose up         # Fresh database
```

---

### 2. **File Upload Returns Error**

**Problem**: When uploading a CSV file, you see an error message.

**Solution**: Check the Docker logs:

```bash
docker-compose logs -f web | grep -A 5 "Error"
```

Common errors:

#### Error: "Could not parse CSV file"
- **Cause**: CSV format not recognized
- **Fix**: Ensure your CSV uses `;` or `,` as separator
- **Test**: Try with sample files in `data/` or `config/` directories

#### Error: "CSRF token missing"
- **Cause**: Form doesn't have CSRF protection
- **Fix**: Ensure form has `{% csrf_token %}` (it should)
- **Clear browser cache**: `Ctrl+Shift+Delete` (or `Cmd+Shift+Delete`)

#### Error: Database table doesn't exist
- **Cause**: Migrations didn't run
- **Fix**: Manually run migrations:
  ```bash
  docker-compose exec web python manage.py migrate
  ```

---

### 3. **Database Tables Not Created**

**Problem**: Upload fails with "table not found" error.

**Solution**: 

```bash
# Check migration status
docker-compose exec web python manage.py showmigrations

# Run migrations manually
docker-compose exec web python manage.py migrate --noinput

# Verify tables exist
docker-compose exec web python manage.py dbshell
# Then run: .tables
# You should see: auth_*, transactions_*
```

---

### 4. **Volume Mount Issues (macOS/Windows)**

**Problem**: File uploads work but database doesn't persist on macOS/Windows.

**Solution**: Docker Desktop volume mounts can be slow on macOS/Windows. Use named volumes (already configured):

```yaml
volumes:
  db_data:  # Managed by Docker, faster than bind mounts
```

**Verify**:
```bash
# List volumes
docker volume inspect financetracker_db_data

# Should show mount point managed by Docker
```

---

## Step-by-Step: Upload a File Successfully

1. **Start the container**:
   ```bash
   docker-compose up
   ```

2. **Wait for migrations to complete**:
   ```
   financetracker | Applying transactions.0004_dashboardsettings... OK
   financetracker | Starting server...
   ```

3. **Access the app**:
   - Navigate to: http://localhost:8000/settings/

4. **Upload a CSV file**:
   - Use a file from `data/` or `config/` directory
   - Or use a sample ZKB/Revolut format CSV

5. **Check the logs**:
   ```bash
   docker-compose logs -f web
   ```
   Should show: `"POST /settings/ HTTP/1.1" 200`

6. **Verify data persists**:
   ```bash
   docker-compose exec web python manage.py shell
   >>> from transactions.models import Transaction
   >>> Transaction.objects.count()  # Should show your uploaded transactions
   >>> exit()
   ```

---

## Debug: Check Database Content

```bash
# Open Django shell
docker-compose exec web python manage.py shell

# Check tables
>>> from transactions.models import Transaction, UploadedFile
>>> UploadedFile.objects.all()  # See all uploaded files
>>> Transaction.objects.count()  # Count transactions
>>> Transaction.objects.first().__dict__  # See first transaction

# Exit
>>> exit()
```

---

## Force Database Persistence

To ensure data persists even after container recreation:

```bash
# Don't use -v flag (which removes volumes)
docker-compose down      # Safe - keeps volumes
docker-compose up        # Data still there

# Only use -v when you want to reset
docker-compose down -v   # Remove volumes and data
```

---

## Production-Ready Setup

For persistent data in production, use PostgreSQL instead of SQLite:

See `DOCKER_ADVANCED.md` for PostgreSQL setup instructions.

---

## Still Having Issues?

1. **Check all logs**:
   ```bash
   docker-compose logs web  # All output
   docker-compose logs web -f  # Follow in real-time
   ```

2. **Verify migrations ran**:
   ```bash
   docker-compose exec web python manage.py showmigrations transactions
   ```

3. **Test file upload with detailed error**:
   ```bash
   docker-compose exec web python manage.py shell
   # Test CSV parsing manually
   ```

4. **Clear everything and start fresh**:
   ```bash
   docker-compose down -v
   docker-compose up --build
   ```
