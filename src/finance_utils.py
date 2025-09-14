"""Finance utility functions for transaction categorization and processing."""
import spacy

nlp = spacy.load("en_core_web_sm")

CATEGORY_KEYWORDS = {
    "Groceries": ["coop", "migros", "aldi", "lidl", "denner", "supermarket", "grocery"],
    "Transport": [
        "sbb",
        "vbz",
        "bus",
        "train",
        "tram",
        "uber",
        "taxi",
        "easyr",
        "easyrider",
        "bahn",
        "sncf",
        "ratp",
        "bp",
    ],
    "Insurance": ["sanitas", "axa", "versicherung", "insurance"],
    "Dining": [
        "restaurant",
        "cafe",
        "bar",
        "mc donald",
        "starbucks",
        "pizza",
        "kebab",
        "dining",
        "resto",
    ],
    "Salary": ["salary", "eraneos", "payroll", "lohn"],
    "Shopping": [
        "galaxus",
        "digitec",
        "decathlon",
        "shopping",
        "store",
        "shop",
        "boutique",
    ],
    "Utilities": [
        "swisscom",
        "sunrise",
        "telecom",
        "internet",
        "electricity",
        "wasser",
        "water",
        "gas",
        "utility",
    ],
    "Parking": ["parking", "park", "parkingpay"],
    "Health": ["pharmacy", "apotheke", "doctor", "arzt", "hospital", "clinic"],
    "Travel": [
        "hotel",
        "hostel",
        "airbnb",
        "booking.com",
        "flight",
        "airline",
        "bahn",
        "train",
        "sncf",
        "ratp",
        "bookaway" "rentcars",
    ],
    "Bank Transfer": [
        "transfer",
        "account transfer",
        "sepa",
        "wire",
        "überweisung",
        "revolut france, succursale de revolut bank uab",
        "payment from",
    ],
    "Mobile Transfer": ["twint"],
    "Standing Order": ["standing order"],
    "Fee": ["fee", "charge", "gebühr"],
    "Other": [],
}


def categorize_transaction(text):
    """Categorize a transaction based on its text description.

    Args:
        text: The transaction description text.

    Returns:
        str: The category of the transaction.
    """
    text_l = str(text).lower()
    if "credit" in text_l:
        return "Refund"
    if ":" in text_l:
        text_l = text_l.split(":", 1)[1].strip()
    # Special rule: if contains 'balance migration'
    # or 'exchanged to' after prefix removal
    if "balance migration" in text_l or "exchanged to" in text_l:
        return "Uncounted"
    # Special rule: if contains 'revolut' and is a standing order
    if "revolut" in text_l and "standing order" in text_l:
        return "Uncounted"
    # Special rule: if matches vault transaction (e.g. 'To pocket CHF TABLET from CHF')
    if ("to pocket" in text_l or "to vault" in text_l) and "from chf" in text_l:
        return "Vault"
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_l:
                return category
    doc = nlp(text_l)
    for ent in doc.ents:
        for category, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in ent.text:
                    return category
    return "Other"


def extract_merchant_from_revolut(description):
    """Extract merchant from Revolut transaction description.

    Args:
        description: The description text from Revolut transaction.

    Returns:
        str: The extracted merchant name.
    """
    doc = nlp(str(description))
    for ent in doc.ents:
        if ent.label_ in ["ORG", "PERSON", "GPE", "LOC"]:
            return ent.text
    words = [w for w in str(description).split() if w.istitle()]
    if words:
        return words[0]
    return str(description).split()[0] if description else ""


def extract_means_and_merchant(text):
    """Extract means of payment and merchant from ZKB booking text.

    Args:
        text: The booking text from ZKB transaction.

    Returns:
        tuple: (means_of_payment, merchant) as strings.
    """
    text = str(text)
    means = None
    for keyword in [
        "TWINT",
        "Standing order",
        "Mobile Banking",
        "Debit card",
        "Credit card",
        "Account transfer",
        "Visa",
        "Mastercard",
    ]:
        if keyword.lower() in text.lower():
            means = keyword.upper()
            break
    merchant = None
    if ":" in text:
        after_colon = text.split(":", 1)[1].strip()
        if means and after_colon.upper().startswith(means):
            after_colon = after_colon[len(means) :].strip(" -:")
        merchant = after_colon
    else:
        merchant = text
    doc = nlp(merchant)
    for ent in doc.ents:
        if ent.label_ in ["ORG", "PERSON", "GPE", "LOC"]:
            merchant = ent.text
            break
    for known in [
        "PARKING",
        "COOP",
        "MIGROS",
        "SBB",
        "BP",
        "POST",
        "DECATHLON",
        "AXA",
        "SUNRISE",
        "SANITAS",
    ]:
        if known in merchant.upper():
            merchant = known.capitalize()
            break
    return means, merchant
