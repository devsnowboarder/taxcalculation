#!/usr/bin/env bash
set -e
# how to run it
# ./run_tax_report.sh taxAccounts/{file.txt} name

# 1. Store input argument into a variable (defaults to income.txt if omitted)
INPUT_NAME="${1:-income.txt}"

# 2. Normalize to file name and full path
# Example: if INPUT_NAME is "taxAccounts/smith.txt" or "smith.txt", FILE_BASENAME becomes "smith.txt"
FILE_BASENAME="$(basename "$INPUT_NAME")"
INPUT_PATH="taxAccounts/$FILE_BASENAME"

# Check if the file exists before running
if [ ! -f "$INPUT_PATH" ]; then
    echo "Error: Input file '$INPUT_PATH' not found."
    exit 1
fi

echo "Processing client file: $FILE_BASENAME"
echo "Reading from: $INPUT_PATH"

# 3. Execute python script using the variable
python3 2026TaxCalculation.py "$INPUT_PATH" \
    --html-dir "taxHTMLReport" \
    --csv \
    --no-browser

echo "Done! Output saved to: taxHTMLReport/${FILE_BASENAME%.*}.html"