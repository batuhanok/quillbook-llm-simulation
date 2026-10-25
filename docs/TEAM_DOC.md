# Quillbook simulation: design, evidence and learning
**Team 08 · Profiles: v7-mixed-network · Engine model: calendar-grounded-v3**

## Personas and population representation

The simulation contains 24 representative voices: eight business owners, eight in-house bookkeepers and eight partner accountants. Their weights reconcile to the dossier's 42,000 businesses, 3,100 accountants, 18,000 Quillbook payroll customers, 21,000 annual plans and 4,000 renewals due in weeks 9–10. Accountants manage 25,200 business customers; the largest 600 represent 16,800 of those relationships. Managed businesses are included in the business population rather than counted again as additional customers. Practice client counts and represented accountant populations are separate quantities.

### Persona architecture: identity, constraints and evolving choices

Each persona combines a stable identity and work history with operational exposure, decision authority, behavioral traits, relationships and changing weekly state. This makes a reaction explainable in terms of a particular business situation rather than a generic satisfied or dissatisfied customer. All 24 have names and distinct role narratives, while their population weights remain separate from their personal speech.

| Layer | Implemented detail | Purpose in the simulation |
|---|---|---|
| Work and identity | Named roles, sector, company size, plan, prior experience and concrete routines | Gives the same incident different practical meaning across businesses. |
| Authority | Owner approval, bookkeeper operation/recommendation, accountant advice | Separates wanting a change from being able to authorize and execute it. |
| Practical capacity | Technical comfort, available time, migration friction and existing help | Allows a capable but overloaded customer to wait, or an unhappy customer to investigate before moving. |
| Operational exposure | Quillbook versus external payroll, 1099 filing needs, wage-adjustment needs and payroll-tax relevance | Distinguishes direct workflow disruption from concern about an event affecting others. |
| Behavioral tensions | Price sensitivity, cash pressure, patience, forgiveness, uncertainty tolerance, values and support needs | Creates competing considerations rather than one trait determining the outcome. |
| Information habits | Source checking, social susceptibility, preferred channels and information sources | Gives recipients context for assessing advice, uncertainty and company claims. |
| Relationships | Explicit client–accountant and peer links with allocated cohort reach | Controls who can hear, question and answer whom. |
| Weekly state | Trust, satisfaction, beliefs, segment memory, support demand, behavior shares and renewal choice | Carries the consequences of earlier experiences and conversations into later decisions. |

Trait levels provide qualitative context to the LLM; they are not a hand-written score that automatically produces churn. Their joint distribution is synthetic coverage design. No external demographic dataset was imported. Decorative attributes such as logo color were excluded because they had no proposed mechanism for the company's decisions.

### Practical contradictions within a persona

The profiles deliberately separate characteristics that are often collapsed into a single willingness-to-switch score:

- **O01, Alex Morgan:** a micro construction owner balancing cash pressure and dependable payroll. Low perceived switching friction can coexist with low technical comfort and a need for help checking an export.
- **B03, Sam Walker:** technically comfortable, but the sole finance worker also handling office administration. Investigating alternatives is feasible; finding migration time and obtaining owner approval are separate constraints.
- **O06, Morgan Reed:** has existing IT help to assess portability and operational checks. Technical feasibility still needs a business reason and workable timing.
- **B07, Sharon Fields:** combines retail administration and bookkeeping and can compare costs with the owner. An attractive price does not establish that an alternative's unknown features meet the business's needs.
- **A08, Sofia Lindqvist:** weighs client continuity, workload, reputation and commercial incentives in a large mixed practice. Lower switching friction or higher commission does not prescribe a recommendation or move clients automatically.

These are starting contexts, not predetermined stories of success or failure. Investigation, preparation, waiting, commitment and switching can emerge in generated memories; completed migration or rival capabilities are not preassigned.

### Exposure follows the work

The January context distinguishes a business's need to file 1099 forms from its need to adjust wages. Payroll-tax tables remain relevant independently of a wage-adjustment flag. An external-payroll customer can care about bookkeeping continuity without experiencing a Quillbook payroll failure directly. Accountants' exposure summaries are derived from their actual linked business profiles rather than invented extra clients. No state, legal rate or measured sector frequency is assigned by these flags.

