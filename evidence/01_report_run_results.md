# Report run results

All runs were made on October 2, 2026 against the DKN IAM Workforce Lab tenant (Microsoft Entra ID P2 trial) from a Windows laptop running Python 3.12.10 in a virtual environment. The script signs in as the `DKN-IAM-Graph-Inactive-Report` app registration with the client credentials flow.

Cutoff dates are in UTC. Report file names use local time (Eastern).

## Runs

| # | Threshold | Cutoff (UTC) | Users scanned | Pages | Flagged | Inactive | Never signed in | Flagged with no manager | Run time | Report file | Screenshot |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 90 days | 2026-07-04 | 8 | 1 | 0 | 0 | 0 | 0 | 1.3 s | `inactive_users_90d_20261002_0132.csv` | 16, 17 |
| 2 | 7 days | 2026-09-25 | 8 | 1 | 0 | 0 | 0 | 0 | 1.3 s | `inactive_users_7d_20261002_0135.csv` | console reviewed, not kept |
| 3 | 3 days (before fix) | 2026-09-29 | 8 | 1 | 6 | 3 | 3 | 3 | 3.0 s | `inactive_users_3d_20261002_0138.csv` | 18, 19 |
| 4 | 3 days (after fix) | 2026-09-29 | 8 | 1 | 6 | 3 | 3 | 3 | not captured | `inactive_users_3d_20261002_0144.csv` | 20 |

## What each run proves

**Run 1, production policy.** The script authenticated, pulled every user, and correctly found nobody inactive for 90 days. The tenant is only a few weeks old, so zero is the right answer.

**Run 2, first threshold test.** Every account had activity after September 25. The three accounts that never signed in were created on September 26, which is after the cutoff, so the new hire grace rule correctly treated them as too new to judge.

**Run 3, logic proof.** Moving the cutoff to September 29 flagged exactly the accounts predicted from Graph Explorer data (Goku Cooper and Jamison Fawkes, last activity September 26) plus Maugaloa Malosi and the three never signed in accounts, now old enough to count. Break Glass and labadmin, both active on September 29, were correctly left off.

**Run 4, regression check.** After the external account fix, only Goku Cooper's `UserType` and `RecommendedAction` changed. All other rows were identical to Run 3.

## Run time note

Runs 1 and 2 made 2 network calls (one token, one page of users). Run 3 added 6 manager lookups, one per flagged account, which accounts for the extra 1.7 seconds. At larger scale, the manager lookups could move into the user query with `$expand=manager` to save a call per flagged user.

## Completeness check

The tenant holds 8 accounts: breakglass01, Goku Cooper (external), DKN Lab Admin, Jamison Fawkes, Lena Oxton, Lúcio Correia dos Santos, Maugaloa Malosi, and Vaira Singhania. Every run scanned 8, so the script saw the whole tenant.
