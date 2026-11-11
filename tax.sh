#!/bin/bash

# Default to james.txt if no argument is passed, or use the first argument ($1)
CLIENT_NAME="${1:-james.txt}"

# Automatically append .txt if you only typed the name (e.g., "./tax.sh james")
if [[ "$CLIENT_NAME" != *.txt ]]; then
    CLIENT_NAME="${CLIENT_NAME}.txt"
fi

INPUT_FILE="taxAccounts/${CLIENT_NAME}"

# Verify the file exists inside taxAccounts/ before running
if [[ ! -f "$INPUT_FILE" ]]; then
    echo "Error: '$INPUT_FILE' not found!"
    echo "Available .txt files in taxAccounts/:"
    ls -1 taxAccounts/*.txt 2>/dev/null
    exit 1
fi

echo "Running 2026 Tax Calculation for: $INPUT_FILE"
python3 2026TaxCalculation.py "$INPUT_FILE" --csv