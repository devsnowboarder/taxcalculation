import os
import sys
import argparse
import webbrowser
import csv


def calculate_ss_breakdown(ss_income, other_income, filing_status='single'):
    # Stock sales (capital gains) are included in MAGI for Social Security taxation
    combined_income = other_income + (ss_income * 0.5)
    base1, base2 = (25000, 34000) if filing_status == 'single' else (32000, 44000)
    tier1_taxable, tier2_taxable = 0.0, 0.0

    if combined_income > base2:
        tier1_taxable = min((base2 - base1) * 0.5, 4500.0 if filing_status == 'single' else 6000.0)
        tier2_taxable = (combined_income - base2) * 0.85
    elif combined_income > base1:
        tier1_taxable = (combined_income - base1) * 0.5

    uncapped_taxable = tier1_taxable + tier2_taxable
    max_cap = ss_income * 0.85
    taxable_ss = min(uncapped_taxable, max_cap)
    non_taxable_ss = ss_income - taxable_ss
    pct_taxable = (taxable_ss / ss_income * 100) if ss_income > 0 else 0.0

    return {
        "combined_income": combined_income, "tier1_taxable": tier1_taxable,
        "tier2_taxable": tier2_taxable, "uncapped_taxable": uncapped_taxable,
        "max_cap": max_cap, "taxable_ss": taxable_ss, "non_taxable_ss": non_taxable_ss,
        "pct_taxable": pct_taxable
    }


def calculate_deduction_breakdown(magi, age, filing_status='single', tax_year=2026):
    is_65_or_older = (age >= 65)
    base_deduction = 16100.0 if filing_status == 'single' else 32200.0
    age_65_additional = (2050.0 if tax_year == 2026 else 2000.0) if is_65_or_older else 0.0
    max_enhanced = 6000.0 if is_65_or_older else 0.0
    phaseout_reduction = 0.0
    enhanced_senior_deduction = 0.0

    if is_65_or_older and tax_year in (2025, 2026, 2027, 2028):
        limit_threshold = 75000.0 if filing_status == 'single' else 150000.0
        phase_end_threshold = 175000.0 if filing_status == 'single' else 350000.0

        if magi <= limit_threshold:
            enhanced_senior_deduction = 6000.0
        elif magi < phase_end_threshold:
            phaseout_reduction = (magi - limit_threshold) * 0.06
            enhanced_senior_deduction = max(0.0, 6000.0 - phaseout_reduction)
        else:
            phaseout_reduction = 6000.0

    total_deduction = base_deduction + age_65_additional + enhanced_senior_deduction
    return {
        "base_ded": base_deduction, "age_ded": age_65_additional,
        "max_enhanced": max_enhanced, "phaseout_reduction": phaseout_reduction,
        "enhanced_ded": enhanced_senior_deduction, "total_ded": total_deduction
    }


def calculate_federal_tax(taxable_income, filing_status='single'):
    brackets = [
        (12400, 0.10), (50400, 0.12), (105700, 0.22),
        (201775, 0.24), (256225, 0.32), (640600, 0.35), (float('inf'), 0.37)
    ] if filing_status == 'single' else [
        (24800, 0.10), (100800, 0.12), (211400, 0.22),
        (403550, 0.24), (512450, 0.32), (768700, 0.35), (float('inf'), 0.37)
    ]
    tax, previous_limit, top_bracket = 0.0, 0.0, 0.10
    for limit, rate in brackets:
        if taxable_income > previous_limit:
            tax += (min(taxable_income, limit) - previous_limit) * rate
            top_bracket = rate
            previous_limit = limit
        else:
            break
    return tax, top_bracket


def calculate_ltcg_tax(ordinary_taxable, ltcg, filing_status='single'):
    if ltcg <= 0:
        return 0.0

    # 2026 LTCG Brackets
    b0 = 49450 if filing_status == 'single' else 98900
    b15 = 545500 if filing_status == 'single' else 613700

    tax = 0.0
    remaining_ltcg = ltcg
    current_income = ordinary_taxable

    # Portion taxed at 0%
    if current_income < b0:
        room = b0 - current_income
        in_0 = min(room, remaining_ltcg)
        tax += in_0 * 0.0
        remaining_ltcg -= in_0
        current_income += in_0

    # Portion taxed at 15%
    if remaining_ltcg > 0 and current_income < b15:
        room = b15 - current_income
        in_15 = min(room, remaining_ltcg)
        tax += in_15 * 0.15
        remaining_ltcg -= in_15
        current_income += in_15

    # Portion taxed at 20%
    if remaining_ltcg > 0:
        tax += remaining_ltcg * 0.20

    return tax


