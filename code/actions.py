"""Strict menu validation and transparent world mechanics, never customer choices."""

from datetime import date, timedelta

MENU = {
    "renewal_price": {"label": "Renewal price for plans renewing in weeks 9 and 10", "levels": {"today's price": 900000, "+10%": 450000, "+30%": -450000}},
    "renewal_free": {"label": "Two months free on annual renewal, up to 2,000 customers", "cost": 350000, "cap": 2000},
    "commission": {"label": "Accountant commission 10% → 20%, 6 months", "cost": 300000, "weeks": 26},
    "office_pro": {"label": "Free Pro for each partner accountant office, one year", "cost": 150000, "weeks": 52},
    "service_credit": {"label": "One free month for incident-hit customers, up to 2,000", "cost": 200000, "cap": 2000},
    "support_staff": {"label": "40 extra year-end support staff for 6 weeks", "cost": 300000, "weeks": 6},
    "hotline": {"label": "Dedicated accountant phone line for 6 weeks", "cost": 100000, "weeks": 6},
    "outside_testing": {"label": "Outside year-end update testing team", "cost": 200000},
    "feature_freeze": {"label": "6-week feature freeze for reliability; reconciliation slips to March", "cost": 0, "weeks": 6},
    "guides": {"label": "Webinars and guides on January changes", "cost": 50000},
    "status_alerts": {"label": "Public status page, incident reports and accountant text alerts", "cost": 30000},
}

ALIASES = {
    "two months free on an annual renewal, for a group you define (up to 2,000 customers)": "renewal_free",
    "partner accountants: commission 10% → 20% on renewing and new clients for 6 months": "commission",
    "free pro plan for every partner accountant's own office for a year": "office_pro",
    "service credit: one month free for customers hit by an incident (up to 2,000 customers)": "service_credit",
    "year-end support: +40 staff for 6 weeks": "support_staff",
    "a dedicated phone line for accountants for 6 weeks": "hotline",
    "an outside testing team for the year-end update": "outside_testing",
    "feature freeze: all engineers on reliability for 6 weeks (the new reconciliation tool, promised for december, slips to march)": "feature_freeze",
    "public status page with incident reports, and text alerts to accountants": "status_alerts",
}
for key, spec in MENU.items():
    ALIASES[spec["label"].lower()] = key
    ALIASES[key] = key
ALIASES["webinars and guides on the january changes"] = "guides"

ASSUMPTIONS = {
    "baseline_support_staff": 100,
    "baseline_weekly_support_contacts": 0.02,
    "staff_productivity": 1.0,
    "testing_workload_factor": 0.9,
    "freeze_workload_factor": 0.8,
    "hotline_priority_share": 0.10,
    "note": "Uncalibrated support/reliability assumptions. No automatic trust or retention benefit. Test alternative settings.",
}


def action_key(action):
    name = str(action.get("action", "")).strip().lower()
    if name not in ALIASES:
        raise ValueError(f"Unknown action: {name}")
    return ALIASES[name]


def action_cost(action):
    key = action_key(action)
    level = str(action.get("level", "")).strip()
    if key == "renewal_price":
        aliases = {"0%": "today's price", "today’s price": "today's price", "today's price: $0.9m": "today's price", "+10% instead of +20%": "+10%", "+10% instead of +20%: $0.45m": "+10%", "+30%: earns $0.45m": "+30%"}
        level = aliases.get(level.lower(), level)
        if level not in MENU[key]["levels"]:
            raise ValueError("Renewal price level must be today's price, +10%, or +30%")
        return MENU[key]["levels"][level]
    if level != "on":
        raise ValueError(f"{key} has one level: on")
    return MENU[key]["cost"]


def matches(persona, selector):
    if not selector:
        return True
    if "ids" in selector and persona["id"] not in selector["ids"]:
        return False
    if "groups" in selector and persona["group"] not in selector["groups"]:
        return False
    return all(persona.get(key) == value for key, value in selector.get("where", {}).items())


def selector_for(decision, selectors, index):
    name = str(decision["target"]).strip().lower()
    if name in ("everyone", "all", "all customers"):
        return {}
    groups = {"business owners": "business owners", "in-house bookkeepers": "in-house bookkeepers",
              "partner accountants": "partner accountants"}
    if name in groups and str(index) not in selectors:
        return {"groups": [groups[name]]}
    if str(index) not in selectors:
        raise ValueError(f"Decision {index}: custom target needs an explicit selector, not fuzzy text matching")
    return selectors[str(index)]


def message_reaches(persona, decision, selectors, index):
    if not matches(persona, selector_for(decision, selectors, index)):
        return False
    channels = decision["channels"] if isinstance(decision["channels"], list) else [decision["channels"]]
    role_channels = []
    for channel in channels:
        name = str(channel).lower().replace("_", " ")
        if name in ("email", "in-app", "in app"):
            return True
        if "owner message" in name:
            role_channels.append("business owners")
        if "bookkeeper message" in name:
            role_channels.append("in-house bookkeepers")
        if "accountant message" in name:
            role_channels.append("partner accountants")
    return not role_channels or persona["group"] in role_channels


