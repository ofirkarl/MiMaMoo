"""Before deploying the notification functions: is the project on the paid plan, and may this key deploy them?

    GOOGLE_APPLICATION_CREDENTIALS=<service-account.json> python3 tools/functions_preflight.py <project>

Prints one line for each. Exits 2 when the project is not ready yet (no Blaze plan, or the key may not deploy
functions), so the workflow skips the deploy quietly instead of failing.
"""
import sys

import google.auth
from google.auth.transport.requests import AuthorizedSession


def say(kind, msg):
    print('::%s::%s' % (kind, msg.replace('%', '%25').replace('\n', '%0A')), flush=True)


project = sys.argv[1]
creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
s = AuthorizedSession(creds)

r = s.get('https://cloudbilling.googleapis.com/v1/projects/%s/billingInfo' % project)
billing_off = False
if r.ok:
    on = r.json().get('billingEnabled')
    billing_off = not on
    say('notice' if on else 'warning', 'billing (Blaze plan): %s' % ('on' if on else 'OFF: functions need the Blaze plan'))
else:
    say('notice', 'billing: could not check (%s)' % r.status_code)

want = ['cloudfunctions.functions.create', 'iam.serviceAccounts.actAs', 'artifactregistry.repositories.create',
        'serviceusage.services.enable', 'run.services.create', 'eventarc.triggers.create', 'resourcemanager.projects.setIamPolicy']
r = s.post('https://cloudresourcemanager.googleapis.com/v1/projects/%s:testIamPermissions' % project, json={'permissions': want})
have = set(r.json().get('permissions', [])) if r.ok else set()
missing = [p for p in want if p not in have]
say('notice' if not missing else 'warning', 'key %s: %s' % (
    getattr(creds, 'service_account_email', '?'), 'may deploy functions' if not missing else 'missing ' + ', '.join(missing)))
if billing_off or missing:
    sys.exit(2)