def calculate_niit(magi, net_investment_income, filing_status='single'):
    """ Calculates the 3.8% Net Investment Income Tax (NIIT). """
    if net_investment_income <= 0:
        return 0.0

    threshold = 200000.0 if filing_status == 'single' else 250000.0
    excess_magi = max(0.0, magi - threshold)

    # NIIT applies to the lesser of Net Investment Income or MAGI over the threshold
    taxable_amount = min(excess_magi, net_investment_income)
    return taxable_amount * 0.038


def calculate_irmaa(magi, age, filing_status='single'):
    """ Calculates Medicare Part B and Part D IRMAA surcharges for 2026. """
    if age < 65:
        return {"irmaa_tier": 0, "standard_part_b": 0.0, "part_b_surcharge": 0.0, "part_d_surcharge": 0.0,
                "total_annual_irmaa": 0.0}

    if filing_status == 'joint':
        thresholds = [218000, 274000, 342000, 410000, 749999]
    else:  # Single
        thresholds = [109000, 137000, 171000, 205000, 499999]

    surcharges = [
        (0.00, 0.00),  # Tier 1
        (81.20, 14.50),  # Tier 2
        (202.90, 37.50),  # Tier 3
        (324.60, 60.40),  # Tier 4
        (446.30, 83.30),  # Tier 5
        (487.00, 91.00)  # Tier 6
    ]

    tier = 0
    for i, limit in enumerate(thresholds):
        if magi > limit:
            tier = i + 1
        else:
            break

    part_b_surcharge, part_d_surcharge = surcharges[tier]
    standard_part_b = 202.90

    # If joint, penalty is 2x for the household assuming both are on Medicare
    multiplier = 2 if filing_status == 'joint' else 1
    total_annual = (part_b_surcharge + part_d_surcharge) * 12 * multiplier

    return {
        "irmaa_tier": tier + 1,
        "standard_part_b": standard_part_b,
        "part_b_surcharge": part_b_surcharge,
        "part_d_surcharge": part_d_surcharge,
        "total_annual_irmaa": total_annual
    }


def calculate_ca_state_tax(income_401k, stock_sales, age):
    ca_std_deduction = 5600.0
    is_65 = (age >= 65)

    # California taxes capital gains as ordinary income
    ca_agi = income_401k + stock_sales
    ca_taxable_income = max(0.0, ca_agi - ca_std_deduction)

    ca_brackets = [
        (10412, 0.01), (24684, 0.02), (38959, 0.04), (54081, 0.06),
        (68350, 0.08), (349137, 0.093), (418965, 0.103), (698271, 0.113), (float('inf'), 0.123)
    ]

    tax, previous_limit, ca_top_bracket = 0.0, 0.0, 0.01

    for limit, rate in ca_brackets:
        if ca_taxable_income > previous_limit:
            tax += (min(ca_taxable_income, limit) - previous_limit) * rate
            ca_top_bracket = rate
            previous_limit = limit
        else:
            break

    senior_credit = 166.0 if is_65 else 0.0
    ca_final_tax = max(0.0, tax - senior_credit)

    return {
        "ca_agi": ca_agi, "ca_deduction": ca_std_deduction,
        "ca_taxable_income": ca_taxable_income, "ca_tax": ca_final_tax,
        "ca_top_bracket": ca_top_bracket * 100, "senior_credit": senior_credit
    }


