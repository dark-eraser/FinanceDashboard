import pandas as pd
import streamlit as st

from src.finance_utils import extract_means_and_merchant, extract_merchant_from_revolut

st.title("Compare Two Months")

# --- Load ZKB ---
zkb = pd.read_csv(
    "data/categorized_zkb_statement_202509_flat.csv",
    sep=";",
    decimal=".",
    thousands=",",
    dayfirst=True,
)
zkb["Date"] = pd.to_datetime(
    zkb["Date"], format="mixed", dayfirst=True, errors="coerce"
)
zkb["Month"] = zkb["Date"].dt.to_period("M")
zkb["Debit CHF"] = pd.to_numeric(
    zkb["Debit CHF"].astype(str).str.replace(",", ""), errors="coerce"
).fillna(0)
zkb["Credit CHF"] = pd.to_numeric(
    zkb["Credit CHF"].astype(str).str.replace(",", ""), errors="coerce"
).fillna(0)
zkb[["Means of Payment", "Merchant/Use"]] = zkb["Booking text"].apply(
    lambda x: pd.Series(extract_means_and_merchant(x))
)
zkb["Spending"] = zkb["Debit CHF"]
zkb["Income"] = zkb["Credit CHF"]

# --- Load Revolut ---
revolut = pd.read_csv("data/categorized_revolut_statement_202509.csv")
revolut["Completed Date"] = pd.to_datetime(
    revolut["Completed Date"], format="mixed", errors="coerce", dayfirst=True
)
revolut["Month"] = revolut["Completed Date"].dt.to_period("M")
revolut["Amount"] = pd.to_numeric(revolut["Amount"], errors="coerce").fillna(0)
revolut["Spending"] = revolut["Amount"].apply(lambda x: abs(x) if x < 0 else 0)
revolut["Income"] = revolut["Amount"].apply(lambda x: x if x > 0 else 0)

# --- Sidebar Filters ---
account = st.sidebar.selectbox("Account", ["ZKB", "Revolut"])
years_zkb = zkb["Date"].dt.year.astype(str).unique().tolist()
years_revolut = revolut["Completed Date"].dt.year.astype(str).unique().tolist()
years = sorted(list(set(years_zkb + years_revolut)), reverse=True)
years.insert(0, "All")
year = st.sidebar.selectbox("Year", years, index=0)

# --- DataFrame selection logic ---
if account == "ZKB":
    if year == "All":
        df = zkb.copy()
    else:
        df = zkb[zkb["Date"].dt.year.astype(str) == year].copy()
    df[["Means of Payment", "Merchant/Use"]] = df["Booking text"].apply(
        lambda x: pd.Series(extract_means_and_merchant(x))
    )
    months = sorted(df["Month"].astype(str).unique(), reverse=True)
    months = [m for m in months if m != "All"]
else:
    if year == "All":
        df = revolut.copy()
    else:
        df = revolut[revolut["Completed Date"].dt.year.astype(str) == year].copy()
    df["Merchant"] = df["Description"].apply(extract_merchant_from_revolut)
    months = sorted(df["Month"].astype(str).unique(), reverse=True)
    months = [m for m in months if m != "All"]

if len(months) < 2:
    st.warning("Not enough months to compare.")
    st.stop()
month1 = st.selectbox("Select first month", months, key="month1")
month2 = st.selectbox(
    "Select second month", [m for m in months if m != month1], key="month2"
)
df1 = df[df["Month"].astype(str) == month1]
df2 = df[df["Month"].astype(str) == month2]
col1, col2 = st.columns(2)
with col1:
    st.subheader(f"Spending in {month1}")
    st.metric("Total Spending", f"{df1['Spending'].sum():,.2f}")
    st.bar_chart(df1.groupby("Category")["Spending"].sum())
with col2:
    st.subheader(f"Spending in {month2}")
    st.metric("Total Spending", f"{df2['Spending'].sum():,.2f}")
    st.bar_chart(df2.groupby("Category")["Spending"].sum())
st.markdown("---")
st.subheader("Category Comparison Table")
cat_compare = pd.DataFrame(
    {
        month1: df1.groupby("Category")["Spending"].sum(),
        month2: df2.groupby("Category")["Spending"].sum(),
    }
).fillna(0)
st.dataframe(cat_compare)
