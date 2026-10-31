"""Opens the live app in a real (headless) browser and reports what a first-time visitor sees.

    python3 tools/live_check.py

1. the old github.io address forwards to the Firebase address
2. the app starts there, connected to the cloud, and offers Google sign-in
3. pressing sign-in opens Google's own page (so the Google provider is set up)
"""
import re
from playwright.sync_api import sync_playwright

OLD = 'https://ofirkarl.github.io/MiMaMoo/'
NEW_HOST = 'mimamoo-b37c7.firebaseapp.com'


def say(kind, msg):
    print('::%s::%s' % (kind, msg.replace('%', '%25').replace('\n', '%0A')), flush=True)


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, locale='he-IL', service_workers='block')
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append('pageerror: %s' % e))
    pg.on('console', lambda m: m.type == 'error' and errs.append('console: %s' % m.text[:200]))

    pg.goto(OLD)
    try:
        pg.wait_for_url(re.compile(re.escape(NEW_HOST)), timeout=30000)
        say('notice', 'old address forwards to ' + pg.url.split('#')[0])
    except Exception:
        say('error', 'old address did not forward, still at ' + pg.url.split('#')[0])

    pg.wait_for_timeout(6000)
    say('notice', 'address after arrival: %s (import consumed: %s)' % (pg.url.split('#')[0], '#import=' not in pg.url))
    body = pg.inner_text('body')
    say('notice', 'first screen: ' + ' | '.join(l.strip() for l in body.splitlines() if l.strip())[:400])
    say('notice', 'cloud: %s; sign-in card: %s' % (
        pg.evaluate("typeof S !== 'undefined' ? S.mode : '?'"), 'כניסה עם Google' in body))

    btn = pg.locator('[data-act="login"]').first
    if btn.count():
        try:
            with ctx.expect_page(timeout=15000) as pop:
                btn.click()
            w = pop.value
            w.wait_for_load_state('domcontentloaded', timeout=20000)
            w.wait_for_timeout(3000)
            host = re.sub(r'^https?://([^/]+).*$', r'\1', w.url)
            say('notice', 'sign-in opens: %s (%s)' % (host, (w.title() or '')[:80]))
            w.close()
        except Exception as e:
            say('error', 'sign-in did not open Google: %s' % str(e)[:300])
    # 4. a category renamed in Settings keeps its new name after a reload (written to the cloud, read back)
    try:
        pg.click('[data-act="settings"]'); pg.wait_for_timeout(800)
        pg.click('[data-fold="cats"]'); pg.wait_for_timeout(500)
        before = pg.locator('#r-cats .set-label').all_inner_texts()
        pg.locator('#r-cats [data-cat-edit]').nth(5).click(); pg.wait_for_timeout(800)
        pg.fill('#cat-name', 'בדיקת שם'); pg.locator('.sheet button[type="submit"]').click(); pg.wait_for_timeout(1500)
        right_away = pg.locator('#r-cats .set-label').all_inner_texts()
        toast = pg.inner_text('#toast') if pg.locator('#toast.show').count() else ''
        pg.wait_for_timeout(4000)
        pg.reload(); pg.wait_for_timeout(7000)
        pg.click('[data-act="settings"]'); pg.wait_for_timeout(800); pg.click('[data-fold="cats"]'); pg.wait_for_timeout(500)
        after = pg.locator('#r-cats .set-label').all_inner_texts()
        say('notice' if 'בדיקת שם' in after else 'error', 'category rename: before %s | right away %s | toast %r | after reload %s' % (before, right_away, toast, after))
    except Exception as e:
        say('error', 'category rename check failed to run: %s' % str(e)[:300])
    pg.wait_for_timeout(1500)
    if errs:
        say('warning', 'page errors: ' + ' || '.join(errs[:8]))
    else:
        say('notice', 'no page errors')
    b.close()
