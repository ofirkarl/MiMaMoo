import asyncio, json, os, re, shutil, sys, threading, http.server, functools
from playwright.async_api import async_playwright
D = os.path.dirname(os.path.abspath(__file__)); DIST = os.path.join(D, 'site')
if os.path.exists(DIST): shutil.rmtree(DIST)
shutil.copytree(os.path.join(D, '..', 'dist'), DIST)
open(os.path.join(DIST, 'config.js'), 'w').write("window.MM_CONFIG = {firebase: {apiKey: 'test', authDomain: 'x', projectId: 'x', appId: 'x'}};\n")
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8765), functools.partial(http.server.SimpleHTTPRequestHandler, directory=DIST))
threading.Thread(target=srv.serve_forever, daemon=True).start()
STORE = {}; LOG = []
def allowed(uid, path):
    p = path.split('/')
    if p[0] == 'spaces' and len(p) >= 3: return True
    if p[0] == 'users' and len(p) >= 3 and p[1] == uid: return True
    return False
def fs(op, payload):
    a = json.loads(payload); path = a['path']; uid = a.get('uid')
    if not allowed(uid, path): LOG.append(('DENY', op, path)); return json.dumps({'err': 'permission-denied'})
    if op == 'set': STORE[path] = a['data']; LOG.append(('set', path))
    elif op == 'update':
        if path not in STORE: return json.dumps({'err': 'not-found'})
        d = STORE[path]
        for segs, v in a['pairs']:
            cur = d
            for s in segs[:-1]:
                if not isinstance(cur.get(s), dict): cur[s] = {}
                cur = cur[s]
            cur[segs[-1]] = v
        LOG.append(('update', path))
    elif op == 'delete': STORE.pop(path, None); LOG.append(('delete', path))
    elif op == 'get': return json.dumps({'ok': STORE.get(path)})
    elif op == 'list':
        n = len(path.split('/'))
        return json.dumps({'ok': sorted([[k.split('/')[-1], v] for k, v in STORE.items() if k.startswith(path + '/') and len(k.split('/')) == n + 1])})
    return json.dumps({'ok': True})
FAKE = {f'https://www.gstatic.com/firebasejs/10.14.1/firebase-{m}.js': open(os.path.join(D, f'fake-{m}.js')).read() for m in ['app', 'auth', 'firestore']}
async def setup(ctx):
    await ctx.expose_function('__fs', fs)
    async def route(r):
        u = r.request.url
        if u in FAKE: await r.fulfill(status=200, content_type='application/javascript', body=FAKE[u], headers={'Access-Control-Allow-Origin': '*'})
        else: await r.abort()
    await ctx.route('https://www.gstatic.com/**', route)
    await ctx.route('https://fonts.googleapis.com/**', lambda r: r.abort())
    await ctx.route('https://fonts.gstatic.com/**', lambda r: r.abort())

HOME_A = 'HOMEAaaaaaaaaaaaaaaaa'
STORE['spaces/' + HOME_A + '/events/old1'] = {'name': 'טיול ישן', 'date': '2026-12-20', 'created': 1, 'bank': [], 'essentials': []}
async def new_trip(pg, name):
    await pg.locator('[data-act="new-trip"]').first.click(); await pg.wait_for_timeout(400)
    await pg.fill('#tf-name', name)
    await pg.locator('form[data-form="new-trip"] button[type="submit"]').click(); await pg.wait_for_timeout(1500)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); errs = []
        A = await b.new_context(viewport={'width': 400, 'height': 820}, service_workers='block'); await setup(A)
        await A.add_init_script("if (!localStorage.getItem('mm:home')) { localStorage.setItem('mm:home', '%s'); localStorage.setItem('wbw:myName', 'אופיר'); localStorage.setItem('wbw:joinAsked', '1'); }" % HOME_A)
        pa = await A.new_page(); pa.on('pageerror', lambda e: errs.append('A ' + str(e)))
        await pa.goto('http://127.0.0.1:8765/'); await pa.wait_for_timeout(1200)
        print('A home shows:', await pa.locator('#r-trips .trip-name').all_inner_texts())
        await new_trip(pa, 'קמפינג חדש')
        evs = sorted(k for k in STORE if re.match(r'spaces/[^/]+/events/[^/]+$', k))
        print('event docs:', evs)
        new_key = [k for k in evs if not k.endswith('old1')][0]; sid, eid = new_key.split('/')[1], new_key.split('/')[3]
        print('new event in its own space:', sid != HOME_A)
        print('templates live in home:', all(k.startswith('spaces/' + HOME_A + '/templates/') for k in STORE if '/templates/' in k), sum('/templates/' in k for k in STORE))
        await pa.fill('#ag-name-' + eid, 'אוהל'); await pa.press('#ag-name-' + eid, 'Enter'); await pa.wait_for_timeout(700)
        print('item stored in the event space:', [k for k in STORE if '/items/' in k])
        await pa.click('[data-act="invite"]'); await pa.wait_for_timeout(400)
        link = await pa.inner_text('#trip-code'); print('invite link:', link)
        await pa.keyboard.press('Escape'); await pa.wait_for_timeout(200)
        await pa.click('[data-act="home"]'); await pa.wait_for_timeout(500)
        print('A home now:', await pa.locator('#r-trips .trip-name').all_inner_texts())
        # B opens the invitation
        B = await b.new_context(viewport={'width': 400, 'height': 820}, service_workers='block'); await setup(B)
        await B.add_init_script("localStorage.setItem('wbw:myName', 'דנה');")
        pb = await B.new_page(); pb.on('pageerror', lambda e: errs.append('B ' + str(e)))
        await pb.goto(link.replace('http://127.0.0.1:8765/', 'http://127.0.0.1:8765/')); await pb.wait_for_timeout(1800)
        print('B lands on:', await pb.evaluate("document.querySelector('.trip-title') && document.querySelector('.trip-title').textContent"))
        if await pb.locator('#sheet-root.open').count(): await pb.locator('#sheet-root .one-row input').fill('דנה'); await pb.locator('#sheet-root form[data-form="add-me"] button').click(); await pb.wait_for_timeout(600)
        await pb.fill('#ag-name-' + eid, 'מחצלת'); await pb.press('#ag-name-' + eid, 'Enter'); await pb.wait_for_timeout(800)
        await pb.click('[data-act="home"]'); await pb.wait_for_timeout(600)
        print('B home shows (no old A event):', await pb.locator('#r-trips .trip-name').all_inner_texts())
        await new_trip(pb, 'יום הולדת של דנה')
        await pb.click('[data-act="home"]'); await pb.wait_for_timeout(600)
        print('B home now:', await pb.locator('#r-trips .trip-name').all_inner_texts())
        await pa.wait_for_timeout(800)
        print('A home (no B private event):', await pa.locator('#r-trips .trip-name').all_inner_texts())
        await pa.locator('#r-trips .trip-card', has_text='קמפינג חדש').click(); await pa.wait_for_timeout(900)
        print('A sees B item:', await pa.locator('#r-group .item-name').all_inner_texts())
        # A reloads: the remembered spaces still show
        await pa.goto('http://127.0.0.1:8765/'); await pa.wait_for_timeout(1500)
        print('A after reload:', await pa.locator('#r-trips .trip-name').all_inner_texts())
        print('errors', [e for e in errs if 'Service Worker' not in e] or 'none')
        await b.close()
    srv.shutdown()
asyncio.run(main())

