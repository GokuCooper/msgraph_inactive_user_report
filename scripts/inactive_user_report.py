"""
inactive_user_report.py
Week 9 | REST APIs and Microsoft Graph

Run from the repo root:  python scripts/inactive_user_report.py

What this script does, in plain English:
  1. Logs in to Microsoft Graph as an app (not as a person)
  2. Pulls every user in the Entra ID tenant, including when they last signed in
  3. Flags anyone who has not signed in for INACTIVE_DAYS or more,
     plus anyone who has never signed in at all
  4. Looks up the manager for each flagged user
  5. Saves a remediation report to a CSV file in the reports folder
"""

import csv
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import msal
import requests
from dotenv import load_dotenv

# The script lives in scripts/, so the repo root is one folder up.
# .env sits at the root next to .env.example, and reports/ is created there.
REPO_ROOT = Path(__file__).resolve().parent.parent

GRAPH_URL = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]

# Graph caps the page size at 120 users when you ask for signInActivity
PAGE_SIZE = 120

USER_FIELDS = ",".join([
    "id", "displayName", "userPrincipalName", "mail", "department", "jobTitle",
    "userType", "accountEnabled", "createdDateTime", "signInActivity",
])

REPORT_COLUMNS = [
    "DisplayName", "UserPrincipalName", "Department", "JobTitle", "UserType",
    "AccountEnabled", "Created", "LastActivity", "DaysInactive", "Finding",
    "ManagerName", "ManagerEmail", "RecommendedAction",
]

ERROR_HINTS = {
    401: "The token was rejected. Recheck TENANT_ID, CLIENT_ID, and CLIENT_SECRET in your .env file.",
    403: ("Access denied. Make sure User.Read.All and AuditLog.Read.All are added as "
          "Application permissions (not Delegated) and that admin consent was granted. "
          "Reading signInActivity also needs an Entra ID P1 or P2 license in the tenant."),
}


# ---------- Settings and sign in ----------

def load_settings():
    """Read the secrets and options from the .env file at the repo root."""
    load_dotenv(REPO_ROOT / ".env")
    settings = {
        "tenant_id": os.getenv("TENANT_ID", "").strip(),
        "client_id": os.getenv("CLIENT_ID", "").strip(),
        "client_secret": os.getenv("CLIENT_SECRET", "").strip(),
    }
    missing = [name.upper() for name, value in settings.items() if not value]
    if missing:
        sys.exit(f"Missing values in .env: {', '.join(missing)}. "
                 "Is the file named .env (not .env.txt) and in the repo root next to .env.example?")

    settings["inactive_days"] = int(os.getenv("INACTIVE_DAYS", "90"))
    exclude = os.getenv("EXCLUDE_UPNS", "")
    settings["exclude_upns"] = {u.strip().lower() for u in exclude.split(",") if u.strip()}
    return settings


def get_token(settings):
    """Trade the app's ID and secret for an access token (client credentials flow)."""
    app = msal.ConfidentialClientApplication(
        client_id=settings["client_id"],
        authority=f"https://login.microsoftonline.com/{settings['tenant_id']}",
        client_credential=settings["client_secret"],
    )
    result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)
    if "access_token" not in result:
        sys.exit(f"Token request failed.\n  Error: {result.get('error')}\n"
                 f"  Details: {result.get('error_description')}")
    return result["access_token"]


# ---------- Talking to Graph ----------

def graph_get(url, token, params=None, retries=3):
    """Send a GET request to Graph. If Graph says slow down (429), wait and try again."""
    headers = {"Authorization": f"Bearer {token}"}
    response = None
    for attempt in range(retries + 1):
        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code == 429 and attempt < retries:
            wait = int(response.headers.get("Retry-After", "10"))
            print(f"  Graph asked us to slow down. Waiting {wait} seconds...")
            time.sleep(wait)
            continue
        break
    return response


def stop_on_error(response, action):
    """Print Graph's error in a readable way, with a hint, then stop the script."""
    try:
        error = response.json().get("error", {})
    except ValueError:
        error = {}
    print(f"\nGraph error while {action}: HTTP {response.status_code}")
    print(f"  Code:    {error.get('code', 'unknown')}")
    print(f"  Message: {error.get('message', response.text[:300])}")
    hint = ERROR_HINTS.get(response.status_code)
    if hint:
        print(f"  Hint:    {hint}")
    sys.exit(1)


def get_all_users(token):
    """Pull every user, one page at a time, following @odata.nextLink until there are no more pages."""
    users, page = [], 1
    url = f"{GRAPH_URL}/users"
    params = {"$select": USER_FIELDS, "$top": PAGE_SIZE}
    while url:
        response = graph_get(url, token, params)
        if response.status_code != 200:
            stop_on_error(response, "listing users")
        data = response.json()
        batch = data.get("value", [])
        users.extend(batch)
        print(f"  Page {page}: {len(batch)} users")
        url = data.get("@odata.nextLink")
        params = None  # the next link already has the whole query baked in
        page += 1
    return users


