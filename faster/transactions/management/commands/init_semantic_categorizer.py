"""
Django management command to initialize the semantic categorizer with existing transaction data.
"""
import os
import sys

from django.conf import settings
from django.core.management.base import BaseCommand

# Add helpers to path
helpers_path = os.path.join(settings.BASE_DIR, "helpers")
if helpers_path not in sys.path:
    sys.path.append(helpers_path)

from semantic_categorizer import SemanticCategorizer
from transactions.models import Transaction


class Command(BaseCommand):
    help = "Initialize semantic categorizer with existing transaction data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--rebuild",
            action="store_true",
            help="Rebuild the categorizer from scratch (clears existing data)",
        )
        parser.add_argument(
            "--min-transactions",
            type=int,
            default=3,
            help="Minimum number of transactions required for a merchant to be included (default: 3)",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Initializing semantic categorizer..."))

        # Initialize categorizer
        data_dir = os.path.join(settings.BASE_DIR, "semantic_data")
        categorizer = SemanticCategorizer(data_dir=data_dir)

        if options["rebuild"]:
            self.stdout.write(
                self.style.WARNING("Rebuilding categorizer from scratch...")
            )
            # Clear existing data
            for file_path in [
                categorizer.merchants_file,
                categorizer.embeddings_file,
                categorizer.corrections_file,
            ]:
                if os.path.exists(file_path):
                    os.remove(file_path)
            # Reinitialize
            categorizer = SemanticCategorizer(data_dir=data_dir)

        # Get all transactions with categories (excluding 'Uncounted')
        transactions = Transaction.objects.exclude(
            category__in=["", "Uncounted"]
        ).exclude(category__isnull=True)

        self.stdout.write(f"Found {transactions.count()} categorized transactions")

        # Group transactions by merchant and category
        merchant_categories = {}
        merchant_counts = {}

        for transaction in transactions:
            merchant = transaction.booking_text.strip()
            category = transaction.category.strip()

            if not merchant or not category:
                continue

            # Count transactions per merchant
            merchant_counts[merchant] = merchant_counts.get(merchant, 0) + 1

            # Track category for each merchant (use most common)
            if merchant not in merchant_categories:
                merchant_categories[merchant] = {}
            merchant_categories[merchant][category] = (
                merchant_categories[merchant].get(category, 0) + 1
            )

        # Filter merchants with minimum transaction count
        min_transactions = options["min_transactions"]
        filtered_merchants = {
            merchant: categories
            for merchant, categories in merchant_categories.items()
            if merchant_counts[merchant] >= min_transactions
        }

        self.stdout.write(
            f"Found {len(filtered_merchants)} merchants with at least {min_transactions} transactions"
        )

        # Prepare data for bulk import
        import_data = []
        for merchant, categories in filtered_merchants.items():
            # Use the most common category for this merchant
            most_common_category = max(categories, key=categories.get)
            import_data.append({"merchant": merchant, "category": most_common_category})

        # Import into categorizer
        self.stdout.write("Importing merchant-category mappings...")
        categorizer.bulk_import_from_existing_data(import_data)

        # Display stats
        stats = categorizer.get_stats()
        self.stdout.write(
            self.style.SUCCESS(
                f"""
Semantic categorizer initialization complete!

Statistics:
- Total known merchants: {stats['total_known_merchants']}
- Total corrections: {stats['total_corrections']}
- Categories: {', '.join(stats['categories'])}
- Model loaded: {stats['model_loaded']}

Data saved to: {data_dir}
        """
            )
        )

        # Test prediction on a few uncategorized transactions
        uncategorized = Transaction.objects.filter(
            category__in=["", "Uncounted"]
        ).exclude(booking_text="")[:5]

        if uncategorized.exists():
            self.stdout.write("\nTesting predictions on uncategorized transactions:")
            for transaction in uncategorized:
                predicted_category, confidence = categorizer.predict_with_context(
                    merchant=transaction.booking_text,
                    amount=float(transaction.amount) if transaction.amount else None,
                    date_str=transaction.date,
                )

                if predicted_category:
                    self.stdout.write(
                        f"  {transaction.booking_text[:50]:50} → {predicted_category:15} (confidence: {confidence:.2f})"
                    )
                else:
                    self.stdout.write(
                        f"  {transaction.booking_text[:50]:50} → No prediction"
                    )
