# App registration configuration

Client ID, tenant ID, object ID, and secret values are intentionally left out of this repo. They live only in the local `.env` file, which `.gitignore` keeps off GitHub.

## Registration

| Setting | Value | Why |
| --- | --- | --- |
| Name | `DKN-IAM-Graph-Inactive-Report` | Says what it does, so anyone reviewing Enterprise apps knows what this identity is for |
| Supported account types | Single tenant (DKN IAM Workforce Lab only) | An internal audit script has no reason to accept sign ins from other organizations |
| Redirect URI | None | Only needed when a person signs in through a browser. This app signs in as itself |
| Credential | Client secret, about 90 days (expires 12/31/2026) | Short lifetime limits how long a leaked secret is useful |
| Sign in flow | OAuth 2.0 client credentials (`acquire_token_for_client` in MSAL) | No user is present when a scheduled report runs |

## Permissions

| API | Permission | Type | Admin consent | Status | Used by the script for |
| --- | --- | --- | --- | --- | --- |
| Microsoft Graph | `User.Read.All` | Application | Required | Granted | Listing users and reading each user's manager |
| Microsoft Graph | `AuditLog.Read.All` | Application | Required | Granted | Reading the `signInActivity` property |
| Microsoft Graph | `User.Read` | Delegated | Not required | Default, unused | Added automatically at registration. The script never signs in as a user. Listed under what I would change |

Not requested on purpose: any `ReadWrite` permission, `Directory.Read.All`, and `Directory.ReadWrite.All`. The script only reads, so it only holds read permissions.

## Delegated versus application, side by side

| | Graph Explorer (Screenshots 04 to 07) | This app (Screenshots 08 to 10) |
| --- | --- | --- |
| Who is acting | labadmin, signed in | The app itself, nobody signed in |
| Permission type | Delegated | Application |
| Effective access | Limited to what labadmin can do | Exactly the granted permissions, tenant wide |
| Good for | Testing a query by hand | Scheduled, unattended automation |

## Secret handling

1. The secret value was copied once into `.env` at the repo root and never into the script.
2. `.env.example` in the repo shows the setting names with placeholder values.
3. `.gitignore` excludes `.env`, `.venv/`, `__pycache__/`, and `reports/`.
4. A screenshot taken before blurring showed most of the first secret value. That secret was treated as exposed: revoked and replaced with a new one. Screenshot 11 is blurred.

## Requirement outside the app

Reading `signInActivity` requires a Microsoft Entra ID P1 or P2 license in the tenant. This lab uses the P2 trial set up in Week 7, which expires October 26, 2026.
