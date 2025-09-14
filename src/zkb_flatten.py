import csv
import re

INPUT_FILE = "data/zkb_statement_202509.csv"
OUTPUT_FILE = "data/zkb_statement_202509_flat.csv"

pattern = re.compile(r"Debit (Mobile Banking|Standing order|eBanking Mobile) \((\d+)\)")

with open(INPUT_FILE, newline="", encoding="utf-8") as infile, open(
    OUTPUT_FILE, "w", newline="", encoding="utf-8"
) as outfile:
    reader = csv.reader(infile, delimiter=";")
    writer = csv.writer(outfile, delimiter=";")
    header = next(reader)
    writer.writerow(header)
    rows = list(reader)
    i = 0
    while i < len(rows):
        row = rows[i]
        booking_text = row[1] if len(row) > 1 else ""
        match = pattern.search(booking_text)
        if match:
            n = int(match.group(2))
            # Write the next n rows (details), skip the parent row
            for j in range(1, n + 1):
                if i + j < len(rows):
                    writer.writerow(rows[i + j])
            i += n + 1  # Skip parent + n detail lines
        else:
            writer.writerow(row)
            i += 1
print(f"Flattened file written to {OUTPUT_FILE}")