def validate_plan(decisions, profiles, selectors=None, require_two=False):
    selectors = selectors or {}
    if len(decisions) > 2 or (require_two and len(decisions) != 2):
        raise ValueError("A final plan requires exactly two decision packages")
    total = 0
    seen = set()
    for index, decision in enumerate(decisions, 1):
        if type(decision.get("week")) is not int or not 1 <= decision["week"] <= 10:
            raise ValueError("Decision week must be an integer from 1 to 10")
        if not isinstance(decision.get("message"), str) or not 0 < len(decision["message"]) <= 600:
            raise ValueError("Decision message must contain 1–600 characters")
        why = decision.get("why", "")
        lines = why if isinstance(why, list) else str(why).splitlines()
        if len(lines) != 3 or any(not str(line).strip() for line in lines):
            raise ValueError("Decision rationale requires exactly three non-empty lines")
        if not decision.get("channels") or not decision.get("target"):
            raise ValueError("Decision needs target and channels")
        actions = decision.get("actions", [])
        if not 1 <= len(actions) <= 3:
            raise ValueError("Each package needs one to three actions")
        selector = selector_for(decision, selectors, index)
        target = [p for p in profiles if matches(p, selector)]
        if not target:
            raise ValueError("Target selector reaches no profile")
        if not any(message_reaches(p, decision, selectors, index) for p in profiles):
            raise ValueError("Message channels and target reach no profile")
        for action in actions:
            key = action_key(action)
            if key in seen:
                raise ValueError("Duplicate actions across packages are ambiguous; use one activation")
            seen.add(key)
            total += action_cost(action)
            if key in ("renewal_free", "service_credit"):
                number = sum(sum(p.get("renewal_counts", {}).values()) if key == "renewal_free" else p["represented_businesses"] for p in target)
                if number > MENU[key]["cap"]:
                    raise ValueError(f"{key} target exceeds 2,000; narrow the selector before running")
    if total > 1500000:
        raise ValueError("Combined decisions exceed $1.5M")
    return total


def active_actions(decisions, week):
    active = []
    for index, decision in enumerate(decisions, 1):
        if week < decision["week"]:
            continue
        for action in decision["actions"]:
            key = action_key(action)
            duration = MENU[key].get("weeks", 10)
            if week < decision["week"] + duration:
                active.append((key, action, decision, index))
    return active


def offers_for(persona, decisions, selectors, week, affected=False):
    offers = []
    for key, action, decision, index in active_actions(decisions, week):
        # Internal operations are not automatic customer knowledge. Their exact
        # announced wording and any experienced service changes are separate.
        if key in ("outside_testing", "feature_freeze", "support_staff"):
            continue
        if not matches(persona, selector_for(decision, selectors, index)):
            continue
        if key == "service_credit" and not affected:
            continue
        if key in ("commission", "office_pro", "hotline") and not persona["represented_accountants"]:
            continue
        if key in ("renewal_price", "renewal_free") and not persona["represented_businesses"]:
            continue
        offers.append({"action": key, "level": action["level"], "description": MENU[key]["label"],
                       "source": f"decision-{index}", "effective_week": decision["week"]})
    return offers


def support_week(week, contact_counts, decisions, assumptions, backlog=None):
    """Baseline-anchored workload proxy; no invented accumulating queue capacity.

    `backlog` now carries the immutable baseline demand reference for compatible
    callers. The historical 3/8-hour references anchor normal and year-end service.
    """
    reference = (backlog or {}).get("reference_contacts")
    if reference is None:
        reference = {role: max(contact_counts[role], assumptions["baseline_weekly_support_contacts"] * population)
                     for role, population in (("business", 42000), ("accountant", 3100))}
    reference_total = sum(reference.values())
    active = {key for key, *_ in active_actions(decisions, week)}
    staff = 1 + (40 * assumptions["staff_productivity"] / assumptions["baseline_support_staff"] if "support_staff" in active else 0)
    original_shares = {role: reference[role] / reference_total for role in reference}
    shares = dict(original_shares)
    if "hotline" in active:
        if assumptions["hotline_priority_share"] >= shares["business"]:
            raise ValueError("Hotline share exceeds baseline business capacity; revise the assumption")
        shares["accountant"] += assumptions["hotline_priority_share"]
        shares["business"] -= assumptions["hotline_priority_share"]
    factor = 1.0
    if week >= 9:
        if "outside_testing" in active:
            factor *= assumptions["testing_workload_factor"]
        if "feature_freeze" in active:
            factor *= assumptions["freeze_workload_factor"]
    days = []
    for offset in range(7):
        day = date(2026, 11, 2) + timedelta(days=(week - 1) * 7 + offset)
        row = {"week": week, "date": day.isoformat(), "excluded_from_goal": day.month == 1 and day.day in (4, 5),
               "model": "baseline_anchored_workload_proxy"}
        seasonal = 3.0 + (5.0 * factor if week >= 9 else 0.0)
        for role in ("business", "accountant"):
            demand_ratio = max(1.0, contact_counts[role] / reference[role])
            priority_ratio = shares[role] / original_shares[role]
            row[role + "_hours"] = seasonal * demand_ratio / (staff * priority_ratio)
            row[role + "_demand_ratio"] = demand_ratio
        row["mean_hours"] = (row["business_hours"] * 42000 + row["accountant_hours"] * 3100) / 45100
        days.append(row)
    return days, {"reference_contacts": reference}
