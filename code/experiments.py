"""Compare BAU, extra staff, and staff+hotline using matched profiles and seeds.

All branches are development experiments, never locked dashboard decisions.
"""

import argparse
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from api_client import DEFAULT_MODEL, create_client
from actions import action_key, validate_plan
from engine import execute_run, load_inputs, write_json


def candidates(week):
    common = {"week": week, "target": "Everyone", "channels": ["email", "in-app"],
        "message": "We are expanding year-end support. Please contact support with account questions. Data export remains free.",
        "why": "Test additional support capacity.\nCompare accountant access with the same message.\nReview costs and effects before selecting a plan."}
    staff = {**common, "actions": [{"action": "support_staff", "level": "on"}]}
    combined = {**common, "actions": [{"action": "support_staff", "level": "on"}, {"action": "hotline", "level": "on"}]}
    return {"bau": [], "staff": [staff], "staff_hotline": [combined]}


def pricing_candidates(week):
    """Test the approved draft against its operational-only alternative.

    Keep common operational wording identical. The pricing sentence and explicit
    offer differ as part of the customer-facing pricing policy being compared.
    These are prospective development branches, not dashboard locks.
    """
    document = json.loads((Path(__file__).parent / "decisions/first_package_for_review.json").read_text())
    proposal = copy.deepcopy(document["run_decisions"][0])
    proposal["week"] = week
    operations = copy.deepcopy(proposal)
    operations["actions"] = [a for a in operations["actions"] if action_key(a) != "renewal_price"]
    common = "From today, 40 extra support staff are available for six weeks. An outside team is testing our January 1 update. Data export remains free."
    if week == 5:
        # Keep the exact reviewed week-5 wording, including its coverage end date.
        common = document["run_decisions"][0]["message"].split(". ", 1)[1]
    proposal["message"] = "For annual plans renewing in late December or early January, the increase will be 10% instead of 20%. " + common
    operations["message"] = "For annual plans renewing in late December or early January, the previously planned 20% increase remains in place. " + common
    operations["why"] = "Test support and testing with standard renewal pricing.\nPreserve $1M for other needs.\nCompare renewal behavior against the added $450k price concession."
    return {"bau": [], "ops_500k": [operations], "plan_950k": [proposal]}


def incident_candidates():
    """Week-3 payroll report: compare delay, BAU and a modest week-4 response."""
    proposed = json.loads((Path(__file__).parent / "decisions/first_package_for_review.json").read_text())["run_decisions"]
    rapid = {"week": 4, "target": "Everyone", "actions": [
        {"action": "status_alerts", "level": "on"}, {"action": "hotline", "level": "on"}],
        "message": "Some Quillbook payroll deposits arrived hours late, and some employees were paid a day late. No money was lost. Our engineers are working with our partner bank. The cause, scale and recurrence risk remain unknown. We are expanding public incident reports and sending accountant text alerts, with a dedicated accountant phone line for six weeks. We will publish new confirmed information as it becomes available. Data export remains free.",
        "channels": ["Email", "In-app"],
        "why": "Communicate known facts and uncertainty without blaming the bank.\nGive accountants a direct channel to help clients and challenge rumors.\nKeep $1.37M and the second decision available for new evidence and January readiness."}
    return {"bau": [], "keep_950k_week5": copy.deepcopy(proposed), "rapid_130k_week4": [rapid]}


def run_comparisons(output, cases, seeds, profiles, links, events, *, weeks, concurrency, parallel_cases, client):
    """Fill freed slots across seeds while preserving each run's weekly order."""
    jobs = [(seed, name, decisions) for seed in seeds for name, decisions in cases.items()]

    def run_case(job):
        seed, name, decisions = job
        execute_run(Path(output) / name / f"seed_{seed}", profiles, links, events, decisions, {},
                    kind="plan" if decisions else "nodecision", seed=seed, model=DEFAULT_MODEL,
                    end_week=weeks, concurrency=concurrency, client=client, probes=False)

    with ThreadPoolExecutor(max_workers=parallel_cases) as pool:
        list(pool.map(run_case, jobs))


