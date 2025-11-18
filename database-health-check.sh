#!/bin/bash
# Database Health Check & Repair Script

set -e

echo "🏥 FinanceTracker Database Health Check"
echo "======================================"

# Check if containers are running
echo ""
echo "📦 Checking if containers are running..."
if ! docker-compose ps | grep -q "financetracker"; then
    echo "❌ Container not running. Starting..."
    docker-compose up -d
    sleep 5
fi

echo "✅ Container is running"

# Run migrations
echo ""
echo "📊 Running database migrations..."
docker-compose exec web python manage.py migrate --noinput

# Check migration status
echo ""
echo "📋 Migration status:"
docker-compose exec web python manage.py showmigrations transactions

# Check if tables exist
echo ""
echo "🔍 Checking database tables..."
docker-compose exec web python manage.py dbshell < /dev/null << EOF
.tables
EOF

# Count transactions
echo ""
echo "📈 Transaction count:"
docker-compose exec web python manage.py shell << EOF
from transactions.models import Transaction, UploadedFile

total = Transaction.objects.count()
files = UploadedFile.objects.count()

print(f"✅ Total Transactions: {total}")
print(f"✅ Uploaded Files: {files}")

if total > 0:
    print(f"✅ Database contains data")
else:
    print(f"⚠️  Database is empty - upload a file to add data")

EOF

# Check volume
echo ""
echo "💾 Checking Docker volumes..."
if docker volume ls | grep -q "financetracker_db_data"; then
    echo "✅ Database volume exists: financetracker_db_data"
    
    # Show volume details
    echo ""
    echo "Volume details:"
    docker volume inspect financetracker_db_data | grep -E '"Mountpoint"|"Driver"'
else
    echo "⚠️  Database volume not found!"
fi

echo ""
echo "✅ Health check complete!"
echo ""
echo "Next steps:"
echo "  - Visit: http://localhost:8000/settings/"
echo "  - Upload a CSV file to test"
echo "  - Use: ./database-health-check.sh (this script) to verify again"
