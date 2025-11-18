"""
Django service for integrating semantic categorization with transaction processing.
"""
import os
import sys
from typing import Dict, List, Optional, Tuple

from django.conf import settings

# Add helpers to path
helpers_path = os.path.join(settings.BASE_DIR, "helpers")
if helpers_path not in sys.path:
    sys.path.append(helpers_path)

from semantic_categorizer import SemanticCategorizer

from .models import Transaction


class TransactionCategorizationService:
    """
    Service class for handling transaction categorization using semantic search.
    """

    def __init__(self):
        data_dir = os.path.join(settings.BASE_DIR, "semantic_data")
        self.categorizer = SemanticCategorizer(data_dir=data_dir)

    def categorize_transaction(
        self, transaction: Transaction, save: bool = True
    ) -> Tuple[str, float]:
        """
        Categorize a single transaction using semantic categorization.

        Args:
            transaction: Transaction object to categorize
            save: Whether to save the transaction after categorization

        Returns:
            Tuple of (predicted_category, confidence_score)
        """
        # Skip if already manually categorized
        if transaction.is_manually_categorized:
            return transaction.category, transaction.category_confidence or 1.0

        # Use existing category if it exists and has high confidence
        # But treat 'nan' and 'Uncategorized' as needing categorization since they're placeholders
        if (
            transaction.category
            and transaction.category not in ["Uncategorized", "nan", ""]
            and transaction.category_confidence
            and transaction.category_confidence > 0.8
        ):
            return transaction.category, transaction.category_confidence

        # Predict category using semantic categorizer
        predicted_category, confidence = self.categorizer.predict_with_context(
            merchant=transaction.booking_text,
            amount=float(transaction.amount) if transaction.amount else None,
            date_str=transaction.date,
        )

        if predicted_category:
            transaction.category = predicted_category
            transaction.category_confidence = confidence
            transaction.predicted_category = predicted_category

            if save:
                transaction.save()

            return predicted_category, confidence
        else:
            # No prediction available, use 'Uncategorized'
            if not transaction.category:
                transaction.category = "Uncategorized"
                transaction.category_confidence = 0.0

                if save:
                    transaction.save()

            return transaction.category, 0.0

    def categorize_transactions_bulk(self, transactions: List[Transaction]) -> Dict:
        """
        Categorize multiple transactions in bulk.

        Args:
            transactions: List of Transaction objects to categorize

        Returns:
            Dict with categorization statistics
        """
        stats = {
            "total": len(transactions),
            "total_processed": len(transactions),
            "categorized": 0,
            "high_confidence": 0,
            "medium_confidence": 0,
            "low_confidence": 0,
            "uncategorized": 0,
        }

        transactions_to_update = []

        for transaction in transactions:
            predicted_category, confidence = self.categorize_transaction(
                transaction, save=False
            )

            if predicted_category and predicted_category != "Uncounted":
                stats["categorized"] += 1

                if confidence >= 0.8:
                    stats["high_confidence"] += 1
                elif confidence >= 0.6:
                    stats["medium_confidence"] += 1
                else:
                    stats["low_confidence"] += 1
            else:
                stats["uncategorized"] += 1

            transactions_to_update.append(transaction)

        # Bulk update transactions
        Transaction.objects.bulk_update(
            transactions_to_update,
            ["category", "category_confidence", "predicted_category"],
        )

        return stats

    def record_manual_categorization(
        self, transaction_id: int, new_category: str
    ) -> bool:
        """
        Record when a user manually updates a transaction's category.
        Also auto-applies the category to all transactions with the same merchant (booking_text).

        Args:
            transaction_id: ID of the transaction being updated
            new_category: New category assigned by user

        Returns:
            True if correction was recorded successfully
        """
        try:
            transaction = Transaction.objects.get(id=transaction_id)
            merchant_text = transaction.booking_text

            # Record correction if we had a previous prediction
            if (
                transaction.predicted_category
                and transaction.predicted_category != new_category
            ):
                self.categorizer.record_correction(
                    merchant=transaction.booking_text,
                    predicted_category=transaction.predicted_category,
                    actual_category=new_category,
                    confidence=transaction.category_confidence,
                )

            # Update this transaction
            transaction.category = new_category
            transaction.is_manually_categorized = True
            transaction.category_confidence = (
                1.0  # Manual categorization has full confidence
            )
            transaction.save()

            # Auto-apply to all transactions with the same merchant (booking_text)
            # but only if they aren't already manually categorized
            if merchant_text:
                same_merchant_transactions = Transaction.objects.filter(
                    booking_text=merchant_text, is_manually_categorized=False
                ).exclude(id=transaction_id)

                count = 0
                for t in same_merchant_transactions:
                    t.category = new_category
                    t.is_manually_categorized = True
                    t.category_confidence = 1.0
                    t.save()
                    count += 1

                if count > 0:
                    print(
                        f"Auto-applied category '{new_category}' to {count} other transactions with merchant '{merchant_text}'"
                    )

            return True
        except Transaction.DoesNotExist:
            return False

    def get_suggestions_for_merchant(
        self, merchant_text: str, top_k: int = 3
    ) -> List[Dict]:
        """
        Get category suggestions for a merchant based on similar merchants.

        Args:
            merchant_text: Merchant/booking text to get suggestions for
            top_k: Number of suggestions to return

        Returns:
            List of suggestion dicts with 'category', 'confidence', and 'similar_merchant'
        """
        similar_merchants = self.categorizer.get_similar_merchants(merchant_text, top_k)

        suggestions = []
        seen_categories = set()

        for similar_merchant, category, similarity in similar_merchants:
            if category not in seen_categories:
                suggestions.append(
                    {
                        "category": category,
                        "confidence": similarity,
                        "similar_merchant": similar_merchant,
                    }
                )
                seen_categories.add(category)

        return suggestions

    def get_categorization_stats(self) -> Dict:
        """Get overall categorization statistics."""
        try:
            total_transactions = Transaction.objects.count()
            categorized = Transaction.objects.exclude(
                category__in=["", "Uncategorized", "nan"]
            ).count()
            manually_categorized = Transaction.objects.filter(
                is_manually_categorized=True
            ).count()
            high_confidence = Transaction.objects.filter(
                category_confidence__gte=0.8
            ).count()
            medium_confidence = Transaction.objects.filter(
                category_confidence__gte=0.6, category_confidence__lt=0.8
            ).count()
            low_confidence = Transaction.objects.filter(
                category_confidence__lt=0.6, category_confidence__gt=0.0
            ).count()

            try:
                semantic_stats = self.categorizer.get_stats()
            except Exception as e:
                print(f"Warning: Could not get semantic stats: {e}")
                semantic_stats = {
                    "total_known_merchants": 0,
                    "total_corrections": 0,
                    "categories": [],
                    "model_loaded": False,
                    "error": str(e),
                }

            return {
                "total_transactions": total_transactions,
                "categorized": categorized,
                "categorization_rate": (categorized / total_transactions * 100)
                if total_transactions > 0
                else 0,
                "manually_categorized": manually_categorized,
                "high_confidence": high_confidence,
                "medium_confidence": medium_confidence,
                "low_confidence": low_confidence,
                "semantic_categorizer": semantic_stats,
            }
        except Exception as e:
            import traceback

            print(f"Error in get_categorization_stats: {e}")
            traceback.print_exc()
            raise

    def recategorize_uncategorized_transactions(self) -> Dict:
        """
        Re-run categorization on all uncategorized transactions.

        Returns:
            Dict with recategorization statistics
        """
        uncategorized = Transaction.objects.filter(
            category__in=["", "Uncategorized", "nan"]
        ).exclude(is_manually_categorized=True)

        return self.categorize_transactions_bulk(list(uncategorized))

    def improve_low_confidence_predictions(
        self, confidence_threshold: float = 0.6
    ) -> List[Dict]:
        """
        Get transactions with low confidence predictions for manual review.
        Returns ALL low-confidence transactions sorted by confidence (lowest first).

        Args:
            confidence_threshold: Threshold below which predictions are considered low confidence

        Returns:
            List of transaction data sorted by confidence (lowest first)
        """
        low_confidence_transactions = (
            Transaction.objects.filter(
                category_confidence__lt=confidence_threshold,
                category_confidence__gte=0.0,
                is_manually_categorized=False,
            )
            .exclude(category__in=["Uncategorized", "nan", ""])
            .order_by("category_confidence")
        )

        results = []
        for transaction in low_confidence_transactions:
            results.append(
                {
                    "transaction_id": transaction.id,
                    "booking_text": transaction.booking_text,
                    "category": transaction.category,
                    "confidence": transaction.category_confidence or 0.0,
                    "amount": transaction.amount,
                    "date": transaction.date,
                    "currency": transaction.currency
                    if hasattr(transaction, "currency")
                    else "CHF",
                }
            )

        return results
