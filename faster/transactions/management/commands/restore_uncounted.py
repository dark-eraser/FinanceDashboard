"""
Django management command to restore legitimate "Uncounted" transactions.
"""
from django.core.management.base import BaseCommand
from transactions.models import Transaction


class Command(BaseCommand):
    help = 'Restore transactions that should be "Uncounted" back from "Uncategorized"'

    def handle(self, *args, **options):
        self.stdout.write('Restoring legitimate "Uncounted" transactions...')

        # Keywords that typically indicate "Uncounted" transactions (internal transfers, exchanges, etc.)
        uncounted_keywords = [
            "exchange",
            "exchanged",
            "payment from",
            "payment to",
            "account transfer",
            "transfer to",
            "transfer from",
            "debit account transfer",
            "credit account transfer",
            "revolut ltd",
            "revolut account",
            "currency exchange",
            "internal transfer",
            "vault",  # Your vault transactions
        ]

        # Find "Uncategorized" transactions that should be "Uncounted"
        uncategorized = Transaction.objects.filter(category="Uncategorized")

        restored_count = 0

        for transaction in uncategorized:
            booking_text = transaction.booking_text.lower()

            # Check if this transaction matches "Uncounted" patterns
            should_be_uncounted = False

            for keyword in uncounted_keywords:
                if keyword in booking_text:
                    should_be_uncounted = True
                    break

            # Additional checks for specific patterns
            if (
                "david colonna" in booking_text
                or "exchanged to" in booking_text
                or "payment from" in booking_text
            ):
                should_be_uncounted = True

            if should_be_uncounted:
                transaction.category = "Uncounted"
                transaction.category_confidence = None
                transaction.predicted_category = ""
                transaction.is_manually_categorized = False
                transaction.save()
                restored_count += 1

                self.stdout.write(f"  Restored: {transaction.booking_text[:60]}")

        self.stdout.write(
            self.style.SUCCESS(f'Restored {restored_count} transactions to "Uncounted"')
        )

        # Show remaining counts
        uncounted = Transaction.objects.filter(category="Uncounted").count()
        uncategorized = Transaction.objects.filter(category="Uncategorized").count()

        self.stdout.write(f"Final counts:")
        self.stdout.write(f"  Uncounted: {uncounted}")
        self.stdout.write(f"  Uncategorized: {uncategorized}")
