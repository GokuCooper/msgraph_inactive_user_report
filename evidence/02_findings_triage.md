# Findings triage (3 day demo threshold)

The production threshold is 90 days, and at 90 days this tenant has zero findings. These verdicts use the 3 day demo run to show how each finding would be handled in a real review. Source: `04_inactive_users_3_day_after_fix.csv` and Screenshot 20.

## Flagged accounts

| Account | Type | Finding | Days | Manager | Recommended action from the script | Verdict | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Goku Cooper | Member (external) | Inactive 3+ days | 6 | No manager assigned | Confirm with the inviting sponsor, then remove access | **Remediate first** | External account with member level access, no manager, and 1 directory role (Screenshot 21). Nobody inside the company owns it. Highest risk on the list |
| Lúcio Correia dos Santos | Member | Never signed in | 6 | No manager assigned | Confirm with manager, then disable | **Escalate** | He manages Jamison, Lena, and Maugaloa but has never signed in himself. The approver for three remediation decisions is a stale account, so the chain of ownership is broken |
| Vaira Singhania | Member | Never signed in | 6 | No manager assigned | Confirm with manager, then disable | **Remediate** | Finance user with no owner. Assign a manager before any access decision can be made |
| Lena Oxton | Member | Never signed in | 6 | Lúcio Correia dos Santos | Confirm with manager, then disable | **Escalate** | Her manager is the ghost account above, so the review goes one level up |
| Jamison Fawkes | Member | Inactive 3+ days | 6 | Lúcio Correia dos Santos | Confirm with manager, then disable | Accept for lab | Test user last active September 26. Only flagged because the demo threshold is artificially short |
| Maugaloa Malosi | Member | Inactive 3+ days | 6 | Lúcio Correia dos Santos | Confirm with manager, then disable | Accept for lab, note | Same as Jamison, with one note: since Week 7 she is eligible for User Administrator through PIM. In a real review, an inactive account with an eligible admin role gets checked first |

## Accounts not flagged

| Account | Last activity (UTC) | Why it was not flagged |
| --- | --- | --- |
| Break Glass Emergency Access 01 | 2026-09-29 23:29 | Active after the September 29 cutoff. Also listed in `EXCLUDE_UPNS`, so even when stale it would only be marked "verify it is monitored," never disabled |
| DKN Lab Admin (labadmin) | 2026-09-29 23:49 (non interactive) | Active after the cutoff. Its last interactive sign in was September 26, so a script that only read interactive sign ins would have flagged it wrongly |

## Patterns worth reporting

1. **3 of 6 flagged accounts have no manager.** An inactive account with no manager has no one to approve disabling it, which is how stale accounts survive for years.
2. **The external account was the riskiest finding and the one the first version of the script mislabeled.** See Snag 8 in the README.
3. **Ownership problems stack.** Lena's manager is Lúcio, and Lúcio has no manager. One missing data point blocks two reviews.
