# SOLUTION — Exercise 14: ML Platform Team Operating Model

> Read this after the module-level [`../SOLUTION.md`](../SOLUTION.md). This is a
> *design* exercise: the deliverable is an operating model / team charter —
> ownership boundaries, intake, support, on-call, and success metrics — not
> running code.

## 1. Solution overview

Exercise 14 asks you to define how an ML platform team operates: its mission,
what it owns and explicitly does not own, how work comes in, how it supports
users, how it runs on-call, how it measures success, and which failure modes it
designs against. The worked sample answer lives alongside this file in
[`CHARTER.md`](./CHARTER.md); this document explains what a complete answer must
demonstrate and how a grader should score it.

The four things a passing submission proves:

1. The student drew an ownership boundary that is mutually exclusive (nothing
   owned twice) and collectively covers the ML lifecycle (nothing orphaned).
2. The default path is self-service — the team enables teams rather than
   gatekeeping them.
3. Support and on-call have concrete tiers, response/restoration targets, and a
   rotation, so reliability is operationalized rather than aspirational.
4. Success metrics are measurable and tied to goals, and each named failure
   mode has a specific countermeasure built into the model.

## 2. Implementation

This is a design exercise, so the "implementation" is the worked operating-model
artifact rather than running code. The model answer is
[`CHARTER.md`](./CHARTER.md). Its structure, and the
reasoning a grader should expect:

**Mission.** Make it easy and safe to ship and operate ML in production via
self-service infrastructure and opinionated workflows — *not* by being a
gatekeeper. This framing is the spine the rest of the charter hangs on.

**Ownership split ("what we own" / "what we do NOT own").** The sample owns the
platform substrate and leaves judgment calls to the domain experts:

- *Owned* — tracking + registry, feature store, serving runtime, pipeline
  framework, drift/bias monitoring, CI/CD plumbing, cost attribution. This maps
  directly onto the module's architectural decisions: the registry as source of
  truth ([`../SOLUTION.md`](../SOLUTION.md) Decision 1), the feature store as the
  contract layer (Decision 5), and model-aware CI/CD (Decision 4).
- *Not owned* — model architecture and hyperparameters, business-metric
  definitions, feature semantics / data correctness, and retraining schedules.
  These belong to data scientists, product/analytics, data engineering, and
  model owners respectively.

The principle stated in the charter — "we provide the rails; teams drive the
trains" — is the test for which side of the line a responsibility falls on.

**Intake.** Three lanes sized to where work actually lands: self-serve
(majority of cases, zero tickets), weekly office hours (small unblockers), and
project intake (multi-week platform changes on an SLA). The lane sizing is what
keeps the team from becoming the gatekeeper its mission rejects.

**Support model.** Three tiers — 24/7 paging for platform outages with a
response and restoration target, a working-hours Slack channel for non-blocking
issues, and a project queue for feature requests on quarterly planning.

**On-call.** A small rotation on weekly shifts, primary/secondary split,
runbooks required for any alert that has fired recently, and a postmortem within
a bounded window of any significant incident.

**Success metrics.** A table pairing each metric with a target — template
adoption, time-from-trained-to-prod, serving MTBF/MTTR, office-hours
utilization, self-serve adoption growth, and cost-attribution coverage. Each one
is an *outcome*, which is what the rubric rewards.

**Failure modes.** The charter names the traps and the countermeasure for each:
the gatekeeper trap (countered by making self-serve genuinely easy),
custom-everywhere (countered by being the obvious-best default), and slow
batching (countered by reserving capacity for quick wins).

## 3. Validation steps

There is no program to run; "validation" here is a consistency review of the
operating model. Check each against the submission:

1. **Every owned surface has matching support coverage.** A page-able Tier 1
   outage class (e.g. registry/serving down) should correspond to something the
   team actually owns. Owning a thing with no support path — or paging on a
   thing you do not own — is a gap.
2. **Ownership boundaries are mutually exclusive and lifecycle-complete.** No
   responsibility appears on both the "own" and "do not own" lists, and the
   union of the two covers the lifecycle with no orphaned area.
3. **Intake capacity is internally consistent.** Reserved capacity for quick
   asks must actually exist if the model claims to avoid slow batching; the lane
   percentages should not sum to "everything is a project".
4. **Each success metric is measurable and tied to a goal.** "Self-serve
   adoption grows" ties to the gatekeeper-trap countermeasure; a metric with no
   goal behind it is decoration.
5. **Each named failure mode has a concrete mechanism preventing it.** If the
   charter names "gatekeeper trap" but every path routes through a ticket, the
   countermeasure is missing.

A sound charter passes all five: ownership is clean and complete, support
mirrors ownership, intake is capacity-consistent, metrics are outcome-tied, and
every named trap has a real defense.

## 4. Rubric / review checklist

| Criterion | Weight | Pass condition |
|---|---|---|
| Ownership clarity | 25% | Explicit own / do-not-own lists; mutually exclusive; lifecycle-complete |
| Self-service orientation | 20% | The default path is self-serve; gatekeeping is avoided by design, not just disavowed |
| Support + on-call model | 20% | Tiers defined with response/restoration targets and a named rotation |
| Success metrics | 20% | Measurable, outcome-tied, covering both adoption and reliability |
| Failure-mode mitigation | 15% | Names the traps *and* the specific countermeasure built in for each |

Borderline cases: a charter whose mission disclaims gatekeeping but whose intake
routes every request through a ticket should not pass "self-service
orientation" — the stated value is contradicted by the mechanism.

## 5. Common mistakes

1. **Becoming a gatekeeper.** Routing every model through a platform ticket —
   the charter's headline failure mode. Self-serve has to be the easy path, not
   a footnote.
2. **Owning what you cannot control.** Claiming model architecture or
   business-metric definitions blurs accountability and sets the team up to be
   blamed for decisions it does not make.
3. **Measuring activity instead of outcomes.** "Tickets closed" rewards a busy
   queue; "median time-to-prod" and "self-serve adoption" reward the mission.
4. **No reserved capacity for quick wins.** A pure project roadmap produces
   slow batching, which pushes teams to build their own workarounds
   (custom-everywhere).
5. **On-call without runbooks or postmortems.** Reliability becomes tribal
   knowledge and the same incident recurs.

## 6. References

- Local exercise context: [`CHARTER.md`](./CHARTER.md) — the worked sample
  charter (mission, ownership, intake, support, on-call, metrics, failure
  modes).
- Module rationale: [`../SOLUTION.md`](../SOLUTION.md) (Decisions 1, 4, and 5 —
  registry as source of truth, model-aware CI/CD, and the feature store as the
  contract layer the platform owns).
- Learning exercise brief: `lessons/mod-106-mlops/exercises/exercise-14-ml-platform-operating-model`
  ([README](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-106-mlops/exercises/exercise-14-ml-platform-operating-model/README.md)).
- NIST AI Risk Management Framework — the **GOVERN** function (accountability
  structures, roles and responsibilities) as the governance lens for an
  ownership / operating model: https://www.nist.gov/itl/ai-risk-management-framework