def read_income_file(filepath="income.txt"):
    client_name = "Valued Client"
    scenarios = []
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.replace(",", " ").split()
            if len(parts) >= 5:
                client_name = parts[0].replace("_", " ")
                try:
                    age = float(parts[1])
                    inc_401k = float(parts[2].replace("$", ""))
                    ss_inc = float(parts[3].replace("$", ""))
                    stock_sales = float(parts[4].replace("$", ""))
                    filing_status = parts[5].lower() if len(parts) > 5 and parts[5].lower() in ('single',
                                                                                                'joint') else 'single'

                    other_income = inc_401k + stock_sales
                    ss_info = calculate_ss_breakdown(ss_inc, other_income, filing_status)

                    fed_agi = inc_401k + stock_sales + ss_info["taxable_ss"]
                    ded_info = calculate_deduction_breakdown(fed_agi, age, filing_status)

                    fed_ordinary_taxable = max(0.0, (inc_401k + ss_info["taxable_ss"]) - ded_info["total_ded"])
                    excess_deductions = max(0.0, ded_info["total_ded"] - (inc_401k + ss_info["taxable_ss"]))
                    net_stock_sales = max(0.0, stock_sales - excess_deductions)

                    fed_ordinary_tax, fed_bracket = calculate_federal_tax(fed_ordinary_taxable, filing_status)
                    fed_ltcg_tax = calculate_ltcg_tax(fed_ordinary_taxable, net_stock_sales, filing_status)

                    # 1. Calculate the NIIT based on AGI and stock sales
                    niit_tax = calculate_niit(fed_agi, net_stock_sales, filing_status)

                    # 2. Calculate Medicare IRMAA surcharges based on Fed MAGI
                    irmaa_info = calculate_irmaa(fed_agi, age, filing_status)

                    # Total up Federal and CA taxes
                    total_fed_tax = fed_ordinary_tax + fed_ltcg_tax + niit_tax
                    ca_info = calculate_ca_state_tax(inc_401k, stock_sales, age)

                    # Compute True Liabilities and Rates
                    gross = inc_401k + ss_inc + stock_sales
                    total_combined_tax = total_fed_tax + ca_info["ca_tax"]
                    total_liability = total_combined_tax + irmaa_info["total_annual_irmaa"]
                    combined_effective_rate = (total_liability / gross * 100) if gross > 0 else 0.0

                    scenarios.append({
                        "age": int(age), "401k": inc_401k, "ss": ss_inc, "stock_sales": stock_sales,
                        "filing_status": filing_status, "gross_income": gross,
                        "fed_agi": fed_agi, "fed_ordinary_taxable": fed_ordinary_taxable,
                        "fed_ordinary_tax": fed_ordinary_tax, "fed_ltcg_tax": fed_ltcg_tax,
                        "niit_tax": niit_tax,
                        "total_fed_tax": total_fed_tax, "fed_bracket": fed_bracket * 100,
                        "total_combined_tax": total_combined_tax,
                        "total_liability": total_liability,
                        "combined_effective_rate": combined_effective_rate,
                        **ss_info, **ded_info, **ca_info, **irmaa_info
                    })
                except ValueError:
                    continue
    return client_name, scenarios


