# 🗄️ Database & Upload Quick Reference

## The Short Answer

**Yes, you need to do something:** Make sure you DON'T use `docker-compose down -v` because the `-v` flag deletes your database!

---

## Quick Commands

### ✅ CORRECT Ways to Use Docker

```bash
# Start container (first time)
docker-compose up

# Stop container (keeps data)
docker-compose down

# Restart container (data persists)
docker-compose restart

# Check database is working
./database-health-check.sh
```

### ❌ WRONG Ways

```bash
# DON'T DO THIS - deletes database!
docker-compose down -v
```

---

## Upload a File

1. **Start container:**
   ```bash
   docker-compose up
   ```

2. **Open browser:**
   - http://localhost:8000/settings/

3. **Upload CSV file:**
   - Click "Upload Statement" button
   - Select a `.csv` file
   - Click Upload

4. **Verify it worked:**
   ```bash
   ./database-health-check.sh
   # Should show: ✅ Total Transactions: [number]
   ```

---

## Verify Database Persistence

```bash
# Method 1: Run health check
chmod +x database-health-check.sh
./database-health-check.sh

# Method 2: Check via Django
docker-compose exec web python manage.py shell
from transactions.models import Transaction
print(Transaction.objects.count())
exit()
```

---

## Reset Database (Start Fresh)

Only do this if you want to delete ALL data:

```bash
docker-compose down -v    # -v removes the volume
docker-compose up         # Fresh empty database
```

---

## File Locations

- **Your uploads are stored:** In Docker named volume `financetracker_db_data`
- **Docker manages the exact location** - you don't need to worry about it
- **Data persists** as long as you use `docker-compose down` (NOT `down -v`)

---

## Still Not Working?

1. **Check logs:**
   ```bash
   docker-compose logs -f web
   ```

2. **Run health check:**
   ```bash
   ./database-health-check.sh
   ```

3. **Read detailed guides:**
   - `UPLOAD_DATABASE_GUIDE.md` - Complete guide
   - `DATABASE_TROUBLESHOOTING.md` - Advanced troubleshooting
   - `DOCKER_ADVANCED.md` - Docker setup details

---

## Key Points

🔑 **Remember:**
- ✅ `docker-compose down` = Safe, keeps data
- ❌ `docker-compose down -v` = Deletes data  
- ✅ Database is automatically managed in a Docker volume
- ✅ No need to manually backup the database
- ✅ Data persists across container restarts

You're all set! 🚀
