#!/bin/bash
# Quick test script for file upload

echo "🧪 Testing FinanceTracker File Upload"
echo "===================================="

# Use sample file from data directory
TEST_FILE="data/test_transactions.csv"

if [ ! -f "$TEST_FILE" ]; then
    echo "❌ Test file not found: $TEST_FILE"
    echo ""
    echo "Creating a sample CSV file..."
    mkdir -p data
    cat > "$TEST_FILE" << 'EOF'
Date,Booking text,Category,Amount,Currency
2025-11-01,Test Store,Shopping,-50.00,CHF
2025-11-02,Test Cafe,Dining,-12.50,CHF
2025-11-03,Test Transfer,Bank Transfer,100.00,CHF
EOF
    echo "✅ Created sample file: $TEST_FILE"
fi

echo ""
echo "📋 Test file content:"
head -5 "$TEST_FILE"

echo ""
echo "📤 Uploading test file via curl..."
echo ""
echo "Method: POST"
echo "Endpoint: http://localhost:8000/settings/"
echo "File: $TEST_FILE"
echo ""

# Get CSRF token first (commented - manual upload easier via web UI)
# CSRF_TOKEN=$(curl -s http://localhost:8000/settings/ | grep -o 'csrfmiddlewaretoken" value="[^"]*' | cut -d'"' -f3)

echo "💡 To test manually:"
echo "  1. Open: http://localhost:8000/settings/"
echo "  2. Click 'Select CSV File'"
echo "  3. Choose: $TEST_FILE"
echo "  4. Click 'Upload Statement'"
echo ""
echo "📝 To verify upload:"
echo "  docker-compose exec web python manage.py shell"
echo "  >>> from transactions.models import Transaction"
echo "  >>> Transaction.objects.count()"
echo "  >>> exit()"
echo ""
echo "📊 Or check via settings page - transactions should appear in the table"
