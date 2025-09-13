"""Bank Statement Trend Analysis.

This script will parse and visualize trends for ZKB and Revolut statements separately.
"""
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# --- ZKB Statement: Month-by-Month by Category ---
zkb = pd.read_csv(
    "data/zkb_statement_202509.csv", sep=";", decimal=".", thousands=",", dayfirst=True
)
zkb["Date"] = pd.to_datetime(zkb["Date"], format="%d.%m.%Y")
zkb["Month"] = zkb["Date"].dt.to_period("M")
zkb["Debit CHF"] = pd.to_numeric(
    zkb["Debit CHF"].astype(str).str.replace(",", ""), errors="coerce"
).fillna(0)
zkb["Credit CHF"] = pd.to_numeric(
    zkb["Credit CHF"].astype(str).str.replace(",", ""), errors="coerce"
).fillna(0)


def zkb_categorize(text):
    """Categorize ZKB transactions based on booking text.

    Args:
        text: The booking text from ZKB statement.

    Returns:
        str: The category of the transaction.
    """
    text = str(text).lower()
    if "salary" in text:
        return "Salary"
    if "twint" in text:
        return "TWINT"
    if "standing order" in text:
        return "Standing Order"
    if "mobile banking" in text:
        return "Mobile Banking"
    if "credit" in text:
        return "Credit"
    if "debit" in text:
        return "Debit"
    if "purchase" in text:
        return "Purchase"
    if "account transfer" in text:
        return "Account Transfer"
    return "Other"


zkb["Category"] = zkb["Booking text"].apply(zkb_categorize)

# Spending and income by month and category
zkb["Spending"] = zkb["Debit CHF"]
zkb["Income"] = zkb["Credit CHF"]
zkb_pivot = zkb.pivot_table(
    index=["Month", "Category"], values=["Spending", "Income"], aggfunc="sum"
).reset_index()

# Plot ZKB spending by category/month
plt.figure(figsize=(14, 6))
sns.barplot(data=zkb_pivot, x="Month", y="Spending", hue="Category")
plt.title("ZKB Spending by Category (Monthly)")
plt.ylabel("Spending (CHF)")
plt.xlabel("Month")
plt.legend(title="Category", bbox_to_anchor=(1.05, 1), loc="upper left")
plt.tight_layout()
plt.show()

# Plot ZKB income by category/month
plt.figure(figsize=(14, 6))
sns.barplot(data=zkb_pivot, x="Month", y="Income", hue="Category")
plt.title("ZKB Income by Category (Monthly)")
plt.ylabel("Income (CHF)")
plt.xlabel("Month")
plt.legend(title="Category", bbox_to_anchor=(1.05, 1), loc="upper left")
plt.tight_layout()
plt.show()

# --- Revolut Statement: Month-by-Month by Category ---
revolut = pd.read_csv("data/revolut_statement_202509.csv")
revolut["Completed Date"] = pd.to_datetime(revolut["Completed Date"])
revolut["Month"] = revolut["Completed Date"].dt.to_period("M")
revolut["Amount"] = pd.to_numeric(revolut["Amount"], errors="coerce").fillna(0)


def revolut_categorize(row):
    """Categorize Revolut transactions based on type and description.

    Args:
        row: A pandas Series containing 'Type' and 'Description' columns.

    Returns:
        str: The category of the transaction.
    """
    t = str(row["Type"]).lower()
    d = str(row["Description"]).lower()
    if "topup" in t or "top-up" in d:
        return "Topup"
    if "exchange" in t:
        return "Exchange"
    if "transfer" in t:
        return "Transfer"
    if "card payment" in t:
        return "Card Payment"
    if "fee" in t or "fee" in d:
        return "Fee"
    return "Other"


revolut["Category"] = revolut.apply(revolut_categorize, axis=1)
revolut["Spending"] = revolut["Amount"].apply(lambda x: -x if x < 0 else 0)
revolut["Income"] = revolut["Amount"].apply(lambda x: x if x > 0 else 0)
revolut_eur = revolut[revolut["Currency"] == "EUR"]
revolut_pivot = revolut_eur.pivot_table(
    index=["Month", "Category"], values=["Spending", "Income"], aggfunc="sum"
).reset_index()

# Plot Revolut spending by category/month
plt.figure(figsize=(14, 6))
sns.barplot(data=revolut_pivot, x="Month", y="Spending", hue="Category")
plt.title("Revolut Spending by Category (Monthly, EUR)")
plt.ylabel("Spending (EUR)")
plt.xlabel("Month")
plt.legend(title="Category", bbox_to_anchor=(1.05, 1), loc="upper left")
plt.tight_layout()
plt.show()

# Plot Revolut income by category/month
plt.figure(figsize=(14, 6))
sns.barplot(data=revolut_pivot, x="Month", y="Income", hue="Category")
plt.title("Revolut Income by Category (Monthly, EUR)")
plt.ylabel("Income (EUR)")
plt.xlabel("Month")
plt.legend(title="Category", bbox_to_anchor=(1.05, 1), loc="upper left")
plt.tight_layout()
plt.show()
