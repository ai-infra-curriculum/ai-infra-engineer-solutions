# Postmortem: {INCIDENT_TITLE}

**Date:** {DATE}
**Severity:** SEV{1|2|3|4}
**Duration:** {DURATION}
**Author:** {AUTHOR}

## Summary
One paragraph: what happened, what was the user impact.

## Timeline (UTC)
| Time | Event |
|------|-------|
| 10:01 | New deploy completed |
| 10:09 | SlowResponses alert fired (MTTD = 8min) |
| 10:11 | On-call ack'd; began diagnosis |
| 10:14 | Identified deploy as cause (TTI = 13min) |
| 10:16 | Rollback initiated |
| 10:18 | Service restored (MTTR = 17min) |

## Root cause
What actually caused this. Be specific. Don't say "human error" — say what process let the error happen.

## Detection
What detected it (alert? user report?). Could we detect faster?

## Response
What worked. What didn't.

## Action items
| Owner | Action | Priority | Due |
|-------|--------|----------|-----|
| @alice | Add canary deployment gate | P0 | 2026-06-01 |
| @bob | Faster burn-rate alert window (5m) | P1 | 2026-06-15 |

## Lessons learned
- What we did right
- What we got lucky on
- What we should change in process