def get_manager(user_id, token):
    """Look up a user's manager. A 404 just means nobody is assigned."""
    response = graph_get(
        f"{GRAPH_URL}/users/{user_id}/manager", token,
        params={"$select": "displayName,mail,userPrincipalName"},
    )
    if response.status_code == 404:
        return "No manager assigned", ""
    if response.status_code != 200:
        return f"Lookup failed (HTTP {response.status_code})", ""
    manager = response.json()
    return manager.get("displayName", ""), manager.get("mail") or manager.get("userPrincipalName", "")


# ---------- Deciding who is inactive ----------

def parse_time(value):
    """Turn a Graph timestamp like 2026-09-01T14:22:05Z into a Python datetime."""
    if not value:
        return None
    value = re.sub(r"\.(\d{6})\d+", r".\1", value.replace("Z", "+00:00"))
    return datetime.fromisoformat(value)


def last_activity(user):
    """Newest of the interactive and non interactive sign in times, or None if never."""
    activity = user.get("signInActivity") or {}
    stamps = [
        parse_time(activity.get("lastSignInDateTime")),
        parse_time(activity.get("lastNonInteractiveSignInDateTime")),
    ]
    stamps = [s for s in stamps if s]
    return max(stamps) if stamps else None


def classify(user, now, cutoff, inactive_days):
    """Return (finding, last_activity, days_inactive). Finding is None when the user is fine."""
    last = last_activity(user)
    created = parse_time(user.get("createdDateTime"))
    if last is None:
        if created and created <= cutoff:
            return "Never signed in", None, (now - created).days
        return None, None, None  # brand new account, give the new hire time
    if last <= cutoff:
        return f"Inactive {inactive_days}+ days", last, (now - last).days
    return None, last, None


def is_external(user):
    """External if Graph says Guest, or if the UPN carries the #EXT# marker.
    An invited account can be set to userType Member and still be external,
    so checking userType alone misses it."""
    upn = user.get("userPrincipalName") or ""
    return user.get("userType") == "Guest" or "#EXT#" in upn.upper()


def describe_user_type(user):
    user_type = user.get("userType", "")
    if user_type == "Member" and is_external(user):
        return "Member (external)"
    return user_type


def recommend_action(user, exclude_upns):
    upn = (user.get("userPrincipalName") or "").lower()
    if upn in exclude_upns:
        return "Excluded (break glass or service account). Verify it is monitored. Do not disable."
    if not user.get("accountEnabled"):
        return "Already disabled. Confirm with manager, remove licenses and group access, then delete."
    if is_external(user):
        return "External account. Confirm with the inviting sponsor, then remove access."
    return "Confirm with manager, then disable the account."


# ---------- Report ----------

def write_report(rows, inactive_days):
    folder = REPO_ROOT / "reports"
    folder.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = folder / f"inactive_users_{inactive_days}d_{stamp}.csv"
    # utf-8-sig so Excel opens names with accents correctly
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def main():
    started = time.perf_counter()
    settings = load_settings()
    days = settings["inactive_days"]
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    print(f"Inactive account report | threshold: {days} days | cutoff: {cutoff:%Y-%m-%d}")
    print("Requesting access token...")
    token = get_token(settings)
    print("Token received. Pulling users from Microsoft Graph...")
    users = get_all_users(token)

    rows = []
    for user in users:
        finding, last, days_inactive = classify(user, now, cutoff, days)
        if not finding:
            continue
        manager_name, manager_email = get_manager(user["id"], token)
        created = parse_time(user.get("createdDateTime"))
        rows.append({
            "DisplayName": user.get("displayName", ""),
            "UserPrincipalName": user.get("userPrincipalName", ""),
            "Department": user.get("department") or "",
            "JobTitle": user.get("jobTitle") or "",
            "UserType": describe_user_type(user),
            "AccountEnabled": user.get("accountEnabled"),
            "Created": f"{created:%Y-%m-%d}" if created else "",
            "LastActivity": f"{last:%Y-%m-%d %H:%M} UTC" if last else "Never",
            "DaysInactive": days_inactive,
            "Finding": finding,
            "ManagerName": manager_name,
            "ManagerEmail": manager_email,
            "RecommendedAction": recommend_action(user, settings["exclude_upns"]),
        })

    rows.sort(key=lambda r: r["DaysInactive"], reverse=True)
    path = write_report(rows, days)

    never = sum(1 for r in rows if r["Finding"] == "Never signed in")
    no_manager = sum(1 for r in rows if r["ManagerName"] == "No manager assigned")
    elapsed = time.perf_counter() - started

    print("\n========== SUMMARY ==========")
    print(f"Users scanned:           {len(users)}")
    print(f"Flagged for review:      {len(rows)}")
    print(f"  Inactive {days}+ days:   {len(rows) - never}")
    print(f"  Never signed in:       {never}")
    print(f"Flagged with no manager: {no_manager}")
    print(f"Run time:                {elapsed:.1f} seconds")
    print(f"Report saved to:         {path}")


if __name__ == "__main__":
    main()
