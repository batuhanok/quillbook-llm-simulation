"""Versioned persona contracts and information boundaries for the full runner."""

import copy
from datetime import date, timedelta
import json
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from actions import action_key, message_reaches, offers_for

BUSINESS = ("stays", "stays but unhappy", "looking at rivals", "moved to a rival")
ACCOUNTANT = ("recommends Quillbook", "neutral", "steering clients away")
QUESTIONS = {
    "1a": "How much do you trust Quillbook? 1 = not at all, 5 = completely.",
    "1b": '"I can count on Quillbook to treat me right." 1 = strongly disagree, 5 = strongly agree.',
    "2a": "How likely are you to keep using Quillbook over the next three months? 1 = very unlikely, 5 = very likely.",
    "2b": '"I am thinking about leaving Quillbook." 1 = strongly disagree, 5 = strongly agree.',
    "3a": "How likely are you to recommend Quillbook to a friend or colleague? 1 = very unlikely, 5 = very likely.",
    "3b": "If a friend asked you about Quillbook today, what would you tell them? 1 = stay away, 5 = go for it.",
    "4a": "How fairly has Quillbook treated you? 1 = very unfairly, 5 = very fairly.",
    "4b": '"Quillbook takes advantage of people like me." 1 = strongly disagree, 5 = strongly agree.',
}

MODEL_VERSION = "calendar-grounded-v3"


def scenario_calendar(week):
    """Fictional calendar only; never include a future surprise or its scale."""
    start = date(2026, 11, 2)
    if week == 0:
        first = last = start - timedelta(days=1)
        phase = "Before week 1; starting assessment"
    elif week == 11:
        first = last = start + timedelta(weeks=10)
        phase = "After week 10; final assessment"
    else:
        first = start + timedelta(weeks=week - 1)
        last = first + timedelta(days=6)
        phase = "Simulated business week"
    return {"phase": phase, "start_date": first.isoformat(), "end_date": last.isoformat(),
            "scheduled_year_end_update": "2026-12-28", "scheduled_january_switch": "2027-01-01",
            "already_known_public_change": "From January 1 the new IRS system is required for 1099 filing; applicable state minimum wages and payroll tax tables change. The sector previously experienced slowdowns at a comparable change. These are known upcoming requirements, not confirmation of a new incident. Internal testing progress is not disclosed here.",
            "rule": "Use these fictional dates, not today's real date. January changes are upcoming before January 1. A scheduled change is not proof of a completed rollout, a failure or recovery. Dates disclose no surprise events."}


class Message(BaseModel):
    recipient: str
    text: str = Field(min_length=1, max_length=500)
    basis: Literal["personal_experience", "supplied_information", "opinion", "question"]
    source_ids: list[str]


class Observation(BaseModel):
    reaction: str = Field(max_length=500)
    outgoing: list[Message] = Field(max_length=2)


class Share(BaseModel):
    status: str
    fraction: float = Field(ge=0, le=1)


class SegmentChoice(BaseModel):
    segment: str
    choices: list[Share]
    trust: int = Field(ge=1, le=5)
    satisfaction: int = Field(ge=1, le=5)
    support_contact_fraction: float = Field(ge=0, le=1)
    renewal_fraction: float | None
    memory: str = Field(max_length=600)

    @model_validator(mode="after")
    def sum_choices(self):
        if abs(sum(x.fraction for x in self.choices) - 1) > 1e-6:
            raise ValueError("Segment choices must sum to one")
        return self


class Influence(BaseModel):
    message_id: str
    effect: Literal["no_change", "reassurance", "concern", "changed_intention", "question"]
    explanation: str = Field(max_length=300)


class Choice(BaseModel):
    statement: str = Field(max_length=500)
    status: str
    segments: list[SegmentChoice]
    beliefs: list[str] = Field(max_length=4)
    influences: list[Influence]
    replies: list[Message] = Field(max_length=2)


class ProbeScore(BaseModel):
    question: Literal["1a", "1b", "2a", "2b", "3a", "3b", "4a", "4b"]
    score: int = Field(ge=1, le=5, strict=True)


class Probe(BaseModel):
    answers: list[ProbeScore]


