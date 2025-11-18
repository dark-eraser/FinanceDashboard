"""Semantic categorization service using sentence embeddings."""

import json
import os
import pickle
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class SemanticCategorizer:
    """
    Semantic categorizer that uses sentence embeddings to find similar merchants
    and predict categories based on similarity to known categorized merchants.

    Uses a 3-tier strategy:
    1. Exact match in merchant mapping (highest confidence)
    2. Keyword rules (high confidence)
    3. Semantic similarity (medium-high confidence)
    """

    # Keyword rules for common merchants
    # NOTE: Order matters! More specific rules should come first
    KEYWORD_RULES = {
        "Uncounted": [
            # Currency exchanges
            r"\bexchanged to (eur|chf|usd|huf|cad)\b",
            # Top-ups (any pattern with asterisks)
            r"\btop-up by \*",
            # Balance migration
            r"\bbalance migration\b",
            # Personal payments (Payment from NAME or Transfer to/from NAME)
            r"(payment from|transfer (to|from))\s+[a-z]",
            # Revolut bank debits/account transfers/standing orders (internal operations)
            r"debit\s+(mobile banking|ebanking mobile|standing order|account transfer):",
            r"^revolut\s+(bank|ltd)",
            # TWINT payments to individuals (format: "TWINT: , NAME +phonenumber")
            r"debit twint:\s*,\s+[a-z\s]+\+\d+",
        ],
        "Utilities": [
            r"\b(swisscom|sunrise|upc|telecom|electricity|water|gas|energie|power|hydro|utility|bill)\b",
        ],
        "Leisure": [
            r"\b(netflix|spotify|youtube|steam|twitch|gaming|playstation|xbox|disney|hulu|hbo)\b",
            r"\b(cinema|movie|theater|concert|museum)\b",
        ],
        "Groceries": [
            r"\b(migros|coop|denner|aldi|lidl|volg|carrefour|edeka|supermarket|market|grocery)\b",
        ],
        "Dining": [
            r"\b(restaurant|pizza|burger|mcdonald|starbucks|cafe|coffee|food|delivery)\b",
            r"\b(domino|kfc|subway|burger king|thai|sushi|chinese|italian)\b",
        ],
        "Transport": [
            r"\b(sbb|vbz|uber|taxi|shell|bp|chevron|fuel|gas station|charging|train|railway)\b",
            r"\b(parking|automat|petrol|diesel)\b",
        ],
        "Shopping": [
            r"\b(amazon|ebay|zalando|h&m|zara|fashion|clothing|store|shop)\b",
            r"\b(digitec|galaxus|mediamarkt|electronics)\b",
        ],
        "Travel": [
            r"\b(booking|airbnb|hotel|flight|airline|ryanair|easyjet|swiss|lufthansa)\b",
            r"\b(hostel|airport|train ticket|train fare)\b",
        ],
        "Health": [
            r"\b(pharmacy|pharma|doctor|medical|dentist|hospital|clinic|health)\b",
            r"\b(dm drogerie|medicine|vitamins)\b",
        ],
        "Bank Transfer": [
            r"\b(wire|revolut|paypal)\b",  # Removed "transfer" and "payment from" which are too generic
        ],
    }

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", data_dir: str = "data"):
        """
        Initialize the semantic categorizer.

        Args:
            model_name: Name of the sentence transformer model to use
            data_dir: Directory to store categorizer data files
        """
        self.model_name = model_name
        self.model = None  # Lazy load to avoid startup delays
        self.data_dir = data_dir

        # Ensure data directory exists
        try:
            os.makedirs(data_dir, exist_ok=True)
            print(f"SemanticCategorizer: Data directory: {data_dir}")
        except Exception as e:
            print(f"ERROR: Failed to create data directory {data_dir}: {e}")
            raise

        # File paths for persistent storage
        self.merchants_file = os.path.join(data_dir, "known_merchants.json")
        self.embeddings_file = os.path.join(data_dir, "merchant_embeddings.pkl")
        self.corrections_file = os.path.join(data_dir, "user_corrections.json")

        print(f"SemanticCategorizer: merchants_file={self.merchants_file}")
        print(f"SemanticCategorizer: embeddings_file={self.embeddings_file}")
        print(f"SemanticCategorizer: corrections_file={self.corrections_file}")

        # In-memory storage
        self.known_merchants: Dict[str, str] = {}  # merchant -> category
        self.merchant_embeddings: Dict[str, np.ndarray] = {}  # merchant -> embedding
        self.correction_history: List[Dict] = []
        self.confidence_adjustments: Dict[str, float] = {}  # merchant -> adjustment

        # Load merchant mapping for rule-based categorization
        self.merchant_mapping: Dict[str, str] = {}  # merchant -> category
        try:
            self._load_merchant_mapping()
        except Exception as e:
            print(f"WARNING: Failed to load merchant mapping: {e}")

        # Load existing data
        try:
            self._load_data()
        except Exception as e:
            print(f"WARNING: Failed to load existing data: {e}")
            import traceback
            traceback.print_exc()

    def _load_merchant_mapping(self):
        """Load merchant category mapping from JSON file."""
        mapping_file = os.path.join(
            os.path.dirname(__file__), "merchant_category_mapping.json"
        )
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r") as f:
                    self.merchant_mapping = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load merchant mapping: {e}")

    def _get_model(self):
        """Lazy load the sentence transformer model."""
        if self.model is None:
            print(f"Loading sentence transformer model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
        return self.model

    def _load_data(self):
        """Load known merchants, embeddings, and correction history from disk."""
        # Load known merchants
        if os.path.exists(self.merchants_file):
            try:
                with open(self.merchants_file, "r") as f:
                    self.known_merchants = json.load(f)
                print(f"Loaded {len(self.known_merchants)} known merchants")
            except Exception as e:
                print(f"ERROR: Failed to load merchants from {self.merchants_file}: {e}")

        # Load embeddings
        if os.path.exists(self.embeddings_file):
            try:
                with open(self.embeddings_file, "rb") as f:
                    self.merchant_embeddings = pickle.load(f)
                print(f"Loaded {len(self.merchant_embeddings)} merchant embeddings")
            except Exception as e:
                print(f"ERROR: Failed to load embeddings from {self.embeddings_file}: {e}")

        # Load correction history
        if os.path.exists(self.corrections_file):
            try:
                with open(self.corrections_file, "r") as f:
                    self.correction_history = json.load(f)
                print(f"Loaded {len(self.correction_history)} corrections")
            except Exception as e:
                print(f"ERROR: Failed to load corrections from {self.corrections_file}: {e}")

        # Build confidence adjustments from correction history
        try:
            self._build_confidence_adjustments()
        except Exception as e:
            print(f"ERROR: Failed to build confidence adjustments: {e}")

    def _save_data(self):
        """Save all data to disk."""
        # Save known merchants
        with open(self.merchants_file, "w") as f:
            json.dump(self.known_merchants, f, indent=2)

        # Save embeddings
        with open(self.embeddings_file, "wb") as f:
            pickle.dump(self.merchant_embeddings, f)

        # Save correction history
        with open(self.corrections_file, "w") as f:
            json.dump(self.correction_history, f, indent=2)

    def _build_confidence_adjustments(self):
        """Build confidence adjustments from correction history."""
        self.confidence_adjustments = {}

        for correction in self.correction_history:
            merchant = correction["merchant"]
            predicted = correction["predicted"]
            actual = correction["actual"]

            # If user corrected our prediction, reduce confidence for this merchant
            if predicted != actual:
                self.confidence_adjustments[merchant] = -0.3
            else:
                # If user confirmed our prediction, increase confidence
                self.confidence_adjustments[merchant] = 0.2

    def add_known_merchant(self, merchant: str, category: str, save: bool = True):
        """
        Add a known merchant-category mapping.

        Args:
            merchant: Merchant name/description
            category: Category to assign
            save: Whether to save to disk immediately
        """
        merchant = merchant.strip()
        category = category.strip()

        self.known_merchants[merchant] = category

        # Generate embedding for the merchant
        model = self._get_model()
        embedding = model.encode([merchant])[0]
        self.merchant_embeddings[merchant] = embedding

        if save:
            self._save_data()

    def _check_keyword_rules(self, merchant: str) -> Tuple[Optional[str], float]:
        """
        Check if merchant matches any keyword rules.

        Args:
            merchant: Merchant name/description

        Returns:
            Tuple of (category, confidence) or (None, 0.0) if no match
        """
        merchant_lower = merchant.lower()

        for category, patterns in self.KEYWORD_RULES.items():
            for pattern in patterns:
                if re.search(pattern, merchant_lower):
                    return category, 0.95  # High confidence for keyword matches

        return None, 0.0

    def _check_merchant_mapping(self, merchant: str) -> Tuple[Optional[str], float]:
        """
        Check if merchant is in the merchant category mapping.
        Uses exact match first, then case-insensitive, then longer substring matches only.

        Args:
            merchant: Merchant name/description

        Returns:
            Tuple of (category, confidence) or (None, 0.0) if no match
        """
        # Try exact match
        if merchant in self.merchant_mapping:
            return self.merchant_mapping[merchant], 1.0

        # Try case-insensitive match
        merchant_lower = merchant.lower()
        for key, category in self.merchant_mapping.items():
            if key.lower() == merchant_lower:
                return category, 1.0

        # Try substring match ONLY for keys longer than 15 characters
        # This avoids matching "Swiss" to "Swisscom" incorrectly
        for key, category in self.merchant_mapping.items():
            if len(key) >= 15 and key.lower() in merchant_lower:
                return category, 0.9

        return None, 0.0

    def predict_category(
        self, merchant: str, threshold: float = 0.5
    ) -> Tuple[Optional[str], float]:
        """
        Predict category for a merchant using 3-tier strategy:
        1. Merchant mapping (exact/substring match) - highest confidence
        2. Keyword rules - high confidence
        3. Semantic similarity - medium-high confidence

        Args:
            merchant: Merchant name/description to categorize
            threshold: Minimum similarity threshold for semantic matching

        Returns:
            Tuple of (predicted_category, confidence_score)
        """
        merchant = merchant.strip()

        # Tier 1: Check merchant mapping first
        mapped_category, mapped_confidence = self._check_merchant_mapping(merchant)
        if mapped_category:
            return mapped_category, mapped_confidence

        # Tier 2: Check keyword rules
        keyword_category, keyword_confidence = self._check_keyword_rules(merchant)
        if keyword_category:
            return keyword_category, keyword_confidence

        # Tier 3: Check if we already know this exact merchant in learned data
        if merchant in self.known_merchants:
            return self.known_merchants[merchant], 1.0

        # Tier 4: Semantic matching with learned merchants
        # If no known merchants, can't predict
        if not self.merchant_embeddings:
            return None, 0.0

        # Generate embedding for the new merchant
        model = self._get_model()
        new_embedding = model.encode([merchant])[0]

        # Find most similar known merchants
        similarities = {}
        for known_merchant, known_embedding in self.merchant_embeddings.items():
            # Ensure both embeddings are 1D arrays
            new_emb = new_embedding.reshape(1, -1)
            known_emb = known_embedding.reshape(1, -1)
            sim = cosine_similarity(new_emb, known_emb)[0][0]
            if sim > threshold:
                similarities[known_merchant] = sim

        if not similarities:
            return None, 0.0

        # Get the most similar merchant
        best_match = max(similarities, key=similarities.get)
        base_confidence = similarities[best_match]

        # Apply confidence adjustments based on user corrections
        confidence_adjustment = self.confidence_adjustments.get(merchant, 0.0)
        final_confidence = min(1.0, max(0.0, base_confidence + confidence_adjustment))

        predicted_category = self.known_merchants[best_match]

        return predicted_category, final_confidence

    def predict_with_context(
        self,
        merchant: str,
        amount: float = None,
        date_str: str = None,
        threshold: float = 0.4,
    ) -> Tuple[Optional[str], float]:
        """
        Enhanced prediction that considers transaction context.

        Args:
            merchant: Merchant name/description
            amount: Transaction amount
            date_str: Date string
            threshold: Minimum similarity threshold (default 0.4 for fuzzy merchant matching)

        Returns:
            Tuple of (predicted_category, confidence_score)
        """
        # Get base prediction
        base_category, base_confidence = self.predict_category(merchant, threshold)

        if base_category is None:
            return None, 0.0

        # Context-based adjustments
        confidence_boost = 0.0

        # Amount and keyword-based heuristics
        if amount is not None:
            merchant_lower = merchant.lower()

            # Small amounts + subscription keywords = likely utilities/services
            if amount < 30 and any(
                word in merchant_lower
                for word in [
                    "subscription",
                    "premium",
                    "monthly",
                    "netflix",
                    "spotify",
                    "adobe",
                ]
            ):
                if base_category in ["Utilities", "Shopping"]:
                    confidence_boost += 0.2

            # Small amounts + food keywords = likely dining
            elif amount < 20 and any(
                word in merchant_lower
                for word in [
                    "cafe",
                    "restaurant",
                    "bar",
                    "pizza",
                    "burger",
                    "starbucks",
                    "mcdonald",
                ]
            ):
                if base_category == "Dining":
                    confidence_boost += 0.15

            # Small amounts + transport keywords = likely transport
            elif amount < 50 and any(
                word in merchant_lower
                for word in [
                    "sbb",
                    "vbz",
                    "transport",
                    "taxi",
                    "uber",
                    "train",
                    "ticket",
                ]
            ):
                if base_category == "Transport":
                    confidence_boost += 0.2

            # Large amounts + store keywords = likely shopping
            elif amount > 50 and any(
                word in merchant_lower
                for word in ["shop", "store", "amazon", "galaxus", "digitec"]
            ):
                if base_category == "Shopping":
                    confidence_boost += 0.1

        final_confidence = min(1.0, base_confidence + confidence_boost)

        return base_category, final_confidence

    def record_correction(
        self,
        merchant: str,
        predicted_category: str,
        actual_category: str,
        confidence: float = None,
    ):
        """
        Record a user correction to improve future predictions.

        Args:
            merchant: Merchant that was categorized
            predicted_category: What we predicted
            actual_category: What user corrected it to
            confidence: Confidence of our original prediction
        """
        correction = {
            "merchant": merchant,
            "predicted": predicted_category,
            "actual": actual_category,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
        }

        self.correction_history.append(correction)

        # Update the known merchants with the corrected category
        self.add_known_merchant(merchant, actual_category, save=False)

        # Rebuild confidence adjustments
        self._build_confidence_adjustments()

        # Save all data
        self._save_data()

    def get_similar_merchants(
        self, merchant: str, top_k: int = 5
    ) -> List[Tuple[str, str, float]]:
        """
        Get the most similar merchants to the given merchant.

        Args:
            merchant: Merchant to find similarities for
            top_k: Number of similar merchants to return

        Returns:
            List of (merchant_name, category, similarity_score) tuples
        """
        if not self.merchant_embeddings:
            return []

        model = self._get_model()
        new_embedding = model.encode([merchant])[0]

        similarities = []
        for known_merchant, known_embedding in self.merchant_embeddings.items():
            # Ensure both embeddings are 1D arrays
            new_emb = new_embedding.reshape(1, -1)
            known_emb = known_embedding.reshape(1, -1)
            sim = cosine_similarity(new_emb, known_emb)[0][0]
            category = self.known_merchants[known_merchant]
            similarities.append((known_merchant, category, sim))

        # Sort by similarity and return top k
        similarities.sort(key=lambda x: x[2], reverse=True)
        return similarities[:top_k]

    def bulk_import_from_existing_data(self, transactions_data: List[Dict]):
        """
        Bulk import merchant-category mappings from existing transaction data.

        Args:
            transactions_data: List of transaction dicts with 'merchant' and 'category' keys
        """
        print("Importing existing merchant-category mappings...")

        imported_count = 0
        for transaction in transactions_data:
            merchant = transaction.get("merchant", "").strip()
            category = transaction.get("category", "").strip()

            if merchant and category and category != "Uncounted":
                if merchant not in self.known_merchants:
                    self.add_known_merchant(merchant, category, save=False)
                    imported_count += 1

        if imported_count > 0:
            self._save_data()
            print(f"Imported {imported_count} new merchant-category mappings")
        else:
            print("No new mappings to import")

    def get_stats(self) -> Dict:
        """Get statistics about the categorizer."""
        try:
            return {
                "total_known_merchants": len(self.known_merchants),
                "total_corrections": len(self.correction_history),
                "categories": list(set(self.known_merchants.values())),
                "model_loaded": self.model is not None,
            }
        except Exception as e:
            print(f"Error in get_stats: {e}")
            return {
                "total_known_merchants": 0,
                "total_corrections": 0,
                "categories": [],
                "model_loaded": False,
                "error": str(e),
            }
