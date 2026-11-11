
import os
import webbrowser

def calculate_ss_breakdown(ss_income, other_income, filing_status='single'):
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

def calculate_deduction_breakdown(magi, age, tax_year=2026):
    is_65_or_older = (age >= 65)
    base_deduction = 16100.0 if tax_year == 2026 else 15750.0
    age_65_additional = (2050.0 if tax_year == 2026 else 2000.0) if is_65_or_older else 0.0
    max_enhanced = 6000.0 if is_65_or_older else 0.0
    phaseout_reduction = 0.0
    enhanced_senior_deduction = 0.0
    if is_65_or_older and tax_year in (2025, 2026, 2027, 2028):
        if magi <= 75000:
            enhanced_senior_deduction = 6000.0
        elif magi < 175000:
            phaseout_reduction = (magi - 75000.0) * 0.06
            enhanced_senior_deduction = max(0.0, 6000.0 - phaseout_reduction)
        else:
            phaseout_reduction = 6000.0
    total_deduction = base_deduction + age_65_additional + enhanced_senior_deduction
    return {
        "base_ded": base_deduction, "age_ded": age_65_additional,
        "max_enhanced": max_enhanced, "phaseout_reduction": phaseout_reduction,
        "enhanced_ded": enhanced_senior_deduction, "total_ded": total_deduction
    }