def profiles_with_segments(profiles):
    result = copy.deepcopy(profiles)
    for p in result:
        if p["id"] in ("O01", "A08"):
            p["segments"] = [
                {"id": "less_flexible", "share": 0.5, "difference": "High switching friction; substantial migration workload."},
                {"id": "more_flexible", "share": 0.5, "difference": "Low switching friction; credible migration capacity."},
            ]
            p["segment_assumption"] = "50/50 is a sensitivity assumption, not survey data. Two histories in one LLM call are not independent samples."
        else:
            p["segments"] = [{"id": "main", "share": 1.0, "difference": "Use the base profile; no additional split."}]
    return result


def visible_sources(persona, week, events, decisions, selectors):
    sources = [{"id": "profile-" + persona["id"], "week": 0, "kind": "personal_experience",
                "text": "Your established context and history: " + persona.get("background", persona["backstory"])}]
    for event in events:
        if event["week"] <= week and (not event.get("audience_ids") or persona["id"] in event["audience_ids"]):
            affected = event.get("affected", False)
            direct = persona["id"] in affected if isinstance(affected, list) else bool(affected)
            source = {"id": event["id"], "week": event["week"], "text": event["text"],
                            "kind": "personal_experience" if direct else "supplied_information",
                            "incident_exposure": direct,
                            "exposure_interpretation": event.get("direct_exposure_note", "Direct experience is an explicit scenario interpretation; the official announcement does not establish an affected population share.") if direct else "This is reported information; personal impact is not established.",
                            "timing_note": event.get("timing_note", "The occurrence is dated to the release week. It does not establish a fresh incident in each later week or prove recovery.")}
            if event.get("updates_source_ids"):
                source["updates_source_ids"] = event["updates_source_ids"]
                source["update_interpretation"] = "Use this later release for the facts it updates. Earlier uncertainty remains historical, not a contradiction. Do not infer additional fixes or guaranteed non-recurrence."
            sources.append(source)
    # Known scenario chronology, not invented outage outcomes or early internal progress.
    if week >= 9:
        sources.append({"id": "known-year-end-switch", "week": 9, "kind": "supplied_information",
                        "text": "Known crisis reminder — already included in your company dossier. Include this event in every simulation run, including plan_nosurprises.\n\n**Week 9, Friday, January 1: the year-end switch.**\n- From January 1, 1099 forms can only be filed through the IRS's new system.\n- New state minimum wages and payroll tax tables take effect for the first payrolls of the year.\n- Quillbook's update is built; testing is 80% done.\n- At the last big change, providers across the sector had slowdowns in the first working days.\n- It is the busiest time of year for accountants: year-end closing, first payrolls, tax forms.\n- About 4,000 annual plans renew in weeks 9 and 10.",
                        "timing_note": "This is the already-known dossier crisis, repeated in week 9, not a new surprise. The 80% testing figure is the dossier snapshot, not a fresh measurement of progress after interventions. No outage, failed rollout or successful completion is confirmed by this reminder."})
    if persona["represented_businesses"]:
        for due_week, count in persona.get("renewal_counts", {}).items():
            if not count:
                continue
            due = date(2026, 11, 2) + timedelta(days=(int(due_week) - 1) * 7 + 4)
            notice = due - timedelta(days=30)
            notice_week = (notice - date(2026, 11, 2)).days // 7 + 1
            if week >= notice_week:
                sources.append({"id": f"renewal-notice-{due_week}", "week": notice_week,
                                "kind": "supplied_information", "text": f"Your cohort includes {count} annual plans due in week {due_week}. The standard renewal notice is issued 30 days ahead with a planned 20% increase unless an eligible offer below changes it. Friday within the renewal week is a scheduling assumption."})
    for index, d in enumerate(decisions, 1):
        if week >= d["week"] and message_reaches(persona, d, selectors, index):
            sources.append({"id": f"decision-{index}", "week": d["week"], "kind": "supplied_information",
                            "text": d["message"], "channels": d["channels"]})
    # The reconciliation delay is a company-wide consequence even after the freeze expires.
    if any(action_key(a) == "feature_freeze" and week >= d["week"] for d in decisions for a in d["actions"]):
        sources.append({"id": "reconciliation-delay", "week": week, "kind": "supplied_information",
                        "text": "The previously promised December reconciliation tool is delayed until March due to the reliability feature freeze."})
    return sources


