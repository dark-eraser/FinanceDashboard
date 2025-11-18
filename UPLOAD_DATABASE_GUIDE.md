# File Upload & Database Issues - Complete Guide

## 🔧 What You Need to Know

### The Core Issue
The SQLite database (`db.sqlite3`) must persist between container restarts. This is already configured in `docker-compose.yml`, but there are a few things you should verify.

---

## ✅ Checklist: Ensure Database Persists

### 1. Verify Docker Volume Configuration

Your `docker-compose.yml` already has this configured:

```yaml
services:
  web:
    volumes:
      - .:/app                    # Live code changes
      - db_data:/app/faster       # Database persistence ← THIS IS KEY

volumes:
  db_data:                        # Named volume for persistence
```

**To verify it's working:**

```bash
# Check volume exists
docker volume ls | grep db_data

# Should output something like: financetracker_db_data
```

### 2. Run Health Check Script

```bash
chmod +x database-health-check.sh
./database-health-check.sh
```

This will:
- ✅ Verify migrations are applied
- ✅ Check database tables exist
- ✅ Count transactions
- ✅ Verify Docker volume is set up correctly

### 3. Important: DON'T Use `docker-compose down -v`

❌ **BAD** - Deletes data:
```bash
docker-compose down -v   # This removes the volume!
```

✅ **GOOD** - Keeps data:
```bash
docker-compose down      # Keeps volume
docker-compose up        # Data still there
```

---

## 📤 How to Upload Files Successfully

### Step 1: Start the Container

```bash
docker-compose up
```

Wait for output like:
```
financetracker  | Starting development server at http://0.0.0.0:8000/
```

### Step 2: Access Settings Page

Open: **http://localhost:8000/settings/**

### Step 3: Upload a File

1. Click "Select CSV File" button
2. Choose a CSV file with columns like:
   - `Date`, `Booking text`, `Category`, `Amount`, `Currency`
   - Or ZKB format: `Date;Booking text;Debit CHF;Credit CHF;...`
   - Or Revolut format: `Type,Description,Amount,Currency,...`

3. Click "Upload Statement" button

### Step 4: Verify Upload Worked

**Via Settings Page:**
- File should appear in the "Files" section below
- Transactions should appear in the table

**Via Terminal:**
```bash
docker-compose exec web python manage.py shell

# Count transactions
from transactions.models import Transaction
print(Transaction.objects.count())

# See uploaded files
from transactions.models import UploadedFile
for f in UploadedFile.objects.all():
    print(f.name, f.uploaded_at)

exit()
```

---

## 🧪 Test With Sample File

Use the included test script:

```bash
chmod +x test-upload.sh
./test-upload.sh
```

Then:
1. Open **http://localhost:8000/settings/**
2. Upload the test file: `data/test_transactions.csv`
3. Verify transactions appear

---

## 🔍 Troubleshooting

### Problem: "Database table doesn't exist" error

**Solution:**
```bash
docker-compose exec web python manage.py migrate --noinput
```

### Problem: File uploads but no transactions appear

**Check the logs:**
```bash
docker-compose logs web | grep -i "error\|exception"
```

**Manually run migrations:**
```bash
docker-compose exec web python manage.py migrate
```

### Problem: Data disappears after restarting container

**Check volume is configured** (see checklist above)

**Make sure you're NOT using** `-v` flag:
```bash
docker-compose down -v   # ❌ DON'T do this!
docker-compose down      # ✅ Do this instead
```

### Problem: "CSRF token missing" error

**Solution:**
1. Clear browser cache: `Ctrl+Shift+Delete` (or `Cmd+Shift+Delete` on Mac)
2. Refresh page
3. Try uploading again

### Problem: File appears in settings but transactions don't show up

**The transactions might not have categories yet.** They are still in the database but just uncategorized. Check via Django shell:

```bash
docker-compose exec web python manage.py shell
from transactions.models import Transaction
Transaction.objects.count()  # Should show your uploaded transactions
exit()
```

---

## 💾 Database Files Location

### Inside Container
```
/app/faster/db.sqlite3      # SQLite database file
```

### On Your Computer (macOS/Linux)
The actual file location is managed by Docker. To find it:

```bash
docker volume inspect financetracker_db_data
```

Look for the `Mountpoint` field.

### On Windows
Similar process, but Docker manages the path for you.

---

## 🚀 Recommended Workflow

### For Development

1. **Start container (first time):**
   ```bash
   docker-compose up
   ```

2. **Upload files:**
   - Go to http://localhost:8000/settings/
   - Upload CSV files

3. **Stop container (keeps data):**
   ```bash
   docker-compose down
   ```

4. **Start again (data is there):**
   ```bash
   docker-compose up
   ```

### To Reset Database (start fresh)

```bash
# Remove volume and recreate
docker-compose down -v
docker-compose up

# Now database is empty, ready for new uploads
```

---

## 📊 Verify Everything is Working

Run this comprehensive test:

```bash
# 1. Check container status
docker-compose ps

# 2. Run health check
./database-health-check.sh

# 3. Check logs for errors
docker-compose logs web | tail -20

# 4. Count transactions
docker-compose exec web python manage.py shell -c "
from transactions.models import Transaction, UploadedFile
print(f'Transactions: {Transaction.objects.count()}')
print(f'Files uploaded: {UploadedFile.objects.count()}')
"
```

---

## Still Having Issues?

1. **Check logs first:**
   ```bash
   docker-compose logs -f web
   ```

2. **Run health check:**
   ```bash
   ./database-health-check.sh
   ```

3. **Reset everything:**
   ```bash
   docker-compose down -v
   docker-compose up --build
   ```

4. **Check file permissions** (shouldn't be an issue but just in case):
   ```bash
   docker-compose exec web ls -la /app/faster/db.sqlite3
   ```

---

## Next Steps

- ✅ Verify database persistence with health check script
- ✅ Upload a test file
- ✅ Verify transactions appear
- ✅ Restart container and confirm data persists
- ✅ Check `DATABASE_TROUBLESHOOTING.md` for advanced debugging

Happy tracking! 📈