This separation also applies to surprises: O01 and B08 supply two illustrative direct payroll-delay experiences, while other personas may receive reports or private advice. Hearing an incident, experiencing it and choosing to act are distinct stages.

### Heterogeneity and memory

A representative voice does not make its entire weighted population act identically. Each internal perspective returns a distribution across the allowed statuses, plus trust, satisfaction, support-contact share and a renewal fraction when due. O01 and A08 each have two perspectives with different migration flexibility and assumed 50/50 shares; the remaining profiles have one. The two perspectives share a model call and are not independent samples.

Individualized baseline calls establish starting assessments instead of assigning every persona a neutral score. Subsequent calls receive the prior state, accessible sources, delivered messages and current fictional dates. Updated beliefs and concise segment memories preserve continuity across weeks. Renewal is evaluated separately for the original due cohort, so a positive statement, dissatisfaction or whole-population departure percentage does not mechanically fix the renewal result. A saved-history interview can subsequently question any persona about its final choices without altering the simulation record.

## Relationships and weekly information

The network has 30 accountant–business advisory pairs and 24 peer pairs, represented as 108 reciprocal directed links. Each accountant cohort connects to both owners and bookkeepers; each business cohort has at most three adviser cohorts. Portfolio allocations reconcile on both sides. Multiple cohort links can represent different businesses within a cohort, rather than several accountants serving every individual business.

Each week has two rounds: observation and outgoing messages, followed by interpretation, choices and replies. Observation messages reach connected recipients before their choices; replies arrive the following week. Advice includes a practical reason, while questions and silence remain possible. Recipients report which delivered messages influenced them, including no-change responses. Each exchange records its sender, recipient, text, timing, relationship, source call and configured cohort reach. Influence reports describe the model's interpretation rather than measured causality.

### Traceable influence rather than automatic persuasion

Outgoing advice includes a practical reason that the recipient can assess. The recipient can report reassurance, concern, a question, changed intention or no change, with the exact message ID and an explanation. Reading advice is therefore distinct from adopting it. No global adviser credibility score rewards agreement or penalizes an adviser whose recommendation is declined.

The submitted `plan_2` history illustrates the complete exchange. In week 1, O08 asks A05 how to prepare high-volume invoice records for January filing. A05 replies with a reason for checking vendor details early; the reply reaches O08 in week 2, where O08 records reassurance. In another week-1 exchange, A07 records B06's preparation question as **no change**, explaining that it aligns with standard year-end guidance. Both outcomes remain visible rather than forcing every interaction to persuade someone.

These examples are traceable in `runs/plan_2/calls.jsonl`: A05's reply is call `32052dbc2da44c3fa2349ae3458514e9b2230e1a30406ea841b1f764ec675f6d`; O08's receiving choice is `53388bb7abe8ff494f3c3cfc0eb570d5c2c4e97ba349f30c537d419c34545c97`; A07's no-change choice is `98fb8e7137ee045fb14dc413fb7512a1094caa44485f5b3ce6b4ebd9918cba29`. These are generated explanations of influence, not experimentally identified causal effects.

Known public January requirements are available from the start. Surprise announcements enter only from their release weeks. The week-3 payroll incident initially has unknown scale, fault and recurrence. O01 and B08 are illustrative direct experiences, not whole-cohort incidence assignments. The week-4 update establishes recovery of the delayed deposits, the stated causes and approximate one-in-20 payroll incidence. Week 7 introduces the shutdown; week 8 confirms Senate passage while House action, reopening and federal pay timing remain uncertain. The week-9 reminder repeats the existing known crisis and remains in every condition. No new week-10 announcement was reported.

Company messages reach their targets verbatim from the locked effective weeks. Menu durations govern operations even where the saved messages describe dates loosely. Peer claims do not alter the official event ledger, and private messages are not broadcast to everyone.

## Model execution and metrics