def summarize(output):
    output = Path(output)
    rows = []
    for completion in sorted(output.glob("*/*/completion.json")):
        if not json.loads(completion.read_text()).get("complete"):
            continue
        folder = completion.parent
        manifest = json.loads((folder / "manifest.json").read_text())
        metric = json.loads((folder / "metrics.json").read_text())
        weekly = [json.loads(x) for x in (folder / "weekly.jsonl").read_text().splitlines()]
        profiles = {p["id"]: p for p in manifest["profiles"]}
        final = [r for r in weekly if r["week"] == manifest["end_week"]]
        total = sum(p["represented_businesses"] for p in profiles.values())
        accountants = sum(p["represented_accountants"] for p in profiles.values())
        rows.append({"case": folder.parent.name, "seed": manifest["seed"], "profiles": len(profiles),
            "weeks": manifest["end_week"], "cost_usd": metric["cost_usd"],
            "business_satisfaction": sum(profiles[r["persona"]]["represented_businesses"] * r["satisfaction"] for r in final) / total,
            "accountant_satisfaction": sum(profiles[r["persona"]]["represented_accountants"] * r["satisfaction"] for r in final) / accountants,
            "goal_1": metric["goal_1"], "goal_2": metric["goal_2"], "goal_3": metric["goal_3"], "goal_4": metric["goal_4"]})
    pricing = any(r["case"] == "plan_950k" for r in rows)
    incident = any(r["case"] == "rapid_130k_week4" for r in rows)
    actual = any(r["case"] == "actual_plan" for r in rows)
    wording = ("Active pricing branches share operational wording; pricing terms and their sentence differ. This is a policy-package comparison, not pure price elasticity. "
               if pricing else "Incident branches differ in timing, actions and customer wording; compare whole packages, not isolated action effects. "
               if incident else "Actual-plan branch uses the exact supplied dashboard decisions; the control follows BAU. "
               if actual else "Active support branches share the same customer message. ")
    write_json(output / "comparison.json", {"development": True, "results": rows,
        "interpretation": "Compare within seed; report variation across seeds, not confidence intervals. " + wording +
        "Partial timelines cannot evaluate all board goals. These are development branches, not proof of dashboard locks or final plan results."})
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "run", "summarize"))
    parser.add_argument("--events")
    parser.add_argument("--comparison", choices=("support", "pricing", "week3", "actual"), default="support")
    parser.add_argument("--weeks", type=int, choices=range(1, 11), default=3)
    parser.add_argument("--action-week", type=int, default=1)
    parser.add_argument("--seeds", default="42,43")
    parser.add_argument("--ids", help="Deprecated: persona subsets are disabled; use all 24")
    parser.add_argument("--concurrency", type=int, default=24)
    parser.add_argument("--parallel-cases", type=int, choices=(1, 2, 3), default=3,
                        help="Parallel development branches; each retains its own sequential weeks")
    parser.add_argument("--output", default="output/action_experiments")
    args = parser.parse_args()
    if args.command == "summarize":
        summarize(args.output)
    else:
        profiles, links, events, _, _ = load_inputs(args.events)
        if args.ids:
            raise SystemExit("Persona subsets are disabled by user instruction; run all 24 profiles")
        if not 1 <= args.action_week <= args.weeks:
            raise SystemExit("Action week must fall inside the experiment")
        seeds = [int(s) for s in args.seeds.split(",")]
        actual_plan = json.loads((Path(__file__).parent / "decisions/locked_plan.json").read_text())["run_decisions"] if args.comparison == "actual" else None
        cases = ({"bau": [], "actual_plan": actual_plan} if args.comparison == "actual" else
                 incident_candidates() if args.comparison == "week3" else
                 pricing_candidates(args.action_week) if args.comparison == "pricing" else candidates(args.action_week))
        costs = {name: validate_plan(decisions, profiles) for name, decisions in cases.items()}
        if args.command == "validate":
            print(json.dumps({"profiles": len(profiles), "weeks": args.weeks, "cases": list(cases), "costs_usd": costs,
                "seeds": seeds, "requests_upper_bound_before_repairs": len(profiles) * (1 + 2 * args.weeks) * len(cases) * len(seeds),
                "development_only": True, "same_operational_wording": args.comparison != "week3",
                "price_wording_differs": args.comparison == "pricing"}, indent=2))
        else:
            with create_client() as client:
                run_comparisons(args.output, cases, seeds, profiles, links, events,
                                weeks=args.weeks, concurrency=args.concurrency,
                                parallel_cases=args.parallel_cases, client=client)
            summarize(args.output)
