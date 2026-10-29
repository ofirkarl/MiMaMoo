"""Publish the site to Firebase Hosting through its REST API (what `firebase deploy --only hosting` does).

    GOOGLE_APPLICATION_CREDENTIALS=<service-account.json> python3 tools/hosting_deploy.py <project> [site]

Needs only Firebase Hosting rights on the service account. Files are taken from the repository root,
skipping the same things firebase.json ignores (tools/, dotfiles, README.md, firebase.json).
"""
import gzip, hashlib, json, os, sys

import google.auth
from google.auth.transport.requests import AuthorizedSession

API = 'https://firebasehosting.googleapis.com/v1beta1/'
SKIP_TOP = {'tools', 'node_modules', 'firebase.json', 'README.md'}


def say(kind, msg):
    print('::%s::%s' % (kind, msg.replace('%', '%25').replace('\n', '%0A')), flush=True)


def files(root):
    out = {}
    for d, dirs, names in os.walk(root):
        rel = os.path.relpath(d, root)
        dirs[:] = [x for x in dirs if not x.startswith('.') and not (rel == '.' and x in SKIP_TOP)]
        for n in names:
            if n.startswith('.') or (rel == '.' and n in SKIP_TOP):
                continue
            p = os.path.join(d, n)
            out['/' + os.path.relpath(p, root).replace(os.sep, '/')] = gzip.compress(open(p, 'rb').read(), mtime=0)
    return out


def main():
    project = sys.argv[1]
    site = sys.argv[2] if len(sys.argv) > 2 else project
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    s = AuthorizedSession(creds)

    def call(method, url, **kw):
        r = s.request(method, url if url.startswith('http') else API + url, **kw)
        if r.status_code >= 300:
            raise SystemExit(say('error', '%s %s -> %s %s' % (method, url, r.status_code, r.text[:600])) or 1)
        return r.json() if r.content else {}

    # what this key may do, in one line (helps when something is missing)
    want = ['firebasehosting.sites.get', 'firebasehosting.sites.create', 'firebasehosting.sites.update']
    r = s.post('https://cloudresourcemanager.googleapis.com/v1/projects/%s:testIamPermissions' % project, json={'permissions': want})
    have = r.json().get('permissions', []) if r.ok else []
    say('notice', 'key %s may: %s' % (getattr(creds, 'service_account_email', '?'), ', '.join(have) or 'nothing of %s (%s)' % (want, r.status_code)))

    r = s.get(API + 'projects/%s/sites/%s' % (project, site))
    if r.status_code == 404:
        call('POST', 'projects/%s/sites?siteId=%s' % (project, site), json={})
        say('notice', 'created the Hosting site ' + site)
    elif not r.ok:
        call('GET', 'projects/%s/sites/%s' % (project, site))

    fs = files('.')
    by_hash = {hashlib.sha256(b).hexdigest(): b for b in fs.values()}
    v = call('POST', 'sites/%s/versions' % site, json={'config': {
        'headers': [{'glob': '**', 'headers': {'Cache-Control': 'no-cache'}}]}})['name']
    pop = call('POST', v + ':populateFiles', json={'files': {p: hashlib.sha256(b).hexdigest() for p, b in fs.items()}})
    for h in pop.get('uploadRequiredHashes', []):
        call('POST', pop['uploadUrl'] + '/' + h, data=by_hash[h], headers={'Content-Type': 'application/octet-stream'})
    call('PATCH', v + '?update_mask=status', json={'status': 'FINALIZED'})
    call('POST', 'sites/%s/releases?versionName=%s' % (site, v), json={})
    say('notice', 'published %d files to https://%s.web.app (%s)' % (len(fs), site, v.rsplit('/', 1)[-1]))

    # what the world now sees
    import requests, time
    want_sw = gzip.decompress(fs['/sw.js'])
    for i in range(10):
        got = [requests.get('https://%s.firebaseapp.com%s' % (site, p), timeout=20) for p in ('/', '/sw.js', '/__/auth/handler')]
        if got[1].content == want_sw:
            break
        time.sleep(3)
    say('notice', 'live check: / %s (%s), sw.js %s and %s, sign-in handler %s' % (
        got[0].status_code, 'the app' if 'MiMaMoo' in got[0].text else 'NOT the app', got[1].status_code,
        'current' if got[1].content == want_sw else 'OLD', got[2].status_code))

    # is Google sign-in switched on, and for which addresses
    IDT = 'https://identitytoolkit.googleapis.com/admin/v2/projects/%s/' % project
    g, c = s.get(IDT + 'defaultSupportedIdpConfigs/google.com'), s.get(IDT + 'config')
    lst = s.get(IDT + 'defaultSupportedIdpConfigs')
    say('notice', 'providers set up: %s' % ([x.get('name', '').rsplit('/', 1)[-1] + (' on' if x.get('enabled') else ' off') for x in lst.json().get('defaultSupportedIdpConfigs', [])] if lst.ok else lst.status_code))
    say('notice', 'sign-in: Google %s; anonymous %s; allowed addresses: %s' % (
        ('on' if g.json().get('enabled') else 'off') if g.ok else 'not set up (%s)' % g.status_code,
        ('on' if c.json().get('signIn', {}).get('anonymous', {}).get('enabled') else 'off') if c.ok else '?',
        ', '.join(c.json().get('authorizedDomains', [])) if c.ok else c.status_code))


if __name__ == '__main__':
    main()
