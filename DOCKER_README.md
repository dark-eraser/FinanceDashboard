# Docker Documentation Quick Reference

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| **`DOCKER_SETUP.md`** | 👉 **START HERE** - Quick start guide |
| **`DOCKER_SECURITY.md`** | Quick answer about data isolation |
| **`DATA_ISOLATION.md`** | Detailed architecture & diagrams |
| **`DOCKER_SECURITY_CHECKLIST.md`** | Verification & testing procedures |
| **`DOCKER_ADVANCED.md`** | Advanced config & production setup |
| **`docker-helper.sh`** | Bash script for common commands |

## 🚀 Getting Started in 3 Steps

```bash
# 1. Clone the repository
git clone <repository-url>
cd FinanceTracker

# 2. Start with Docker
docker-compose up --build

# 3. Open in browser
# http://localhost:8000/transactions/dashboard/
```

**That's it!** ✅

## 🔒 Your Data is Completely Isolated

**Each user gets their own database:**
- Your transactions are in YOUR container's volume
- Other users can't access your data
- Other users get a fresh, empty database
- Source code is shared, data is not

See `DOCKER_SECURITY.md` for detailed explanation.

## 📋 Common Commands

### Start / Stop
```bash
docker-compose up              # Start
docker-compose up -d           # Start in background
docker-compose down            # Stop
docker-compose restart         # Restart
```

### Development
```bash
docker-compose logs -f         # View logs
docker-compose exec web bash   # Terminal access
docker-compose exec web python manage.py shell  # Django shell
```

### Database Management
```bash
docker-compose exec web python manage.py migrate  # Run migrations
docker-compose exec web python manage.py createsuperuser  # Add admin
docker-compose down -v         # Reset database
```

### Cleanup
```bash
docker-compose down            # Stop containers
docker-compose down -v         # Remove containers & volumes
docker system prune            # Clean up all Docker resources
```

## 🎯 Using the Helper Script

```bash
chmod +x docker-helper.sh

./docker-helper.sh up              # Build and start
./docker-helper.sh logs            # View logs
./docker-helper.sh shell           # Django shell
./docker-helper.sh migrate         # Run migrations
./docker-helper.sh createsuperuser # Create admin user
./docker-helper.sh down            # Stop
./docker-helper.sh cleanup         # Full cleanup
```

## ⚙️ Configuration

### Environment Variables

Create `.env` from `.env.example`:
```bash
cp .env.example .env
```

Edit `.env` to customize:
```
DEBUG=True
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1
```

### Port Conflicts

If port 8000 is taken, edit `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"  # Use 8001 instead
```

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Port 8000 already in use | Change port in `docker-compose.yml` |
| Database errors | Run `docker-compose down -v && docker-compose up` |
| Can't upload files | Check `docker-compose logs -f` for errors |
| Container won't start | Run `docker-compose up --build` to rebuild |
| Docker not found | Install Docker Desktop from https://docker.com |

## 🔍 Verification

### Check data isolation:
```bash
docker volume ls
docker volume inspect financetracker_db_data
```

### Verify no sensitive data in repo:
```bash
git ls-files | grep -E "(sqlite3|\.env|creds)"
# Should show: Nothing
```

### Test from clean clone:
```bash
cd /tmp
git clone <your-repo> test-clone
cd test-clone
docker-compose up
# Should work with empty database
```

## 📖 Need More Help?

| Question | Read This |
|----------|-----------|
| How do I start? | `DOCKER_SETUP.md` |
| Is my data secure? | `DOCKER_SECURITY.md` |
| Show me the architecture | `DATA_ISOLATION.md` |
| How do I verify security? | `DOCKER_SECURITY_CHECKLIST.md` |
| Production deployment? | `DOCKER_ADVANCED.md` |
| Advanced configuration? | `DOCKER_ADVANCED.md` |

## 🎓 Learn More

- **Docker Basics**: https://docs.docker.com/get-started/
- **Docker Compose**: https://docs.docker.com/compose/
- **Django Deployment**: https://docs.djangoproject.com/en/5.2/howto/deployment/
- **Docker Volumes**: https://docs.docker.com/storage/volumes/

## 🚢 Production Deployment

Ready for production? See `DOCKER_ADVANCED.md` for:
- Using Dockerfile.prod with Gunicorn
- PostgreSQL setup for multi-user environments
- Environment-specific configurations
- Health checks and auto-restart
- Security best practices

---

## ✅ Quick Checklist

- [x] Docker installed? (https://docker.com/products/docker-desktop)
- [x] Repository cloned?
- [x] `.env` file created? (`cp .env.example .env`)
- [x] Ready to run?

**You're all set! Run:**
```bash
docker-compose up --build
```

**Then visit:** http://localhost:8000/transactions/dashboard/

---

**Questions?** Check the relevant documentation file above or refer to the GitHub repo issues.