def calculate_federal_tax(taxable_income):
    brackets = [
        (12400, 0.10), (50400, 0.12), (105700, 0.22),
        (201775, 0.24), (256225, 0.32), (640600, 0.35), (float('inf'), 0.37)
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

def calculate_ca_state_tax(income_401k, age):
    ca_std_deduction = 5600.0
    is_65 = (age >= 65)
    ca_agi = income_401k
    ca_taxable_income = max(0.0, ca_agi - ca_std_deduction)
    ca_brackets = [
        (10412, 0.01), (24684, 0.02), (38959, 0.04), (54081, 0.06),
        (68350, 0.08), (349137, 0.093), (418965, 0.103), (698271, 0.113), (float('inf'), 0.123)
    ]
    tax = 0.0
    previous_limit = 0.0
    ca_top_bracket = 0.01
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
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.replace(",", " ").split()
            if len(parts) >= 4:
                client_name = parts[0].replace("_", " ")
                try:
                    age = float(parts[1])
                    inc_401k = float(parts[2].replace("$", ""))
                    ss_inc = float(parts[3].replace("$", ""))

                    ss_info = calculate_ss_breakdown(ss_inc, inc_401k)
                    fed_agi = inc_401k + ss_info["taxable_ss"]
                    ded_info = calculate_deduction_breakdown(fed_agi, age)
                    fed_taxable_inc = max(0.0, fed_agi - ded_info["total_ded"])
                    fed_tax, fed_bracket = calculate_federal_tax(fed_taxable_inc)
                    ca_info = calculate_ca_state_tax(inc_401k, age)
                    gross = inc_401k + ss_inc
                    total_combined_tax = fed_tax + ca_info["ca_tax"]
                    combined_effective_rate = (total_combined_tax / gross * 100) if gross > 0 else 0.0

                    scenarios.append({
                        "age": int(age), "401k": inc_401k, "ss": ss_inc,
                        "fed_agi": fed_agi, "fed_taxable_income": fed_taxable_inc,
                        "fed_tax": fed_tax, "fed_bracket": fed_bracket * 100,
                        "total_combined_tax": total_combined_tax,
                        "combined_effective_rate": combined_effective_rate,
                        **ss_info, **ded_info, **ca_info
                    })
                except ValueError:
                    continue
    return client_name, scenarios

def generate_html(output_html="federalTax.html"):
    client_name, results = read_income_file("income.txt")

    ss_rows, ded_rows, ca_rows = "", "", ""

    # Accumulators for Totals / Averages
    tot_401k = sum(r['401k'] for r in results)
    tot_ss = sum(r['ss'] for r in results)
    tot_combined_inc = sum(r['combined_income'] for r in results)
    tot_tier1 = sum(r['tier1_taxable'] for r in results)
    tot_tier2 = sum(r['tier2_taxable'] for r in results)
    tot_taxable_ss = sum(r['taxable_ss'] for r in results)
    tot_non_taxable_ss = sum(r['non_taxable_ss'] for r in results)

    tot_fed_agi = sum(r['fed_agi'] for r in results)
    tot_base_ded = sum(r['base_ded'] for r in results)
    tot_age_ded = sum(r['age_ded'] for r in results)
    tot_max_enh = sum(r['max_enhanced'] for r in results)
    tot_phaseout = sum(r['phaseout_reduction'] for r in results)
    tot_enh_ded = sum(r['enhanced_ded'] for r in results)
    tot_total_ded = sum(r['total_ded'] for r in results)
    tot_fed_taxable = sum(r['fed_taxable_income'] for r in results)
    tot_fed_tax = sum(r['fed_tax'] for r in results)

    tot_ca_agi = sum(r['ca_agi'] for r in results)
    tot_ca_ded = sum(r['ca_deduction'] for r in results)
    tot_ca_taxable = sum(r['ca_taxable_income'] for r in results)
    tot_ca_tax = sum(r['ca_tax'] for r in results)
    tot_combined_tax = sum(r['total_combined_tax'] for r in results)

    n = len(results) if len(results) > 0 else 1
    avg_effective_rate = sum(r['combined_effective_rate'] for r in results) / n

    for r in results:
        age_badge = f"Age {r['age']} (65+)" if r['age'] >= 65 else f"Age {r['age']} (<65)"
        cap_note = "Yes (85% Cap)" if r['uncapped_taxable'] >= r['max_cap'] else "No"

        ss_rows += f"<tr><td><strong>{age_badge}</strong></td><td class="num">${r['401k']:,.2f}</td><td class="num">${r['ss']:,.2f}</td><td class="num">${r['combined_income']:,.2f}</td><td class="num">${r['tier1_taxable']:,.2f}</td><td class="num">${r['tier2_taxable']:,.2f}</td><td class="num">{cap_note}</td><td class="num highlight-cell">${r['taxable_ss']:,.2f} ({r['pct_taxable']:.1f}%)</td><td class="num green-cell">${r['non_taxable_ss']:,.2f}</td></tr>"
        ded_rows += f"<tr><td><strong>{age_badge}</strong></td><td class="num highlight-cell">${r['fed_agi']:,.2f}</td><td class="num">${r['base_ded']:,.2f}</td><td class="num">${r['age_ded']:,.2f}</td><td class="num">${r['max_enhanced']:,.2f}</td><td class="num red-cell">-${r['phaseout_reduction']:,.2f}</td><td class="num">${r['enhanced_ded']:,.2f}</td><td class="num green-cell">${r['total_ded']:,.2f}</td><td class="num">${r['fed_taxable_income']:,.2f}</td><td class="num tax-cell">${r['fed_tax']:,.2f}</td></tr>"
        ca_rows += f"<tr><td><strong>{age_badge}</strong></td><td class="num">${r['401k']:,.2f}</td><td class="num green-cell">$0.00 (Exempt)</td><td class="num highlight-cell">${r['ca_agi']:,.2f}</td><td class="num">${r['ca_deduction']:,.2f}</td><td class="num">${r['ca_taxable_income']:,.2f}</td><td class="num">${r['ca_tax']:,.2f}</td><td class="num">{r['ca_top_bracket']:.1f}%</td><td class="num tax-cell">${r['total_combined_tax']:,.2f}</td><td class="num">{r['combined_effective_rate']:.2f}%</td></tr>"

    # Add Summary Rows
    ss_rows += f"<tr class="summary-row"><td><strong>Total / Sum</strong></td><td class="num">${tot_401k:,.2f}</td><td class="num">${tot_ss:,.2f}</td><td class="num">${tot_combined_inc:,.2f}</td><td class="num">${tot_tier1:,.2f}</td><td class="num">${tot_tier2:,.2f}</td><td class="num">—</td><td class="num highlight-cell">${tot_taxable_ss:,.2f}</td><td class="num green-cell">${tot_non_taxable_ss:,.2f}</td></tr>"
    ded_rows += f"<tr class="summary-row"><td><strong>Total / Sum</strong></td><td class="num highlight-cell">${tot_fed_agi:,.2f}</td><td class="num">${tot_base_ded:,.2f}</td><td class="num">${tot_age_ded:,.2f}</td><td class="num">${tot_max_enh:,.2f}</td><td class="num red-cell">-${tot_phaseout:,.2f}</td><td class="num">${tot_enh_ded:,.2f}</td><td class="num green-cell">${tot_total_ded:,.2f}</td><td class="num">${tot_fed_taxable:,.2f}</td><td class="num tax-cell">${tot_fed_tax:,.2f}</td></tr>"
    ca_rows += f"<tr class="summary-row"><td><strong>Total / Average</strong></td><td class="num">${tot_401k:,.2f}</td><td class="num green-cell">$0.00</td><td class="num highlight-cell">${tot_ca_agi:,.2f}</td><td class="num">${tot_ca_ded:,.2f}</td><td class="num">${tot_ca_taxable:,.2f}</td><td class="num">${tot_ca_tax:,.2f}</td><td class="num">—</td><td class="num tax-cell">${tot_combined_tax:,.2f}</td><td class="num">{avg_effective_rate:.2f}% (Avg)</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>2026 Tax Estimate for {client_name}</title>
    <style>
        body {{ font-family: system-ui, sans-serif; background: #000000; color: #f8fafc; padding: 2rem; }}
        .container {{ max-width: 1300px; margin: 0 auto; background: #111827; padding: 2rem; border-radius: 12px; border: 1px solid #1f2937; }}
        header {{ background: #0f172a; padding: 2.5rem 2rem; border-radius: 12px; border: 1px solid #1f2937; margin-bottom: 2rem; text-align: center; display: block; }}
        h1 {{ margin: 0 0 0.4rem 0; color: #ffffff; font-size: 2rem; }}
        p {{ color: #94a3b8; font-size: 1rem; margin: 0; }}
        .client-badge {{ background: #172554; border: 1px solid #3b82f6; color: #93c5fd; padding: 0.85rem 2rem; border-radius: 8px; font-size: 1.25rem; font-weight: 700; display: inline-block; margin-bottom: 1rem; }}
        h2 {{ font-size: 1.25rem; color: #ffffff; margin: 1.5rem 0 0.75rem; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 2rem; }}
        th, td {{ padding: 0.9rem; border-bottom: 1px solid #1f2937; font-size: 0.86rem; }}
        th {{ background: #1e293b; color: #f8fafc; font-weight: 600; text-transform: uppercase; font-size: 0.73rem; }}
        th.num, td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
        .highlight-cell {{ color: #60a5fa; font-weight: 600; }}
        .green-cell {{ color: #4ade80; font-weight: 600; }}
        .red-cell {{ color: #f87171; font-weight: 600; }}
        .tax-cell {{ background: #451a03; color: #fde68a; font-weight: 700; }}
        tr.summary-row {{ background-color: #1e293b; font-weight: 700; border-top: 2px solid #3b82f6; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="client-badge">Client: {client_name}</div>
            <h1>2026 Federal &amp; California State Tax Breakdown</h1>
            <p>Source file: <strong>income.txt</strong></p>
        </header>

        <h2>1. Federal Social Security Taxation Breakdown</h2>
        <table>
            <thead><tr><th>Age Group</th><th class="num">401(k)</th><th class="num">Gross SS</th><th class="num">Combined Income</th><th class="num">Tier 1 (50%)</th><th class="num">Tier 2 (85%)</th><th class="num">85% Cap?</th><th class="num">Taxable SS</th><th class="num">Tax-Free SS</th></tr></thead>
            <tbody>{ss_rows}</tbody>
        </table>

        <h2>2. Federal Tax Deductions &amp; Federal Tax</h2>
        <table>
            <thead><tr><th>Age Group</th><th class="num">Fed AGI</th><th class="num">Base Ded</th><th class="num">Age 65+</th><th class="num">Max Senior</th><th class="num">Phase-Out</th><th class="num">Net Senior</th><th class="num">Total Ded</th><th class="num">Taxable Inc</th><th class="num">Federal Tax</th></tr></thead>
            <tbody>{ded_rows}</tbody>
        </table>

        <h2>3. California State Tax Section</h2>
        <table>
            <thead><tr><th>Age Group</th><th class="num">401(k)</th><th class="num">CA SS</th><th class="num">CA AGI</th><th class="num">CA Ded</th><th class="num">CA Taxable</th><th class="num">CA Tax</th><th class="num">CA Top</th><th class="num">Total Combined Tax</th><th class="num">Combined Effective Rate</th></tr></thead>
            <tbody>{ca_rows}</tbody>
        </table>
    </div>
</body>
</html>
"""

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated {output_html} with summary rows.")

if __name__ == "__main__":
    generate_html()