SPEECH_RULES = (
    "Speak as this particular customer, briefly and naturally. No corporate analyst jargon or cohort percentages in personal speech. "
    "Silence is acceptable: do not repeatedly ask about distant deadlines without new relevant information. "
    "Only the supplied sources are verified here. Prior memory and peer messages are fallible beliefs. "
    "Use the fictional calendar in context: November or December is not January. Distinguish preparation from a completed January change. "
    "If a source says the cause is unknown, it does not confirm fault at a bank, Quillbook, or another provider. "
    "Engineers working with a bank and another provider reporting delays do not establish a shared cause. "
    "Do not turn a peer's assertion into confirmed information through repetition. Ask for evidence or label it as a belief. "
    "A dated progress percentage does not establish current progress or that testing is on track. "
    "Two reports do not verify a platform-wide incident. You may infer or worry, but label that as a belief. "
    "Read 'this week' in an announcement relative to its release week. A past delay is not evidence of a new delay, continuing disruption or recovery in a later week. "
    "Do not invent private engineering information, company guarantees, support contacts, or actions. "
    "Do not invent product capabilities, tier entitlements, or usage limits. Missing feature details here do not mean the company lacks them or has hidden them. "
    "Ask about unknown capabilities instead of claiming you tested them; prior generated memories and peer messages cannot verify new product specifications. "
    "Population weights are not the size of your own business or practice. "
    "Choose freely; do not optimize for the company or manufacture agreement. "
)


def prompt_for(persona, state, week, links, inbox, sources, decisions, selectors,
               observation=None, baseline=False, support=None, reasoned_messages=True):
    allowed = BUSINESS if persona["represented_businesses"] else ACCOUNTANT
    context = {"week": week, "scenario_calendar": scenario_calendar(week),
               "persona": persona, "prior_beliefs_and_state": state,
               "verified_sources": sources, "peer_inbox": inbox,
               "available_connections": [e for e in links if e["source"] == persona["id"]],
               "network_interpretation": "An advisory link allocates a portion of representative businesses to an accountant cohort; multiple links need not mean each individual business has several accountants. recipient_reach_share is the portion directly reached, not universal exposure. Consider the remaining cohort separately; additional spread requires actual delivered messages. Peer reach is an explicit modeling assumption.",
               "allowed_statuses": allowed, "own_observation": observation,
               "public_terms": {"prices_usd_monthly": {"Starter": 40, "Pro": 90, "Plus": 180},
                                "free_data_export": True, "routine_support_hours": 3,
                                "known_product_capabilities": ["invoices", "bank reconciliation", "payroll and direct deposit", "year-end tax forms", "reports"],
                                "tier_feature_matrix": "Not supplied. Inventory capability, tier-specific feature differences and usage caps are unknown. Do not infer presence, absence, or completed feature tests."},
               "eligible_offers": offers_for(persona, decisions, selectors, week,
                    any(s.get("incident_exposure", False) for s in sources)),
               "renewals_due_now": persona.get("renewal_counts", {}).get(str(week), 0),
               "personal_support_experience": support,
               "segment_rule": "Keep distinct histories for each internal perspective. Shares are assumptions, not measured distributions."}
    if baseline:
        task = (
            "Assess your starting situation before week 1 using the profile's history and constraints, not a preset neutral score. "
            "Return a Choice with every segment, trust/satisfaction 1-5, and ALL allowed status fractions summing to one. "
            "All business customers are active at this snapshot, so moved-to-a-rival fraction is zero. "
            "Use renewal_fraction=null, influences=[], replies=[]. Set initial support demand based on your context. "
        )
        context["analyst_historical_context"] = {"monthly_churn_pct": 1.6,
            "note": "Company-level historical reference, not your personal experience or a target to force in answers."}
    elif observation is None:
        task = "Return an Observation with reaction and up to two optional outgoing messages to valid connections. Cite source_ids for experiential/information claims; opinions and questions may use none."
    else:
        task = (
            "Return a Choice with your representative status and ALL segments. Each segment's choices must include each exact "
            "allowed status once and sum to one. Fractions refer to that segment's original population, with cumulative "
            "business departures never decreasing. Choose integer trust/satisfaction 1-5, support_contact_fraction, "
            "and a concise updated segment memory. If renewals_due_now > 0, renewal_fraction is the fraction of that "
            "segment's ORIGINAL due cohort renewing now, including the effect of any eligible offer; otherwise null. "
            "The due cohort is distinct from the whole segment: choose its renewal fraction between zero and one; do not mechanically cap it using the whole-segment departure percentage. Do not count a due customer as both departed and renewed. These are synthetic judgments; do not "
            "claim empirical accuracy. Keep statement personal; keep numerical analyst estimates in segments only. "
            "Cite actual inbox message IDs in influences; use no_change when appropriate. An empty inbox requires no influences. "
            "Replies only go to senders in your inbox, using available connections. They arrive next week. "
        )
    if reasoned_messages and not baseline:
        task += (
            " When you choose to send advice, a recommendation, or an intention, "
            "include one brief practical reason in the message text itself, so the recipient can assess it. "
            "Use only your supplied situation, accessible information, or explicitly labeled beliefs. "
            "For example, explain a relevant workload constraint, payment consequence, cost concern, or uncertainty; "
            "do not invent an experience or a factual claim just to supply a reason. "
            "Questions and simple acknowledgments need no forced explanation; silence remains acceptable. "
            "When assessing a received message, consider whether the sender's reason applies to your own situation. "
            "You may disagree, ask for evidence, or make no change. Explaining a reason is not proof of its truth "
            "or a requirement to persuade anyone. Never claim a later announcement's facts before its release. "
        )
    return SPEECH_RULES + task + "\nCONTEXT_JSON\n" + json.dumps(context, ensure_ascii=False, sort_keys=True)


