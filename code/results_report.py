"""Make a concise evidence report and SVG chart from completed actual runs."""

import argparse
from collections import Counter
import html
import json
from pathlib import Path

from audit_engine import audit
from experiments import summarize


COLORS = {"bau": "#64748b", "staff": "#6b4fa2", "staff_hotline": "#168473",
          "ops_500k": "#6b4fa2", "plan_950k": "#168473"}
COLORS.update({"keep_950k_week5": "#6b4fa2", "rapid_130k_week4": "#168473"})
COLORS["actual_plan"] = "#168473"


def generate(output):
    output = Path(output)
    summarize(output)
    results = json.loads((output / "comparison.json").read_text())["results"]
    if not results:
        raise ValueError("No completed actual runs to report")
    lines = ["# Live action comparison", "", "Development evidence: synthetic behavior, one or more matched seeds. No company decision is selected or locked.", "",
             "| Case | Seed | Voices | Weeks | Cost | Business satisfaction /5 | Accountant satisfaction /5 | Max support hours |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in results:
        lines.append(f"| {r['case']} | {r['seed']} | {r['profiles']} | {r['weeks']} | ${r['cost_usd']:,.0f} | {r['business_satisfaction']:.2f} | {r['accountant_satisfaction']:.2f} | {r['goal_4']:.2f} |")
    lines += ["", "Satisfaction is a population-weighted average of LLM 1–5 ratings, not the percentage of happy customers. Support timing comes from the documented workload assumptions; customer choices remain LLM-generated.", "",
              "## Integrity and disagreement", ""]
    baseline_by_seed = {}
    for r in results:
        folder = output / r["case"] / f"seed_{r['seed']}"
        result, weekly, manifest = audit(folder)
        starts = result["baseline_satisfaction_by_voice"]
        if r["seed"] in baseline_by_seed and starts != baseline_by_seed[r["seed"]]:
            raise ValueError("Matched cases have different baseline responses")
        baseline_by_seed[r["seed"]] = starts
        final = [row for row in weekly if row["week"] == r["weeks"]]
        headlines = dict(Counter(row["status"] for row in final))
        effects = Counter(i["effect"] for row in weekly for i in row["influences"])
        lines.append(f"- **{r['case']}, seed {r['seed']}:** {result['valid_calls']} valid calls; {result['repair_attempts']} saved repair attempts; {result['messages']} messages, {result['delivered_messages']} delivered within the run. Headlines: {headlines}. Self-reported message effects: {dict(effects)}.")
        lines.append(f"  Integrity checks passed: recipient routing, release timing, raw-response traceability, weighted aggregation. These checks establish execution integrity, not calibrated behavioral accuracy.")
    lines += ["", "## Representative evidence (all accountants at the last week)", ""]
    for r in results:
        folder = output / r["case"] / f"seed_{r['seed']}"
        profiles = {p["id"]: p for p in json.loads((folder / "manifest.json").read_text())["profiles"]}
        for row in (json.loads(line) for line in (folder / "weekly.jsonl").read_text().splitlines()):
            if row["week"] == r["weeks"] and profiles[row["persona"]]["represented_accountants"]:
                lines.append(f"- {r['case']}/{r['seed']} **{row['persona']}**: {row['statement']} (call `{row['call']}`)")
    pricing = any(r["case"] == "plan_950k" for r in results)
    incident = any(r["case"] == "rapid_130k_week4" for r in results)
    if pricing:
        lines += ["", "## Incremental price-policy comparison", "",
            "Operational wording is shared between the active branches. Pricing terms and their explicit sentence differ. This is a package comparison, not an estimate of pure price elasticity.", "",
            "| Seed | Extra cost | Renewal difference, pp | Churn difference, pp | Accountant rating difference |",
            "|---|---:|---:|---:|---:|"]
        for seed in sorted({r["seed"] for r in results}):
            pair = {r["case"]: r for r in results if r["seed"] == seed}
            if not {"ops_500k", "plan_950k"} <= pair.keys():
                continue
            low, high = pair["ops_500k"], pair["plan_950k"]
            if high["goal_1"] is not None and high["goal_2"] is not None:
                lines.append(f"| {seed} | ${high['cost_usd']-low['cost_usd']:,.0f} | {high['goal_1']-low['goal_1']:+.2f} | {high['goal_2']-low['goal_2']:+.2f} | {high['accountant_satisfaction']-low['accountant_satisfaction']:+.2f} |")
        sensitivity_path = output / "support_sensitivity.json"
        if sensitivity_path.exists():
            sensitivity = json.loads(sensitivity_path.read_text())
            lines += ["", "## Support assumption check", "", sensitivity["finding"], "",
                      "This is a mechanical sensitivity check with baseline demand held fixed. Persona reactions were not rerun under these variants.", "",
                      "| Assumed baseline staff | Modeled year-end hours, staff + testing |", "|---|---:|"]
            lines += [f"| {row['assumed_baseline_staff']} | {row['year_end_response_hours_at_unchanged_baseline_demand']:.2f} |" for row in sensitivity["rows"]]
    comparison_limit = ("The pricing comparison holds operational wording constant but changes pricing terms and their wording. "
        "Inspect the incremental concession separately by seed; no calibrated revenue or ROI estimate follows from these synthetic fractions."
        if pricing else "The incident branches differ in effective week, action mix and customer wording. This tests complete response packages; one seed and six voices cannot establish causal effects or population benefit."
        if incident else "BAU versus an action package includes both communication and operations. Staff versus staff+hotline holds message wording constant, but one seed cannot establish a causal effect or confidence interval.")
    lines += ["", "## Limits and next experiment", "",
        "Short runs cannot evaluate weeks 9–10 renewals; under four weeks they cannot calculate the monthly churn proxy. A six-voice subset is a mechanism check, not a population forecast. Even the full 24-profile weighted run uses assumed attitude frequencies, not observed customer research.", "",
        comparison_limit + " Message influence categories are model self-reports. Do not select a winner from tiny rating changes.", "",
        "Next: inspect counterexamples and sensitive cohorts; use the same profiles and actual events to compare a price/reliability package, a partner-first package, and BAU over ten weeks with two seeds. Then run the exact locked decisions in all five final runs."]
    (output / "RESULTS.md").write_text("\n".join(lines) + "\n")
    # Compact standard SVG bar chart, with fixed 0–5 rating scale.
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="420" viewBox="0 0 900 420">',
             '<rect width="900" height="420" fill="#fafaf7"/>',
             '<g font-family="Arial,sans-serif" fill="#202621">',
             '<text x="35" y="35" font-size="22">Actual development runs: weighted satisfaction</text>',
             '<text x="35" y="58" font-size="13">LLM ratings, scale 1–5; synthetic judgments, not measured customer survey results</text>']
    for value in range(6):
        y = 305 - value * 42
        parts.append(f'<line x1="60" x2="860" y1="{y}" y2="{y}" stroke="#dce2db"/><text x="40" y="{y+5}" font-size="12">{value}</text>')
    width = 760 / len(results)
    for index, r in enumerate(results):
        x = 75 + index * width
        color = COLORS[r["case"]]
        for offset, key, opacity in ((0, "business_satisfaction", "1"), (45, "accountant_satisfaction", ".5")):
            value = r[key]
            height = value * 42
            parts.append(f'<rect x="{x+offset}" y="{305-height}" width="34" height="{height}" fill="{color}" opacity="{opacity}"/><text x="{x+offset+17}" y="{296-height}" text-anchor="middle" font-size="12">{value:.2f}</text>')
        label = html.escape(f"{r['case']} · seed {r['seed']}")
        parts.append(f'<text x="{x+40}" y="330" text-anchor="middle" font-size="12">{label}</text><text x="{x+40}" y="349" text-anchor="middle" font-size="12">{r["profiles"]} voices · {r["weeks"]} weeks</text>')
    parts += ['<text x="60" y="386" font-size="13">Solid bar: business customers   ·   Lighter bar: partner accountants</text>', '</g></svg>']
    (output / "satisfaction.svg").write_text("\n".join(parts))
    print(f"Report: {(output / 'RESULTS.md').resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output")
    args = parser.parse_args()
    generate(args.output)
