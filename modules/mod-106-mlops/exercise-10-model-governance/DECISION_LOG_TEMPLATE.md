# Decision Log: {MODEL_NAME}

Each entry: what was decided, what was rejected, why.

## 2026-04-01: Choose random forest over neural network
- **Decision**: RandomForestClassifier(n_estimators=200, max_depth=12)
- **Rejected**: MLPClassifier with 3 hidden layers
- **Why**: RF achieved 91% AUC vs MLP 92.5%; training time 3min vs 4hr; serving cost 1/5 of MLP for negligible business impact
- **Decided by**: @ml_eng_alice, @ds_bob (peer review)

## 2026-04-15: Drop `referrer_domain` feature
- **Decision**: Remove from feature set
- **Why**: Compliance review flagged as proxy for protected class; removing dropped AUC by 0.4pp — acceptable
- **Decided by**: @compliance_lead approved; @ds_bob signed off on impact
