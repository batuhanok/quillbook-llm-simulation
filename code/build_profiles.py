"""Build explicitly synthetic profiles, reconciled weights, and relationship links."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Population totals come from the dossier; all within-cell assignments are assumptions.
BUSINESSES = [
    ("O01", "construction", "micro", 4200, True, "tight cash flow; dependable payday matters"),
    ("O02", "restaurants", "small", 2400, True, "seasonal workload; little time to chase support"),
    ("O03", "retail", "micro", 4300, False, "low technical comfort; values familiar workflows"),
    ("O04", "logistics", "small", 2300, True, "previous rival outage; wants evidence of reliability"),
    ("O05", "services", "micro", 4300, False, "technically comfortable; willing to compare rivals"),
    ("O06", "construction", "medium", 1500, True, "has IT help; cares about auditability and deadlines"),
    ("O07", "restaurants", "micro", 4000, False, "uses Quillbook for bookkeeping; payroll elsewhere; trusts accountant"),
    ("O08", "services", "small", 2400, False, "high invoice volume; awaiting reconciliation feature"),
    ("B01", "retail", "small", 2500, True, "frequent support contact; owner pressures costs"),
    ("B02", "logistics", "medium", 1400, False, "multi-location bookkeeping; payroll outside Quillbook"),
    ("B03", "services", "micro", 3200, False, "sole finance worker; limited migration time"),
    ("B04", "construction", "small", 2500, True, "detailed process controls; asks for testing evidence"),
    ("B05", "restaurants", "medium", 1300, True, "past filing problem; wants accountable resolution"),
    ("B06", "services", "small", 1300, False, "reconciliation tool expected; values honest commitments"),
    ("B07", "retail", "micro", 3100, False, "researches rivals; fair and clear pricing matters"),
    ("B08", "logistics", "small", 1300, True, "works with external accountant; balances conflicting advice"),
]
PRACTICES = [
    ("A01", 10, 500, 2, "microbusiness specialist; hands-on support"),
    ("A02", 20, 500, 2, "restaurant specialist; payroll concentration"),
    ("A03", 35, 400, 3, "construction specialist; compliance cautious"),
    ("A04", 50, 400, 4, "mixed sectors; experienced rival user"),
    ("A05", 75, 400, 6, "retail specialist; clients under cash pressure"),
    ("A06", 100, 300, 4, "services specialist; technology confident"),
    ("A07", 125, 300, 24, "large logistics practice; influential professional network"),
    ("A08", 150, 300, 32, "large mixed practice; weighs reputation against commercial incentives"),
]

# User-authorized fictional role/workflow enrichment, not observed customer data.
# No new demographics, legal facts, portfolio counts, or prescribed reactions.
BACKGROUND_DETAILS = {
    "O01": ("owner-operator", "Balances construction work, supplier payments and payroll preparation. Cash pressure makes both dependable payday and the software bill relevant; a convenient workaround may still consume time needed elsewhere."),
    "O02": ("restaurant owner-operator", "Balances service shifts and seasonal staffing with checking the books. Chasing a support answer competes with running the restaurant; changing software also requires time away from operations."),
    "O03": ("retail owner-operator", "Uses familiar screens to check invoices and balances alongside running the shop. An unfamiliar workflow can mean extra checking; continuity and the cost of staying both matter when considering alternatives."),
    "O04": ("logistics business owner", "Coordinates operating commitments with bookkeeping and payroll. A previous rival outage is part of their own history, not evidence about Quillbook; reliability claims and the practical work of migration can pull in different directions."),
    "O05": ("services business owner", "Handles client work alongside the books and is comfortable comparing software workflows. Time saved, subscription value and the effort of moving records are competing considerations rather than a predetermined reason to switch."),
    "O06": ("construction company owner", "Can involve internal IT help when checking a software problem or assessing migration. Needs understandable records and deadline visibility; technical help does not remove disruption or make vendor promises verified facts."),
    "O07": ("restaurant owner-operator", "Uses Quillbook for the books while payroll is handled elsewhere. Values accountant advice but must weigh it against work in the restaurant; a Quillbook payroll incident would not directly delay their own payroll through that product."),
    "O08": ("services business owner", "Frequent invoices make matching payments and reconciling records a recurring task. The expected reconciliation feature matters to workflow planning, alongside the reliability and cost of the tools already in use."),
    "B01": ("in-house bookkeeper", "Handles retail bookkeeping and payroll preparation while explaining software costs to the owner. Support contact takes time from routine work; an option that simplifies their day may still need the owner's spending approval."),
    "B02": ("in-house bookkeeper coordinating locations", "Collects records across locations and checks that bookkeeping stays consistent. Payroll is outside Quillbook, so bookkeeping disruption and payroll-system disruption are distinct exposures; migration also requires coordinating other people's records."),
    "B03": ("office administrator with in-house bookkeeping duties", "Combines the books with office administration in a micro services firm rather than belonging to a separate finance department. As the sole finance worker, must fit corrections or migration into existing work; lack of time need not imply satisfaction."),
    "B04": ("in-house bookkeeper responsible for process checks", "Maintains construction bookkeeping and payroll checks and prepares information for the owner. Can ask what has actually been tested and keep track of unresolved questions; a reassuring message and usable evidence are different inputs to assess."),
    "B05": ("in-house bookkeeper handling filing preparation", "Coordinates restaurant bookkeeping and payroll records. A past filing problem provides personal context, not evidence of a new failure; evaluating explanations and practical recovery work can matter alongside the subscription bill."),
    "B06": ("in-house bookkeeper", "Organizes services bookkeeping around existing reconciliation work and the expected new tool. A changed feature commitment may alter work planning; can weigh an honest explanation against the cost of continuing manual work or migrating."),
    "B07": ("retail office administrator with in-house bookkeeping duties", "Combines day-to-day shop administration with keeping the books in a micro firm. Looks at competing software and discusses costs with the owner; headline prices, workable features and migration effort may point to different options."),
    "B08": ("in-house bookkeeper coordinating external advice", "Prepares logistics bookkeeping and payroll records and exchanges questions with connected external accountants. Must translate advice into work the business can actually perform and explain conflicting recommendations to the owner."),
    "A01": ("microbusiness accounting practitioner", "Provides hands-on help to microbusiness clients. Advice must fit clients with limited administrative time; helping them through an issue and assessing another tool both consume practice capacity."),
    "A02": ("accounting practitioner specializing in restaurants", "Works with restaurant clients and payroll-related questions. The timing of a problem can matter alongside its duration; must balance client continuity, preparation work and the credibility of information received."),
    "A03": ("accounting practitioner specializing in construction", "Helps construction clients organize records and compliance work. Wants to understand unresolved filing or payroll questions; professional concern is a reason to assess evidence, not advance knowledge that an incident will occur."),
    "A04": ("accounting practitioner serving mixed sectors", "Has experience using a rival and can compare familiar workflows across client needs. That experience supplies a reference point, not proof the rival will handle a future event better; migration still requires coordinating client records."),
    "A05": ("accounting practitioner specializing in retail", "Advises retail clients under cash pressure while keeping the practice's own finances separate from theirs. A software saving, service problem or credit can affect clients differently; recommendations need to account for the work of changing tools."),
    "A06": ("accounting practitioner specializing in services", "Is comfortable evaluating technology and explaining workflow changes to services clients. Can assess useful features alongside operational reliability; technical confidence does not establish that a company claim is correct."),
    "A07": ("accounting practitioner in a large logistics practice", "Coordinates advice in a large practice and exchanges views through the existing professional network. Reputational consequences and client continuity both matter; professional influence does not grant access to private messages or guarantee agreement."),
    "A08": ("accounting practitioner in a large mixed practice", "Balances a mixed client portfolio, practice workload and professional reputation. Commercial incentives can be considered alongside client interests; neither an incentive nor a company explanation determines the recommendation in advance."),
}


PROFILE_NAMES = {
    "O01": "Alex Morgan",
    "O02": "Jamie Rivera",
    "O03": "Taylor Brooks",
    "O04": "Jordan Ellis",
    "O05": "Casey Bennett",
    "O06": "Morgan Reed",
    "O07": "Riley Parker",
    "O08": "Avery Collins",
    "B01": "Linda Novak",
    "B02": "Jasmine Patel",
    "B03": "Sam Walker",
    "B04": "Dana Chen",
    "B05": "Robin Hughes",
    "B06": "Mei Foster",
    "B07": "Sharon Fields",
    "B08": "Cameron Lewis",
    "A01": "Carla Jimenez",
    "A02": "Bill Hartmann",
    "A03": "Nina Rossi",
    "A04": "James Whitaker",
    "A05": "Ellen Strand",
    "A06": "Omar Haddad",
    "A07": "Rachel Goldberg",
    "A08": "Sofia Lindqvist"
}

# Fictional coverage examples, not researched sector frequencies or state laws.
# Tuple: representative business needs 1099 filing; needs a wage adjustment.
# These flags are not population shares and never switch off payroll-tax changes.
JANUARY_EXPOSURE = {
    "O01": (True, False), "O02": (False, True),
    "O03": (False, True), "O04": (True, False),
    "O05": (True, False), "O06": (True, False),
    "O07": (False, True), "O08": (True, False),
    "B01": (False, True), "B02": (True, False),
    "B03": (True, False), "B04": (True, False),
    "B05": (True, True), "B06": (True, False),
    "B07": (False, True), "B08": (True, False),
}

# Stable fictional constraints; no customer search, renewal or switching is preset.
DECISION_CONTEXT = {
    "O01": "Approves the software bill while managing construction work. Low technical comfort may require help checking an export even when perceived switching friction is low; a manageable move and an effortless move are different things.",
    "O02": "Personally approves changes but must fit evaluation around restaurant service and staffing. A cheaper alternative still has to justify time spent learning it and obtaining useful support.",
    "O03": "Can authorize a change but needs help judging unfamiliar workflows. Familiarity has practical value; dissatisfaction alone does not establish that a replacement is ready or suitable.",
    "O04": "Can authorize migration and can examine a workflow comparison. The previous rival outage supplies personal context, not evidence that every rival is unreliable or that Quillbook will perform better.",
    "O05": "Can authorize changes and independently investigate export and setup requirements. Technical comfort makes investigation feasible but does not establish that a rival has been tested or chosen.",
    "O06": "Approves software choices and can ask existing IT help to assess data portability and operational checks. A technically feasible move still needs a business reason and a workable timing plan.",
    "O07": "Signs off on changes after considering accountant advice. Keeping bookkeeping and the separate payroll workflow consistent matters; trust in an accountant is influential rather than automatic agreement.",
    "O08": "Approves changes but may need help checking a replacement despite low perceived switching friction. Frequent invoice reconciliation creates a concrete comparison task; an anticipated feature is not evidence of an existing capability.",
    "B01": "Can investigate and recommend software; the owner approves the spending and move. Must explain both support time and costs, rather than treating the option easiest for the bookkeeper as already authorized.",
    "B02": "Can coordinate a replacement assessment across locations and recommend it to the owner. Must consider record handoffs and compatibility with the separate payroll provider; multiple locations do not establish multiple states.",
    "B03": "Can investigate tools but needs owner approval. High technical comfort does not create spare working time: finance duties share an office-administration role, so migration preparation competes with ordinary work.",
    "B04": "Can prepare a structured testing and migration assessment for the owner. Technical ability supports scrutiny, while established process controls make validation and handover work important before committing.",
    "B05": "Can recommend changes but needs owner approval and may require technical help. Prior filing difficulty makes usable explanations relevant; it does not prove current errors or dictate rejection of the company.",
    "B06": "Can document reconciliation workload and recommend a tool to the owner. Limited technical comfort and high switching friction constrain implementation even if feature commitments are disappointing.",
    "B07": "Can compare prices and investigate alternatives, but the owner must approve a change. Low switching friction does not prove a rival or lower tier meets the reporting needs; unknown capabilities must be checked.",
    "B08": "Can gather migration requirements and discuss them with connected accountants, then advise the owner. Must reconcile conflicting advice with the work of maintaining logistics books and payroll during a move.",
    "A01": "Can assess alternatives for clients and explain practical tradeoffs. Technical comfort and low switching friction do not grant permission to move every client; each client has its own authority and workload.",
    "A02": "Can investigate alternatives and recommend them to restaurant clients. Practice migration work competes with payroll and closing support; client urgency and readiness may differ even under the same advice.",
    "A03": "Can advise construction clients, but low technical comfort may require help validating setup details despite low perceived switching friction. Compliance caution should prompt questions rather than unsupported certainty.",
    "A04": "Can draw on established rival experience when advising clients, without claiming a fresh comparison or completed migration. Clients may weigh the same familiar alternative differently.",
    "A05": "Can compare the burden of remaining with the burden of moving cash-constrained retail clients. High switching friction limits practical options; the client's price concern is distinct from the practice's own cash position.",
    "A06": "Can investigate technical options and translate findings for services clients. Each recommendation must account for migration work and client consent; technical confidence is not verified knowledge of missing product details.",
    "A07": "Can discuss alternatives through the existing professional links, but high switching friction remains relevant to a large practice. Influence does not give access to private conversations or make clients follow advice automatically.",
    "A08": "Can evaluate alternatives and discuss commercial terms while protecting client interests. Low switching friction does not imply an immediate migration or that commission determines the recommendation; clients retain separate choices.",
}


def add_decision_context(profiles, links):
    for p in profiles:
        accountants = sorted({l["target"] for l in links if l["source"] == p["id"] and l["kind"] == "client_asks_accountant"})
        business = bool(p["represented_businesses"])
        owner = p["group"] == "business owners"
        authority = ("Approves this business's software decision; may seek advice." if owner else
                     "Operates software and recommends a change; owner approval is needed." if business else
                     "Advises client businesses; a recommendation does not authorize or execute every client's move.")
        workflows = (["bookkeeping", "invoices", "bank reconciliation"] + (["Quillbook payroll"] if p["runs_payroll"] else [])
                     if business else ["client bookkeeping continuity", "client filing preparation", "advice to linked businesses"])
        p["decision_context"] = {
            "authority": authority,
            "practical_constraints": DECISION_CONTEXT[p["id"]],
            "workflow_dependencies": workflows,
            "connected_accountants": accountants,
            "relationship_basis": "Use only existing network links and received messages. Advice can be relevant without being followed; no new relationship or adviser reputation score is implied.",
            "migration_progress": "Not preset. The LLM may choose and record investigation, evaluation, preparation, commitment, waiting or switching in weekly memories. No rival feature or completed action is assumed.",
            "renewal_evaluation": "Explain price, continuity and practical alternatives using this profile's existing traits and actual weekly information. Neither a positive statement nor dissatisfaction fixes the cohort renewal fraction.",
            "basis": "User-approved fictional distribution grounded in existing roles, technical comfort, switching friction and backstories; not a measured frequency or a predetermined choice.",
        }


def add_january_exposure(profiles, links):
    """Add explicit operational assumptions without prescribing any reaction."""
    by_id = {p["id"]: p for p in profiles}
    basis = ("User-approved fictional operational exposure design, not measured frequencies or verified state law. "
             "Describes the representative situation, not identical behavior or exposure for every cohort member. "
             "No wage adjustment does not remove payroll-tax or applicable filing obligations. "
             "A requirement is not evidence of an outage, an error or a missed deadline.")
    for p in profiles:
        if not p["represented_businesses"]:
            continue
        filing, wages = JANUARY_EXPOSURE[p["id"]]
        provider = "Quillbook" if p["runs_payroll"] else "outside Quillbook"
        p["january_change_exposure"] = {
            "scope": "representative business; within-cohort exposure shares unspecified",
            "needs_1099_filing": filing,
            "minimum_wage_adjustment_required": wages,
            "payroll_tax_table_updates_relevant": True,
            "payroll_provider": provider,
            "state": None,
            "basis": basis,
        }
        p["background"] += (
            " Fictional January operational assumptions: "
            + ("needs 1099 filing; " if filing else "no 1099 filing need assigned to this representative business; ")
            + ("needs a minimum-wage-related pay adjustment; " if wages else "no minimum-wage-related pay adjustment assigned; ")
            + f"payroll-tax table updates remain relevant, with payroll handled {('in ' if p['runs_payroll'] else '')}{provider}. "
            + "No state, legal rate or confirmed software incident is asserted. These are representative circumstances, not cohort-wide exposure percentages."
        )
    for p in profiles:
        if not p["represented_accountants"]:
            continue
        clients = [by_id[l["target"]] for l in links
                   if l["kind"] == "accountant_advises_client" and l["source"] == p["id"]]
        def coverage(field):
            return ("present among linked representative businesses" if any(c["january_change_exposure"][field] for c in clients)
                    else "not assigned among linked representative businesses; other practice clients unspecified")
        p["january_change_exposure"] = {
            "scope": "linked representative businesses; not a complete practice-client census",
            "client_1099_filing_needs": coverage("needs_1099_filing"),
            "client_minimum_wage_adjustment_needs": coverage("minimum_wage_adjustment_required"),
            "payroll_tax_table_updates_relevant": True,
            "state_coverage": "unspecified; no single-state or multi-state assignment",
            "basis": basis + " Accountant coverage is derived from existing links, not invented extra clients.",
        }
        e = p["january_change_exposure"]
        p["background"] += (" Fictional January operational context from existing links: 1099 filing need is "
                            + e["client_1099_filing_needs"] + "; minimum-wage adjustment need is "
                            + e["client_minimum_wage_adjustment_needs"]
                            + ". Payroll-tax updates remain relevant. State coverage and other practice clients' details are unspecified; no extra client counts or confirmed incident are implied.")


def build():
    profiles = []
    for i, (pid, sector, size, weight, payroll, story) in enumerate(BUSINESSES):
        profiles.append({
            "id": pid,
            "group": "business owners" if pid.startswith("O") else "in-house bookkeepers",
            "sector": sector, "company_size": size,
            "represented_businesses": weight, "represented_accountants": 0,
            "runs_payroll": payroll, "annual_plans": weight // 2,
            "renewal_counts": {"9": 250 if i % 2 == 0 else 0, "10": 250 if i % 2 else 0},
            "partner_managed_businesses": weight * 3 // 5,
            "plan": ("Starter", "Pro", "Plus")[i % 3],
            "decision_authority": "approves" if pid.startswith("O") else "operates_and_advises_owner",
            "backstory": story,
        })
    for pid, total, weight, qb_count, story in PRACTICES:
        profiles.append({
            "id": pid, "group": "partner accountants",
            "practice_clients_total": total, "quillbook_clients_per_practice": qb_count,
            "represented_businesses": 0, "represented_accountants": weight,
            "managed_quillbook_businesses": weight * qb_count,
            "decision_authority": "advises_clients", "backstory": story,
        })
    levels = ("low", "medium", "high")
    for i, p in enumerate(profiles):
        p["attributes"] = {
            "price_sensitivity": levels[i % 3],
            "cash_pressure": levels[(i // 3) % 3],
            "switching_friction": levels[(i + i // 3) % 3],
            "technical_comfort": levels[(i // 2) % 3],
            "uncertainty_tolerance": levels[(i + 1) % 3],
            "patience": levels[(i // 4) % 3],
            "forgiveness": levels[(i + i // 4 + 2) % 3],
            "tax_rule_concern": levels[(i // 3 + 1) % 3],
            "support_need": levels[(i // 2 + 1) % 3],
            "source_checking": levels[(i + i // 2) % 3],
            "social_susceptibility": levels[(i // 5) % 3],
            "preferred_channel": ("email", "in-app", "phone")[i % 3],
            "information_sources": ["accountant or professional peers", "company notices"],
            "values": ["reliability", "fairness", "convenience"] if i % 2 else ["value for money", "control", "reliability"],
        }
        p["assumption_note"] = "Synthetic coverage design, not measured segment frequencies; plan and attitude assignments need sensitivity checks."
    # Preserve explicit narrative constraints instead of contradictory generic bins.
    overrides = {
        "O01": {"cash_pressure": "high"},
        "O03": {"technical_comfort": "low"},
        "O05": {"technical_comfort": "high", "switching_friction": "low"},
        "O06": {"technical_comfort": "high"},
        "B01": {"support_need": "high"},
        "B03": {"switching_friction": "high"},
        "B04": {"tax_rule_concern": "high", "source_checking": "high"},
        "A03": {"tax_rule_concern": "high"},
        "A06": {"technical_comfort": "high"},
    }
    for p in profiles:
        p["attributes"].update(overrides.get(p["id"], {}))
        p["profile_version"] = "v7-mixed-network"
        p["name"] = PROFILE_NAMES[p["id"]]
        p["role"], detail = BACKGROUND_DETAILS[p["id"]]
        if p["represented_businesses"]:
            role = "owns" if p["group"] == "business owners" else "keeps the books for"
            decision = ("They approve software decisions for the business." if p["group"] == "business owners"
                        else "They operate the software and advise the owner on software decisions.")
            payroll = " and payroll" if p["runs_payroll"] else ""
            p["background"] = (f"{p['id']} {role} a {p['company_size']} {p['sector']} business using Quillbook for bookkeeping{payroll}. "
                               f"Their established context: {p['backstory']}. {decision} "
                               f"Fictional role/workflow context: {detail}")
        else:
            p["background"] = (f"{p['id']} advises a practice with {p['practice_clients_total']} total business clients, "
                               f"of whom {p['quillbook_clients_per_practice']} use Quillbook. "
                               f"Their established context: {p['backstory']}. "
                               "Their software advice can strongly influence clients; a recommendation is not an automatic client departure. "
                               f"Fictional role/workflow context: {detail} "
                               "The remaining practice clients are outside the Quillbook count; their software is unspecified. "
                               "The total-portfolio interpretation is a modeling assumption, not an explicit dossier fact.")
        p["background_basis"] = ("User-approved fictional role/workflow enrichment of existing profile context; "
                                 "not measured customer research. Existing traits, quantities and links are unchanged. "
                                 "No new demographics, legal claims or predetermined reactions; choices remain with the LLM.")
    # Reconcile role-balanced portfolios without assigning relationships by list order.
    # Role proportions and hash order are synthetic coverage assumptions, not observed ties.
    # Salt 45 is the first structural candidate (0..45) with <=3 advisers/business
    # and no allocated link below 50 businesses; no generated outcomes were used.
    accountants = sorted(profiles[16:], key=lambda p: p["id"])
    businesses = sorted(profiles[:16], key=lambda p: p["id"])
    total = sum(a["managed_quillbook_businesses"] for a in accountants)
    owner_total = sum(b["partner_managed_businesses"] for b in businesses if b["group"] == "business owners")
    owner_quota = {a["id"]: a["managed_quillbook_businesses"] * owner_total // total for a in accountants}
    remainder = owner_total - sum(owner_quota.values())
    ranked = sorted(accountants, key=lambda a: (-(a["managed_quillbook_businesses"] * owner_total % total), a["id"]))
    for a in ranked[:remainder]:
        owner_quota[a["id"]] += 1
    links = []
    for group in ("business owners", "in-house bookkeepers"):
        pool = [b for b in businesses if b["group"] == group]
        order = lambda p: hashlib.sha256(("mixed-sparse-v2-45|" + group + "|" + p["id"]).encode()).hexdigest()
        pool.sort(key=order)
        rows = sorted(accountants, key=order)
        remaining = {b["id"]: b["partner_managed_businesses"] for b in pool}
        for a in rows:
            needed = owner_quota[a["id"]] if group == "business owners" else a["managed_quillbook_businesses"] - owner_quota[a["id"]]
            for b in pool:
                allocation = min(needed, remaining[b["id"]])
                if not allocation:
                    continue
                for sender, recipient, kind in [(a, b, "accountant_advises_client"), (b, a, "client_asks_accountant")]:
                    links.append({"source": sender["id"], "target": recipient["id"], "kind": kind,
                                  "businesses_linked": allocation, "initial_trust": "medium",
                                  "recipient_reach_share": allocation / (b["represented_businesses"] if recipient is b else a["managed_quillbook_businesses"])})
                remaining[b["id"]] -= allocation
                needed -= allocation
                if not needed:
                    break
            assert needed == 0
        assert sum(remaining.values()) == 0
    # Sparse peer rings; a bounded reach is a pilot assumption, not measured reach.
    for pool in (profiles[:8], profiles[8:16], profiles[16:]):
        for i, p in enumerate(pool):
            other = pool[(i + 1) % len(pool)]
            for source, target in ((p, other), (other, p)):
                links.append({"source": source["id"], "target": target["id"], "kind": "peer",
                              "initial_trust": "medium", "recipient_reach_share": 0.1})
    add_january_exposure(profiles, links)
    add_decision_context(profiles, links)
    return profiles, links


def validate(profiles, links):
    business = [p for p in profiles if p["represented_businesses"]]
    accountants = [p for p in profiles if p["represented_accountants"]]
    assert len(profiles) == 24 and len({p["id"] for p in profiles}) == 24
    assert all(sum(p["group"] == g for p in profiles) == 8 for g in {p["group"] for p in profiles})
    assert sum(p["represented_businesses"] for p in business) == 42000
    assert sum(p["represented_accountants"] for p in accountants) == 3100
    assert sum(p["represented_businesses"] for p in business if p["runs_payroll"]) == 18000
    assert sum(sum(p["renewal_counts"].values()) for p in business) == 4000
    assert sum(p["annual_plans"] for p in business) == 21000
    assert sum(p["partner_managed_businesses"] for p in business) == 25200
    for size, expected in {"micro": 23100, "small": 14700, "medium": 4200}.items():
        assert sum(p["represented_businesses"] for p in business if p["company_size"] == size) == expected
    assert sum(p["managed_quillbook_businesses"] for p in accountants) == 25200
    large = [p for p in accountants if p["id"] in ("A07", "A08")]
    assert sum(p["represented_accountants"] for p in large) == 600
    assert sum(p["managed_quillbook_businesses"] for p in large) == 16800
    ids = {p["id"] for p in profiles}
    assert all(l["source"] in ids and l["target"] in ids and l["source"] != l["target"] and 0 < l["recipient_reach_share"] <= 1 for l in links)
    for b in business:
        assert sum(l["businesses_linked"] for l in links if l["kind"] == "accountant_advises_client" and l["target"] == b["id"]) == b["partner_managed_businesses"]
    ids = {p["id"] for p in profiles}
    edges = {(e["source"], e["target"]): e for e in links}
    assert len(edges) == len(links)
    for e in links:
        assert e["source"] in ids and e["target"] in ids and e["source"] != e["target"]
        assert 0 < e["recipient_reach_share"] <= 1
        reverse = edges[(e["target"], e["source"])]
        if e["kind"] != "peer":
            assert reverse["businesses_linked"] == e["businesses_linked"]
    for a in accountants:
        outgoing = [e for e in links if e["source"] == a["id"] and e["kind"] == "accountant_advises_client"]
        assert sum(e["businesses_linked"] for e in outgoing) == a["managed_quillbook_businesses"]
    return {"profiles": 24, "businesses": 42000, "accountants": 3100, "payroll_businesses": 18000,
            "annual_plans": 21000, "renewals_due": 4000, "partner_managed_businesses": 25200,
            "largest_600_managed_businesses": 16800, "network_links": len(links),
            "status": "Dossier margins reconcile; joint distributions and network remain synthetic assumptions."}


if __name__ == "__main__":
    profiles, links = build()
    audit = validate(profiles, links)
    audit["profile_version"] = "v7-mixed-network"
    audit["enrichment"] = "User-approved mixed sparse network; all population margins and prior numeric traits preserved. Relationship-derived context regenerated."
    folder = ROOT / "data"
    folder.mkdir(exist_ok=True)
    (folder / "personas.jsonl").write_text("".join(json.dumps(p) + "\n" for p in profiles))
    (folder / "network.json").write_text(json.dumps(links, indent=2) + "\n")
    (folder / "population_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))
