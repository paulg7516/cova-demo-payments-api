# Cova end-to-end test

Real numbers in Datadog, real deploys on GitHub, and a stand-in deploy
pipeline, so one incident can go through all five stages for real:
Detect, Investigate, Fix (rollback), Verify, Prevent.

`simulate.py` plays the running service: every 10 seconds it checks which
commit GitHub says is live in `production`, sends 120 requests through this
app (12% fail if the live commit's message contains `[e2e-bad]`), and sends
the counts to Datadog as `e2e.requests` / `e2e.errors`, tagged
`service:cova-demo-payments-api`. When Cova rolls back (a new GitHub
deployment of the previous commit), the next loop runs the old commit and
the errors stop, like a real pipeline redeploying the old build.

No Docker or Datadog agent needed: metrics go straight to Datadog's API.

## You need

1. A Datadog account (the free trial is enough), with an **API key** and an
   **Application key**: Organization Settings > API Keys / Application Keys.
2. Python 3.9+ and `gh` signed in to the account that owns this repo.
3. In Cova: a workspace you can make changes in (not the Demo workspace,
   which only simulates), with the GitHub app installed on this repo.
4. A decision on rollback: `COVA_ROLLBACK_ENABLED=1` on the Cova server for
   the test (switch it back off after). Without it the rollback is preview
   only and the test stops at Fix.

## One-time setup (about 10 minutes)

```bash
cd cova-demo-payments-api && git checkout e2e-kit
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r e2e/requirements.txt
git push -u origin e2e-kit                     # deployments need pushed commits
.venv/bin/python e2e/deploy.py                 # mark the current commit as live (good)
export DD_API_KEY=... DD_SITE=datadoghq.com    # your site, e.g. datadoghq.eu
.venv/bin/python e2e/simulate.py               # leave running in its own terminal
```

In Cova:

| Where | Set |
|---|---|
| Settings > Data sources | Connect Datadog (API key + Application key + site) |
| Settings > Services | Add `cova-demo-payments-api` (must match the repo name: that's how deploys are matched) |
| Settings > Metrics, Error rate | `100 * sum:e2e.errors{service:{service}}.as_count() / sum:e2e.requests{service:{service}}.as_count()` then **Test** on `cova-demo-payments-api` (expect about 0.2%) |
| Rules | Error rate (5xx) on |
| Settings > API keys | An Anthropic key, so Cova runs its own checks |

Wait until the Datadog Metrics Explorer shows `e2e.requests` (1 to 2 minutes).

## Scenario A: bad deploy, rollback, verify, prevent

```bash
git commit --allow-empty -m "Retry Stripe calls on timeout [e2e-bad]" && git push
.venv/bin/python e2e/deploy.py                 # ship the bad build
```

| Stage | Expect | Roughly when |
|---|---|---|
| Detect | Incident "Error rate (5xx) on cova-demo-payments-api", about 12% | 2 to 4 min (Datadog lag + 2 breaches in a row) |
| Investigate | Changed: the `[e2e-bad]` commit, minutes before. Cova checked: other services, deploys before/after | same minute; checks within ~30s |
| Fix | "Roll back deploy" offered after the 3 min safety wait; approve it | 3 min after it opened |
| Verify | simulate.py shows the old commit live and ~0% errors; "Fix verified: the rollback worked. 12% → 0.2% ... Over the threshold for about N min" | 2 to 4 min after approving |
| Prevent | "Let Cova run the fix" (turn on Autopilot for this rule), or "Add an SLO" if the service has an open SLO gap | at close |

## Scenario B: someone fixes it by redeploying

Ship a bad commit as in A, wait for the incident, then deploy the good
commit yourself (`.venv/bin/python e2e/deploy.py <good sha>`) and don't
touch Cova. Expect Verify: "Recovered after deploy <sha> by @you".

## Scenario C: a short blip

With a good commit live: stop simulate.py and run
`.venv/bin/python e2e/simulate.py --blip 240` (4 minutes of errors). Expect an
incident that clears on its own, and Prevent: "Fewer false alarms".

## Write down for each stage

What Cova said, how long it took, and anything wrong or confusing: that
list is the fix pass after the test.

## Afterwards

Stop simulate.py, set `COVA_ROLLBACK_ENABLED` back to off, and optionally
delete the `production` deployments in the repo's Environments settings.

If the rollback fails with a 403, the GitHub app needs **Deployments: Read
and write** on this repo.
