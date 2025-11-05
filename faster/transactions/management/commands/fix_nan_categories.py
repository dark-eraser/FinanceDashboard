"""
Django management command to fix transactions with 'nan' categories and convert 'Uncounted' used as uncategorized.
"""
from django.core.management.base import BaseCommand
from transactions.models import Transaction


class Command(BaseCommand):
    help = 'Fix transactions with "nan" categories and convert incorrectly used "Uncounted" to "Uncategorized"'

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix-uncounted",
            action="store_true",
            help='Also convert "Uncounted" categories that were used as placeholders to "Uncategorized"',
        )

    def handle(self, *args, **options):
        self.stdout.write("Fixing transactions with problematic categories...")

        # Find transactions with "nan" category
        nan_transactions = Transaction.objects.filter(category="nan")
        nan_count = nan_transactions.count()

        if nan_count > 0:
            self.stdout.write(f'Found {nan_count} transactions with "nan" category')

            # Update them to have Uncategorized category
            nan_transactions.update(
                category="Uncategorized",
                category_confidence=0.0,
                predicted_category="",
                is_manually_categorized=False,
            )

            self.stdout.write(
                self.style.SUCCESS(f'Successfully fixed {nan_count} "nan" transactions')
            )
        else:
            self.stdout.write('No transactions with "nan" category found')

        # Optionally fix Uncounted categories that were used as placeholders
        if options["fix_uncounted"]:
            # Only fix Uncounted that have no confidence score (likely placeholders)
            uncounted_placeholders = Transaction.objects.filter(
                category="Uncounted", category_confidence__isnull=True
            )
            uncounted_count = uncounted_placeholders.count()

            if uncounted_count > 0:
                self.stdout.write(
                    f'Found {uncounted_count} "Uncounted" placeholder transactions'
                )

                uncounted_placeholders.update(
                    category="Uncategorized",
                    category_confidence=0.0,
                    is_manually_categorized=False,
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully converted {uncounted_count} "Uncounted" placeholders to "Uncategorized"'
                    )
                )
            else:
                self.stdout.write('No "Uncounted" placeholder transactions found')

        self.stdout.write(self.style.SUCCESS("Category cleanup complete!"))
