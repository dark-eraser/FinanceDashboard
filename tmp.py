import re

import pandas as pd

csv_file = "data/categorized_zkb_statement_202509_flat.csv"

df = pd.read_csv(csv_file, sep=";")

pattern = re.compile(r"^Credit TWINT: [^,]+ [0-9]{7,}$")

mask = df["Booking text"].apply(lambda x: bool(pattern.match(str(x))))
refund_mask = df["Category"] == "Refund"
to_update = mask & refund_mask

df.loc[to_update, "Category"] = "Bank Transfer"

df.to_csv(csv_file, sep=";", index=False)
print(f"Updated {to_update.sum()} rows.")
