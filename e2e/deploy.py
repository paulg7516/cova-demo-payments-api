"""Mark a commit as deployed to production on GitHub, the way a CD pipeline
does after it ships a build. Cova reads these deployments to match a
deploy to an incident, and rolls back by creating one for the previous
commit.

    python e2e/deploy.py            # deploy the current HEAD (must be pushed)
    python e2e/deploy.py <sha>      # deploy a specific commit
"""
from __future__ import annotations

import subprocess
import sys

import httpx

from simulate import REPO, gh_token


def main() -> None:
    sha = sys.argv[1] if len(sys.argv) > 1 else subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    h = {"Authorization": f"Bearer {gh_token()}", "Accept": "application/vnd.github+json"}
    with httpx.Client(timeout=15, headers=h) as c:
        r = c.post(f"https://api.github.com/repos/{REPO}/deployments", json={
            "ref": sha, "environment": "production", "auto_merge": False, "required_contexts": [],
            "description": "e2e deploy",
        })
        if r.status_code >= 300:
            sys.exit(f"GitHub refused the deployment ({r.status_code}): {r.text[:300]}\n"
                     f"Is {sha[:7]} pushed to {REPO}?")
        dep = r.json()
        c.post(f"https://api.github.com/repos/{REPO}/deployments/{dep['id']}/statuses",
               json={"state": "success", "environment": "production"}).raise_for_status()
    print(f"Deployed {sha[:7]} to production (deployment {dep['id']}).")


if __name__ == "__main__":
    main()
