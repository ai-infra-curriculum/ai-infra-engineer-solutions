# SOLUTION — Exercise 01: MLOps Maturity Assessment

> Read this after the module-level [`../SOLUTION.md`](../SOLUTION.md) and after
> you have attempted your own assessment. This is a *design / analysis*
> exercise: the deliverable is a defensible maturity rating plus a prioritized,
> sequenced roadmap — not running code.

## 1. Solution overview

Exercise 01 asks you to assess a team's MLOps maturity, name the
highest-leverage next investments, and lay out a roadmap that moves the team up
a level. The worked sample answer lives alongside this file in
[`ASSESSMENT.md`](./ASSESSMENT.md); this document explains what a complete
answer must demonstrate and how a grader should score it.

The four things a passing submission proves:

1. The student rated *current* maturity per capability with evidence (what the
   team does today), not by which tools they happen to own.
2. The student covered the whole ML lifecycle — data validation, feature
   engineering, training, experiment tracking, registry, CI/CD, monitoring, and
   retraining — rather than only the parts they find interesting.
3. The student prioritized investments by leverage *and* dependency order, so
   the foundation (tracking, versioning) lands before the advanced capabilities
   (canary, feature store) that depend on it.
4. The roadmap is time-bound, owned, and ends at a maturity level that is
   justified by which capabilities crossed the automation threshold.

## 2. Implementation

This is a design / analysis exercise, so the "implementation" is the worked
assessment artifact rather than running code. The model answer is
[`ASSESSMENT.md`](./ASSESSMENT.md). Its shape, and the
reasoning a grader should expect:

**Team profile (the sample case):** a mid-size data team — 4 ML engineers, 3
production models, deploys done by hand via notebooks. That profile is what
pins the team at the bottom of the scale.

**Current level.** The sample rates the team at its lowest "manual" tier and
walks each capability from its manual/ad-hoc present state to a tooled target
state (manual data validation → Great Expectations; per-notebook features →
Feast; spreadsheet tracking → MLflow; filesystem registry → MLflow registry;
no model CI/CD → GitHub Actions + canary; latency-only monitoring → drift + bias
+ slice metrics; manual retrain → event/cron triggered).

> Indexing note: the sample uses a 1-indexed scale (Level 1 = manual). Google
> Cloud's published MLOps maturity model is 0-indexed — level 0 (manual
> process), level 1 (ML pipeline automation), level 2 (CI/CD pipeline
> automation). What a grader scores is the *capability transitions*, not the
> absolute number; just keep one scale consistent throughout the answer.

**Top investments, in priority order.** The sample orders them so each unlocks
the next, which is exactly the dependency logic the module rationale argues for:

1. **MLflow tracking first** — it is the foundation everything else builds on,
   and it directly fixes the module's first graded mistake ("tracking
   experiments locally, not centrally"). See [`../SOLUTION.md`](../SOLUTION.md)
   Decision 1.
2. **DVC for data + model versioning** — operationalizes the module's
   "everything is versioned" thesis and answers "what data trained this model"
   ([`../SOLUTION.md`](../SOLUTION.md) Decision 2).
