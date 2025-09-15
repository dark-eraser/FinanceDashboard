import streamlit as st

st.title("Finance Dashboard")
st.markdown(
    """
Welcome to your personal finance dashboard!

Use the sidebar to navigate between pages:

- **Dashboard**: View and filter your ZKB and Revolut transactions.
- **Compare Months**: Compare spending by category between any two months.
"""
)

# Add a sidebar widget to ensure the sidebar is always visible
st.sidebar.info("Use the sidebar to navigate between pages.")
