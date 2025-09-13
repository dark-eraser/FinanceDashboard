"""Finance Dashboard for ZKB and Revolut accounts."""
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

from src.finance_utils import (
    categorize_transaction,
    extract_means_and_merchant,
    extract_merchant_from_revolut,
)

# --- Custom CSS to widen content area ---
st.markdown(
    """
    <style>
        .main .block-container {
            max-width: 95vw;
            padding-left: 2vw;
            padding-right: 2vw;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Finance Dashboard: ZKB & Revolut")

# --- Load ZKB ---

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
zkb["Category"] = zkb["Booking text"].apply(categorize_transaction)
zkb[["Means of Payment", "Merchant/Use"]] = zkb["Booking text"].apply(
    lambda x: pd.Series(extract_means_and_merchant(x))
)
zkb["Spending"] = zkb["Debit CHF"]
zkb["Income"] = zkb["Credit CHF"]

# --- Load Revolut ---

revolut = pd.read_csv("data/revolut_statement_202509.csv")
revolut["Completed Date"] = pd.to_datetime(revolut["Completed Date"])
revolut["Month"] = revolut["Completed Date"].dt.to_period("M")
revolut["Amount"] = pd.to_numeric(revolut["Amount"], errors="coerce").fillna(0)
revolut["Category"] = revolut["Description"].apply(categorize_transaction)
revolut["Spending"] = revolut["Amount"].apply(lambda x: abs(x) if x < 0 else 0)
revolut["Income"] = revolut["Amount"].apply(lambda x: x if x > 0 else 0)
revolut_eur = revolut[revolut["Currency"] == "EUR"]


# --- Sidebar Filters ---
account = st.sidebar.selectbox("Account", ["ZKB", "Revolut"])
years_zkb = zkb["Date"].dt.year.astype(str).unique().tolist()
years_revolut = revolut_eur["Completed Date"].dt.year.astype(str).unique().tolist()
years = sorted(list(set(years_zkb + years_revolut)), reverse=True)
years.insert(0, "All")
year = st.sidebar.selectbox("Year", years, index=0)

if account == "ZKB":
    if year == "All":
        df = zkb.copy()
    else:
        df = zkb[zkb["Date"].dt.year.astype(str) == year].copy()
    # Always recalculate category and merchant columns after filtering
    df["Category"] = df["Booking text"].apply(categorize_transaction)
    df[["Means of Payment", "Merchant/Use"]] = df["Booking text"].apply(
        lambda x: pd.Series(extract_means_and_merchant(x))
    )
    months = sorted(df["Month"].astype(str).unique(), reverse=True)
    months.insert(0, "All")
    month = st.sidebar.selectbox("Month", months, index=0)
    if month != "All":
        df = df[df["Month"].astype(str) == month]
    # Category filter
    all_categories = sorted(df["Category"].dropna().unique())
    default_categories = [
        c
        for c in all_categories
        if not (c.lower().startswith("uncounted") or c.lower() == "vault")
    ]
    selected_categories = st.sidebar.multiselect(
        "Show categories", all_categories, default=default_categories
    )
    df = df[df["Category"].isin(selected_categories)]
else:
    if year == "All":
        df = revolut_eur.copy()
    else:
        df = revolut_eur[
            revolut_eur["Completed Date"].dt.year.astype(str) == year
        ].copy()
    # Always recalculate category and merchant columns after filtering
    df["Category"] = df["Description"].apply(categorize_transaction)
    df["Merchant"] = df["Description"].apply(extract_merchant_from_revolut)
    months = sorted(df["Month"].astype(str).unique(), reverse=True)
    months.insert(0, "All")
    month = st.sidebar.selectbox("Month", months, index=0)
    if month != "All":
        df = df[df["Month"].astype(str) == month]
    # Category filter
    all_categories = sorted(df["Category"].dropna().unique())
    default_categories = [
        c
        for c in all_categories
        if not (c.lower().startswith("uncounted") or c.lower() == "vault")
    ]
    selected_categories = st.sidebar.multiselect(
        "Show categories", all_categories, default=default_categories
    )
    df = df[df["Category"].isin(selected_categories)]

# --- Main Dashboard ---

# --- Main Dashboard ---
if account == "ZKB":
    header_text = (
        f'ZKB Account - {year if year != "All" else "All Years"}'
        f'{" / " + month if month != "All" else ""}'
    )
    st.header(header_text)
    st.dataframe(
        df[
            [
                "Date",
                "Booking text",
                "Category",
                "Means of Payment",
                "Merchant/Use",
                "Debit CHF",
                "Credit CHF",
            ]
        ]
    )
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Spending", f"{df['Spending'].sum():,.2f} CHF")
    with col2:
        st.metric("Total Income", f"{df['Income'].sum():,.2f} CHF")
    st.markdown("---")
    st.subheader("Spending by Category")
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.barplot(
        data=df.groupby("Category")["Spending"]
        .sum()
        .reset_index()
        .sort_values("Spending", ascending=False),
        x="Category",
        y="Spending",
        ax=ax,
        palette="crest",
    )
    plt.xticks(rotation=30, ha="right")
    st.pyplot(fig)
    st.subheader("Income by Category")
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.barplot(
        data=df.groupby("Category")["Income"]
        .sum()
        .reset_index()
        .sort_values("Income", ascending=False),
        x="Category",
        y="Income",
        ax=ax,
        palette="crest",
    )
    plt.xticks(rotation=30, ha="right")
    st.pyplot(fig)
else:
    header_text = (
        f'Revolut Account (EUR) - {year if year != "All" else "All Years"}'
        f'{" / " + month if month != "All" else ""}'
    )
    st.header(header_text)
    df["Merchant"] = df["Description"].apply(extract_merchant_from_revolut)
    st.dataframe(
        df[["Completed Date", "Description", "Category", "Merchant", "Amount"]]
    )
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Spending", f"{df['Spending'].sum():,.2f} EUR")
    with col2:
        st.metric("Total Income", f"{df['Income'].sum():,.2f} EUR")
    st.markdown("---")
    st.subheader("Spending by Category")
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.barplot(
        data=df.groupby("Category")["Spending"]
        .sum()
        .reset_index()
        .sort_values("Spending", ascending=False),
        x="Category",
        y="Spending",
        ax=ax,
        palette="crest",
    )
    plt.xticks(rotation=30, ha="right")
    st.pyplot(fig)
    st.subheader("Income by Category")
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.barplot(
        data=df.groupby("Category")["Income"]
        .sum()
        .reset_index()
        .sort_values("Income", ascending=False),
        x="Category",
        y="Income",
        ax=ax,
        palette="crest",
    )
    plt.xticks(rotation=30, ha="right")
    st.pyplot(fig)