def generate_html(client_name, results, input_file="income.txt", output_html="federalTax.html"):
    if not results:
        print("No valid scenarios found to generate HTML.")
        return

    ss_rows, ded_rows, ca_rows, hidden_rows = "", "", "", ""
    labels, tax_values, liability_values = [], [], []

    for i, r in enumerate(results, start=1):
        age_badge = f"Age {r['age']} ({r['filing_status'].capitalize()})"
        cap_note = "Yes (85% Cap)" if r['uncapped_taxable'] >= r['max_cap'] else "No"
        irmaa_alert = "bg-red" if r['irmaa_tier'] > 1 else ""

        labels.append(f"Age {r['age']}")
        tax_values.append(round(r['total_combined_tax'], 2))
        liability_values.append(round(r['total_liability'], 2))

        ss_rows += f"<tr><td>{i}</td><td><strong>{age_badge}</strong></td><td class=\"num\">${r['401k']:,.2f}</td><td class=\"num\">${r['stock_sales']:,.2f}</td><td class=\"num\">${r['ss']:,.2f}</td><td class=\"num\">${r['combined_income']:,.2f}</td><td class=\"num\">${r['tier1_taxable']:,.2f}</td><td class=\"num\">${r['tier2_taxable']:,.2f}</td><td class=\"num\">{cap_note}</td><td class=\"num highlight-cell\">${r['taxable_ss']:,.2f} ({r['pct_taxable']:.1f}%)</td><td class=\"num green-cell\">${r['non_taxable_ss']:,.2f}</td></tr>"
        ded_rows += f"<tr><td>{i}</td><td><strong>{age_badge}</strong></td><td class=\"num highlight-cell\">${r['fed_agi']:,.2f}</td><td class=\"num\">${r['total_ded']:,.2f}</td><td class=\"num\">${r['fed_ordinary_taxable']:,.2f}</td><td class=\"num\">${r['fed_ordinary_tax']:,.2f}</td><td class=\"num\">${r['fed_ltcg_tax']:,.2f}</td><td class=\"num tax-cell\">${r['total_fed_tax']:,.2f}</td></tr>"
        ca_rows += f"<tr><td>{i}</td><td><strong>{age_badge}</strong></td><td class=\"num highlight-cell\">${r['ca_agi']:,.2f}</td><td class=\"num\">${r['ca_deduction']:,.2f}</td><td class=\"num\">${r['ca_taxable_income']:,.2f}</td><td class=\"num\">${r['ca_tax']:,.2f}</td><td class=\"num\">{r['ca_top_bracket']:.1f}%</td><td class=\"num tax-cell\">${r['total_combined_tax']:,.2f}</td></tr>"
        hidden_rows += f"<tr class=\"{irmaa_alert}\"><td>{i}</td><td><strong>{age_badge}</strong></td><td class=\"num highlight-cell\">${r['fed_agi']:,.2f}</td><td class=\"num\">${r['stock_sales']:,.2f}</td><td class=\"num\">${r['niit_tax']:,.2f}</td><td class=\"num\">Tier {r['irmaa_tier']}</td><td class=\"num\">${r['part_b_surcharge']:,.2f}</td><td class=\"num\">${r['part_d_surcharge']:,.2f}</td><td class=\"num tax-cell\">${r['total_annual_irmaa']:,.2f}</td><td class=\"num\">{r['combined_effective_rate']:.2f}%</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>2026 Tax Estimate for {client_name}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: system-ui, sans-serif; background: #000000; color: #f8fafc; padding: 2rem; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: #111827; padding: 2rem; border-radius: 12px; border: 1px solid #1f2937; }}
        header {{ background: #0f172a; padding: 2.5rem 2rem; border-radius: 12px; border: 1px solid #1f2937; margin-bottom: 2rem; text-align: center; }}
        h1 {{ margin: 0 0 0.4rem 0; color: #ffffff; font-size: 2rem; }}
        p {{ color: #94a3b8; font-size: 1rem; margin: 0; }}
        .client-badge {{ background: #172554; border: 1px solid #3b82f6; color: #93c5fd; padding: 0.85rem 2rem; border-radius: 8px; font-size: 1.25rem; font-weight: 700; display: inline-block; margin-bottom: 1rem; }}
        h2 {{ font-size: 1.25rem; color: #ffffff; margin: 2rem 0 0.75rem; border-bottom: 1px solid #334155; padding-bottom: 0.5rem; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 2rem; }}
        th, td {{ padding: 0.9rem; border-bottom: 1px solid #1f2937; font-size: 0.86rem; text-align: left; }}
        th {{ background: #1e293b; color: #f8fafc; font-weight: 600; text-transform: uppercase; font-size: 0.73rem; }}
        th.num, td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
        .highlight-cell {{ color: #60a5fa; font-weight: 600; }}
        .green-cell {{ color: #4ade80; font-weight: 600; }}
        .tax-cell {{ background: #451a03; color: #fde68a; font-weight: 700; }}
        .bg-red td {{ background: rgba(153, 27, 27, 0.2); }}
        .chart-container {{ background: #0f172a; padding: 1.5rem; border-radius: 12px; border: 1px solid #1f2937; margin-bottom: 2rem; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="client-badge">Client: {client_name}</div>
            <h1>2026 Federal &amp; California State Tax Breakdown</h1>
            <p>Source file: <strong>{input_file}</strong></p>
        </header>

        <div class="chart-container">
            <canvas id="taxChart" height="90"></canvas>
        </div>

        <h2>1. Federal Social Security Taxation Breakdown</h2>
        <table>
            <thead><tr><th>#</th><th>Scenario</th><th class="num">401(k)</th><th class="num">Stock Sales</th><th class="num">Gross SS</th><th class="num">Combined Income</th><th class="num">Tier 1 (50%)</th><th class="num">Tier 2 (85%)</th><th class="num">85% Cap?</th><th class="num">Taxable SS</th><th class="num">Tax-Free SS</th></tr></thead>
            <tbody>{ss_rows}</tbody>
        </table>

        <h2>2. Federal Tax Deductions &amp; Federal Tax</h2>
        <table>
            <thead><tr><th>#</th><th>Scenario</th><th class="num">Fed AGI</th><th class="num">Total Ded</th><th class="num">Ord Taxable</th><th class="num">Ord Tax</th><th class="num">LTCG Tax</th><th class="num">Total Fed Tax (w/ NIIT)</th></tr></thead>
            <tbody>{ded_rows}</tbody>
        </table>

        <h2>3. California State Tax Section</h2>
        <table>
            <thead><tr><th>#</th><th>Scenario</th><th class="num">CA AGI</th><th class="num">CA Ded</th><th class="num">CA Taxable</th><th class="num">CA Tax</th><th class="num">CA Top Bracket</th><th class="num">Total Combined Tax (Fed + CA)</th></tr></thead>
            <tbody>{ca_rows}</tbody>
        </table>

        <h2>4. Hidden Taxes &amp; Surcharges (NIIT & Medicare IRMAA)</h2>
        <table>
            <thead><tr><th>#</th><th>Scenario</th><th class="num">Fed MAGI</th><th class="num">Net Inv Income</th><th class="num">NIIT (3.8%)</th><th class="num">IRMAA Tier</th><th class="num">Part B Sur. (Mo)</th><th class="num">Part D Sur. (Mo)</th><th class="num">Total Annual IRMAA</th><th class="num">Total Effective Rate</th></tr></thead>
            <tbody>{hidden_rows}</tbody>
        </table>
    </div>

    <script>
        const ctx = document.getElementById('taxChart').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: {labels},
                datasets: [
                    {{
                        label: 'Standard Taxes (Fed + CA)',
                        data: {tax_values},
                        backgroundColor: '#3b82f6',
                        borderColor: '#60a5fa',
                        borderWidth: 1,
                    }},
                    {{
                        label: 'Total Output (Taxes + IRMAA)',
                        data: {liability_values},
                        backgroundColor: '#991b1b',
                        borderColor: '#f87171',
                        borderWidth: 1,
                        type: 'line'
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{ 
                    legend: {{ labels: {{ color: '#f8fafc' }} }},
                    title: {{ display: true, text: 'Total Tax Liability vs. Surcharges', color: '#ffffff', font: {{ size: 16 }} }}
                }},
                scales: {{
                    x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1f2937' }} }},
                    y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1f2937' }} }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated HTML report: {output_html}")
    webbrowser.open('file://' + os.path.realpath(output_html))


def generate_csv(client_name, results, output_csv="federalTax.csv"):
    """ Exports the raw calculated data into a CSV format for Excel/spreadsheet modeling. """
    if not results:
        print("No valid scenarios found to generate CSV.")
        return

    # Extract field names from the first result dictionary
    headers = list(results[0].keys())

    with open(output_csv, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(results)

    print(f"Generated CSV export: {output_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Federal & California Tax Breakdown Reports.")
    parser.add_argument("--input", default="income.txt", help="Path to input income text file")
    parser.add_argument("--output", default="federalTax.html", help="Path to output HTML report")
    parser.add_argument("--csv", default=None, help="Optional: Path to export data as CSV (e.g. data.csv)")
    args = parser.parse_args()

    # Read and process the data
    client, scenario_results = read_income_file(args.input)

    # Always generate the HTML
    generate_html(client, scenario_results, args.input, args.output)

    # Generate CSV if the flag was provided
    if args.csv:
        generate_csv(client, scenario_results, args.csv)