Gemini 3.7 Flash generates starting assessments, reactions, messages, statuses, support demand, renewal choices and cohort behavior shares. Calls use actual seeds 42 or 43 and temperature 1. Code handles timing, exposure, routing, validation and weighted aggregation. Full prompts, raw responses and repair attempts are saved. Network failures were resumed from matching cached calls at lower concurrency; missing answers were not substituted. Cache keys include the full prompt, schema, persona, week, phase, seed, model and temperature. Seeds alone do not guarantee provider determinism.

Renewal is the fraction of the original 4,000 due plans renewed. Churn is the maximum rolling four-week departure percentage within the ten-week horizon. Accountant satisfaction is the weighted final-minus-baseline change on the same 1–5 scale. Support is the maximum daily population-weighted response time, excluding January 4–5. Questionnaire scores remain as returned, including negatively worded items.

Support is a baseline-anchored workload proxy. It assumes 100 existing staff, a 2% fallback contact rate, equal productivity for the additional 40 staff, and a hotline shift of ten percentage points of capacity toward accountants. The baseline response references are three hours normally and eight at year-end. Outside testing reduces the incremental year-end workload term by an assumed 10%; the unselected feature-freeze option uses 20%. These parameters are assumptions, not estimated intervention effects. The selected staffing/testing combination has a roughly 5.36-hour year-end floor before hotline tradeoffs, making the four-hour target structurally difficult in this model. Testing-related incident prevention is not separately quantified.

## Experiments, problems and revisions

Development diagnostics exposed neutral starting-score anchoring, repetitive future references and unsupported confidence in testing. Individualized baselines, explicit fictional dates, source provenance and speech constraints addressed those mechanisms. A reasoned-message comparison also revealed that a plausible explanation can spread an unsupported belief; reasons were therefore retained alongside uncertainty boundaries and recipients' ability to question advice.

Two early runs were rejected after an arbitrary queue-capacity assumption created an artificial backlog. The replacement workload model anchors demand to each run's starting assessment. Graph inspection subsequently revealed that sequential portfolio allocation concentrated all bookkeeper links on A08. The final sparse mixed network preserves population margins while removing that ordering artifact. Its structural criteria were chosen without consulting generated renewal outcomes; a fully dense network was rejected because it would expand direct access to private advice.

A further review removed a validator cap that conflated whole-cohort departures with renewals in a distinct due cohort. Renewal and departure percentages now use their respective denominators. Individual due-customer histories are not tracked, so consistency remains limited to cohort-level reasoning and validation. Earlier outputs and inputs were preserved separately; the final comparison was replayed consistently after the revisions.

## Final comparison and findings

The submitted conditions are `plan_1` and `plan_2` with the exact locked packages and seeds 42/43; `nodecision_1` and `nodecision_2` without packages using those seeds; and `plan_nosurprises` with the same plan and seed 42 but surprise announcements and updates removed. The known January switch remains. All five share identical profiles, relationships, assumptions and runtime source hashes. Matched plan/control histories are identical through week 4, before the first intervention.

Across the two seeds, the plan increases renewal by 2.75 and 4.38 percentage points and improves support by approximately 2.3–2.4 hours. It improves accountant sentiment but slightly increases churn. Renewal and support still miss their targets. The results describe the tested locked plan, not an optimal policy or demonstrated return on investment. The no-surprises branch retains incident references in the unchanged company messages, limiting isolation of event effects. Six-month commission benefits beyond the ten-week horizon are not measured.

The final evidence comprises 1,200 weekly records and 768 original start/end questionnaire scores. All five runs passed local checks for raw-response traceability, timing, private delivery, aggregation and exact decision equality. The unchanged organizer checker passed the submission archive. Twenty-eight offline tests were completed before the final replay. These checks establish execution and file integrity rather than calibrated predictive accuracy.

## Reproduction and further work

`code/README.md` gives installation, authentication, reproduction, audit and saved-persona interview commands. `runs/` contains full calls, weekly states, metrics, interactions, manifests and audits; `code/data/locked_plan.json` preserves the actual decisions. Credentials and historical experiments are excluded from the archive.

Additional work would test alternative networks and exposure allocations, more independent seeds and support/action-effect sensitivity; validate consequential assumptions against customer and operational evidence; and extend the horizon to assess February departures and longer-term partner incentives. The two-seed findings are exploratory and do not establish statistical confidence.