3. **Model registry + staged promotion** — makes the registry the source of
   truth, distinct from the experiment tracker ([`../SOLUTION.md`](../SOLUTION.md)
   Decision 1 and graded mistake #3).
4. **CI for model code** — catches regressions at PR time.
5. **Production drift monitoring** — surfaces degradation before customers do.

Note what is deliberately *not* first: the feature store and canary deploys.
The module's "When to go beyond this implementation" section is explicit that a
proper feature store is adopted once the training/serving contract is a
recurring source of bugs — i.e. after the foundation exists.

**Roadmap and transition.** The sample lays out a month-by-month, owned
6-month plan (tracking → DVC proof → registry workflow → CI → feature store →
drift → canary) and states the resulting transition: first model up one level
at 6 months, all models up one level plus the highest-traffic model reaching
the CI/CD tier at 12 months. The end-state level is justified by *which*
capabilities became automated, which is the standard the rubric below enforces.

## 3. Validation steps

There is no program to run; "validation" here is a self/peer review that the
assessment is internally consistent. Check each of these against the submission:

1. **Every "current" rating cites an observable.** "Experiment tracking =
   spreadsheet" is a fact you can point at; an unsupported rating is a guess.
2. **Every "target" maps to a concrete tool already in the reference stack**
   (MLflow, DVC, Feast, GitHub Actions) — not a hand-wave like "automate it".
3. **The roadmap respects dependencies.** Tracking precedes registry; registry
   precedes promotion-gated CD; monitoring precedes triggered retraining. A plan
   that schedules canary before tracking exists fails this check.
4. **Every roadmap item has an owner and a named outcome.** An item with
   neither cannot be held to account.
5. **The claimed end-state level is derivable from the table.** Tie the final
   level back to the specific capabilities that crossed from manual to
   automated; if the number does not follow from the capabilities, it is
   unjustified.

A sound assessment passes all five: each rating is evidenced, each target is
concrete, the sequence is dependency-correct, every step is owned, and the
ending level follows from the capability changes.

## 4. Rubric / review checklist

| Criterion | Weight | Pass condition |
|---|---|---|
| Current-level diagnosis | 20% | A level is assigned with per-capability evidence, not by tool inventory |
| Lifecycle coverage | 20% | Data, features, training, tracking, registry, CI/CD, monitoring, and retraining are all rated |
| Prioritization quality | 25% | Investments ordered by leverage *and* dependency; foundation (tracking, versioning) before advanced (feature store, canary) |
| Roadmap feasibility | 20% | Time-bound, owned, dependency-respecting, with an outcome per step |
| Transition justification | 15% | The end-state level follows from which capabilities became automated |

Borderline cases: a submission that proposes a feature store or canary deploys
as the *first* investment should not pass "prioritization quality" — it has
skipped the foundation the rest of the plan depends on, which is the exact
sequencing error the module rationale warns against.

## 5. Common mistakes

1. **Skipping the foundation.** Proposing a feature store or canary before
   centralized tracking and versioning exist. The dependency order is not
   optional.
2. **Rating maturity by tools owned, not capabilities automated.** Owning
   MLflow does not make you mature if every run still goes to a spreadsheet.
3. **Conflating experiment tracking with the model registry.** They are
   distinct stages — the lab versus production (module idea 2 / Decision 1).
4. **A roadmap with no owners or no dependency ordering.** Unsequenced,
   unowned plans do not survive contact with a real quarter.
5. **Tracking experiments locally instead of centrally** — the module's first
   graded mistake; nobody else can reproduce or compare.
6. **Treating the level *number* as the goal.** The number is a label for a
   set of capabilities; chasing the digit (and tangling indexing schemes)
   instead of the capabilities misses the point.

## 6. References

- Local exercise context: [`ASSESSMENT.md`](./ASSESSMENT.md) — the worked
  sample assessment, gap table, prioritized investments, and 6-month roadmap.
- Module rationale: [`../SOLUTION.md`](../SOLUTION.md) (Decisions 1–2 and the
  "Common mistakes graders see" / "When to go beyond" sections).
- Learning exercise brief: `lessons/mod-106-mlops/exercises/exercise-01-mlops-maturity-assessment`
  ([README](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-106-mlops/exercises/exercise-01-mlops-maturity-assessment/README.md)).
- Google Cloud — *MLOps: Continuous delivery and automation pipelines in
  machine learning* (the maturity model the sample's leveling is built on):
  https://cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning
- NIST AI Risk Management Framework — the **GOVERN** function (accountability,
  roles, and process maturity) as a complementary governance lens for a maturity
  assessment: https://www.nist.gov/itl/ai-risk-management-framework
