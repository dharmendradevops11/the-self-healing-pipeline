import requests
from datetime import datetime, timedelta, timezone

GITHUB_TOKEN = "ghp_..."
PAGERDUTY_TOKEN = "..."
REPO = "myorg/myservice"
DEPLOY_SERVICE_IDS = ["PABC123"]  # PagerDuty services owned by this pipeline
DAYS = 30

def get_deployments():
    """Fetch production deployments, following GitHub's pagination."""
    since = datetime.now(timezone.utc) - timedelta(days=DAYS)
    deployments = []
    page = 1
    while True:
        resp = requests.get(
            f"https://api.github.com/repos/{REPO}/deployments",
            headers={"Authorization": f"token {GITHUB_TOKEN}"},
            params={"environment": "production", "per_page": 100, "page": page},
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        for d in batch:
            created = datetime.fromisoformat(
                d["created_at"].rstrip("Z")
            ).replace(tzinfo=timezone.utc)
            if created > since:
                deployments.append(d)
        # Stop paging once the oldest item on the page is outside the window
        oldest = datetime.fromisoformat(
            batch[-1]["created_at"].rstrip("Z")
        ).replace(tzinfo=timezone.utc)
        if oldest < since:
            break
        page += 1
    return deployments

def get_incidents():
    """Fetch resolved incidents, scoped to deploy-related services only."""
    since = (datetime.now(timezone.utc) - timedelta(days=DAYS)).isoformat()
    incidents = []
    offset = 0
    while True:
        resp = requests.get(
            "https://api.pagerduty.com/incidents",
            headers={"Authorization": f"Token token={PAGERDUTY_TOKEN}"},
            params={
                "since": since,
                "statuses[]": "resolved",
                "service_ids[]": DEPLOY_SERVICE_IDS,
                "limit": 100,
                "offset": offset,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        incidents.extend(data["incidents"])
        if not data.get("more"):
            break
        offset += 100
    return incidents

deploys = get_deployments()
incidents = get_incidents()

deploy_frequency = len(deploys) / DAYS

mttr_seconds = [
    (datetime.fromisoformat(i["last_status_change_at"].rstrip("Z"))
     - datetime.fromisoformat(i["created_at"].rstrip("Z"))).total_seconds()
    for i in incidents
]
mttr_minutes = sum(mttr_seconds) / len(mttr_seconds) / 60 if mttr_seconds else 0

print(f"Deployment frequency: {deploy_frequency:.2f}/day")
print(f"MTTR: {mttr_minutes:.1f} minutes over {len(incidents)} incidents")