def validate_choice(result, persona, state, inbox, sources, links, baseline=False, due=False):
    allowed = BUSINESS if persona["represented_businesses"] else ACCOUNTANT
    if result["status"] not in allowed:
        raise ValueError("Invalid role status")
    specs = {s["id"]: s for s in persona["segments"]}
    if len(result["segments"]) != len(specs) or {s["segment"] for s in result["segments"]} != set(specs):
        raise ValueError("Missing or duplicate segment")
    prior = {s["segment"]: s for s in state.get("segments", [])}
    for segment in result["segments"]:
        if len(segment["choices"]) != len(allowed) or {s["status"] for s in segment["choices"]} != set(allowed):
            raise ValueError("Invalid segment status choices")
        choices = {x["status"]: x["fraction"] for x in segment["choices"]}
        if persona["represented_businesses"]:
            old = {s["status"]: s["fraction"] for s in prior.get(segment["segment"], {}).get("choices", [])}.get("moved to a rival", 0)
            if choices["moved to a rival"] + 1e-6 < old or (baseline and choices["moved to a rival"] != 0):
                raise ValueError("Invalid cumulative departure")
        renewal = segment["renewal_fraction"]
        if due and persona["represented_businesses"]:
            if renewal is None or not 0 <= renewal <= 1:
                raise ValueError("Invalid due-cohort renewal fraction")
        elif renewal is not None:
            raise ValueError("Renewal answer before/after its due week")
    inbox_ids = {x["id"] for x in inbox}
    if any(x["message_id"] not in inbox_ids for x in result["influences"]):
        raise ValueError("Invalid influence source")
    validate_messages(result["replies"], persona, links, sources, inbox, replying=True)


def validate_messages(messages, persona, links, sources, inbox, replying=False):
    targets = {e["target"] for e in links if e["source"] == persona["id"]}
    if replying:
        targets &= {m["sender"] for m in inbox}
    source_ids = {x["id"] for x in sources} | {x["id"] for x in inbox}
    personal = {x["id"] for x in sources if x["kind"] == "personal_experience"}
    verified = {x["id"] for x in sources}
    for message in messages:
        if message["recipient"] not in targets or any(s not in source_ids for s in message["source_ids"]):
            raise ValueError("Invalid message target or evidence reference")
        if message["basis"] in ("personal_experience", "supplied_information") and not message["source_ids"]:
            raise ValueError("Factual message needs an accessible source")
        if message["basis"] == "personal_experience" and not set(message["source_ids"]) <= personal:
            raise ValueError("Personal experience cannot cite another actor's claim as your own")
        if message["basis"] == "supplied_information" and not set(message["source_ids"]) <= verified:
            raise ValueError("Peer claims are not verified company information")


def aggregate(persona, choice):
    shares = {s["id"]: s["share"] for s in persona["segments"]}
    fields = {"trust": 0.0, "satisfaction": 0.0, "support_contact_fraction": 0.0}
    distribution = {}
    renewed = 0.0
    for segment in choice["segments"]:
        share = shares[segment["segment"]]
        for key in fields:
            fields[key] += share * segment[key]
        for item in segment["choices"]:
            distribution[item["status"]] = distribution.get(item["status"], 0) + share * item["fraction"]
        if segment["renewal_fraction"] is not None:
            renewed += share * segment["renewal_fraction"]
    return {**fields, "cohort_choices": [{"status": key, "fraction": value} for key, value in distribution.items()],
            "renewal_fraction": renewed}
