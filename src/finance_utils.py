import os

import pandas as pd
import spacy

"""Finance utility functions for transaction categorization and processing."""

nlp = spacy.load("en_core_web_sm")

CATEGORY_KEYWORDS = {
    "Groceries": [
        "coop",
        "migros",
        "aldi",
        "lidl",
        "denner",
        "supermarket",
        "grocery",
        "carrefour",
        "migrolino",
        "coop to go",
        "volg",
        "edeka",
        "franprix",
    ],
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
        "ratp",
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
        "steakhouse",
        "le crobag",
        "burger king",
        "selecta",
        "orient world",
        "paul",
        "relay",
        "toogoodtogo",
        "too good to go",
        "vending machine",
        "sv group",
        "Gletscherrest.",
        "asiaway",
        "buchmann",
        "gelati",
        "nooba",
        "rice up",
        "nordbrücke",
        "amboss rampe",
        "les halles",
        "tiny fish",
        "monocle",
        "glace",
        "gelateria",
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
        "hm",
        "jumbo",
        "blattner",
        "fnac",
        "brocki-land",
        "aliexpress",
        "amazon",
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
        "apple",
        "swiss post",
        "www.1global.com",
    ],
    "Car": ["garage", "parking", "park", "parkingpay"],
    "Health": [
        "pharmacy",
        "apotheke",
        "doctor",
        "arzt",
        "hospital",
        "clinic",
        "dm",
        "dr",
        "Centre Ophtalmol",
        "coiffure",
    ],
    "Travel": [
        "hotel",
        "hostel",
        "airbnb",
        "booking.com",
        "flight",
        "airline",
        "bahn",
        "train",
        "bookaway",
        "rentcars",
        "easyjet",
        "autostrade",
        "titls rotair",
        "bahn",
        "sncf",
        "bp",
        "shell",
        "socar",
        "iberia",
        "benzin discount",
        "alpes recepcion",
        "edelweiss",
        "esso",
    ],
    "Bank Transfer": [
        "transfer",
        "account transfer",
        "sepa",
        "wire",
        "überweisung",
        "revolut france, succursale de revolut bank uab",
        "payment from",
        "top-up",
    ],
    "Investment": ["degen", "crypto", "coinbase", "binance", "investment", "etoro"],
    "Leisure": [
        "cinema",
        "theater",
        "concert",
        "event",
        "leisure",
        "museo",
        "museum",
        "steam",
        "gotcourts",
        "kunsthaus",
        "disney+",
        "yoga",
        "ground news",
        "kobo",
        "audible",
        "netflix",
        "spotify",
        "hallenbad",
    ],
    "Standing Order": ["standing order"],
    "Fee": ["fee", "charge", "gebühr"],
    "Cash Withdrawal": [
        "atm",
        "cash withdrawal",
        "geldautomat",
        "bankomat",
        "cajero",
        "bancomat",
    ],
    "Work": ["isc2"],
    "Uncounted": ["balance migration", "exchanged to"],
    "Vault": ["pocket", "vault", "pocket withdrawal"],
    "Refund": ["refund"],
    "Rent": ["rent", "miete", "immobilien"],
    "Donation": ["pro infirmis"],
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
    if ":" in text_l:
        text_l = text_l.split(":", 1)[1].strip()

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


def save_categorized_transactions(df, account_name, filename=None):
    """
    Save categorized transactions to a CSV file.
    Args:
        df (pd.DataFrame): DataFrame with transactions and categories.
        account_name (str): 'revolut' or 'zkb' (used in filename if not provided).
        filename (str, optional): Custom filename. If None, uses default pattern.
    """
    if filename is None:
        filename = f"categorized_{account_name.lower()}.csv"
    # Save all columns, or select a subset if you prefer
    df.to_csv(filename, index=False)


def classify_other_transactions_with_spacy(
    input_csv, output_csv=None, text_column="Description"
):
    """
    Load transactions from a CSV (assumed to be uncategorized).
    use spaCy to classify them, and save the result.
    Args:
        input_csv (str): Path to the CSV file with uncategorized transactions.
        output_csv (str, optional): Path to save the classified CSV.
        If None, appends '_spacy' to input filename.
        text_column (str): The column containing the transaction description.
    Returns:
        pd.DataFrame: The DataFrame with new categories.
    """
    import pandas as pd

    df = pd.read_csv(input_csv)
    df["Category_spacy"] = df[text_column].apply(lambda x: categorize_transaction(x))
    if output_csv is None:
        output_csv = input_csv.replace(".csv", "_spacy.csv")
    df.to_csv(output_csv, index=False)
    return df


if __name__ == "__main__":
    # Example: Load and save categorized ZKB transactions
    if os.path.exists("data/zkb_statement_202509.csv"):
        zkb = pd.read_csv(
            "data/zkb_statement_202509.csv",
            sep=";",
            decimal=".",
            thousands=",",
            dayfirst=True,
        )
        if "Category" not in zkb.columns:
            zkb["Category"] = zkb["Booking text"].apply(categorize_transaction)
        save_categorized_transactions(zkb, "zkb")
    # Example: Load and save categorized Revolut transactions
    if os.path.exists("data/revolut_statement_202509.csv"):
        revolut = pd.read_csv("data/revolut_statement_202509.csv")
        if "Category" not in revolut.columns:
            revolut["Category"] = revolut["Description"].apply(categorize_transaction)
        save_categorized_transactions(revolut, "revolut")
