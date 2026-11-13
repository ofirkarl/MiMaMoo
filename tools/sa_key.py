"""Checks the service-account key a workflow wrote to a file, and repairs a paste that wrapped its long lines.

    python3 tools/sa_key.py <key.json>

Prints only the key's shape (never its contents), so a wrong paste is easy to spot in a public log.
"""
import base64, json, re, sys

path = sys.argv[1]
raw = open(path).read()
try:
    k = json.loads(raw)
    msg = "key: JSON ok, type=%s, project=%s, has client_email=%s, private_key looks right=%s, %d chars" % (
        k.get("type"), k.get("project_id"), bool(k.get("client_email")),
        str(k.get("private_key", "")).startswith("-----BEGIN PRIVATE KEY-----"), len(raw))
except Exception as e:
    t = raw.strip()
    cls = lambda c: "quote" if c == '"' else "newline" if c == "\n" else "space" if c.isspace() else "letter/digit" if c.isalnum() else "U+%04X" % ord(c)
    pos = getattr(e, "pos", None)
    msg = ("key: not JSON: %s at line %s col %s (char there: %s), %d chars, %d lines, braces at ends=%s, "
           "straight quotes=%d, curly quotes=%d, long dashes=%d, has PRIVATE KEY=%s, has client_email=%s" % (
               getattr(e, "msg", type(e).__name__), getattr(e, "lineno", "?"), getattr(e, "colno", "?"),
               cls(raw[pos]) if pos is not None and pos < len(raw) else "end", len(raw), raw.count("\n") + 1,
               t[:1] == "{" and t[-1:] == "}", raw.count('"'), sum(raw.count(c) for c in "“”‘’"),
               sum(raw.count(c) for c in "–—"), "PRIVATE KEY" in raw, "client_email" in raw))
print("::notice::" + msg)
# a paste that wrapped long lines leaves raw line breaks inside the values: take them out again
if not msg.startswith("key: JSON ok"):
    out, inside, esc, dropped = [], False, False, 0
    for c in raw:
        if inside and c in "\r\n":
            dropped += 1
            continue
        out.append(c)
        if esc:
            esc = False
        elif c == "\\":
            esc = inside
        elif c == '"':
            inside = not inside
    try:
        k = json.loads("".join(out))
        body = re.sub(r"-----[A-Z ]+-----|\s", "", k.get("private_key", ""))
        base64.b64decode(body, validate=True)
        open(path, "w").write(json.dumps(k))
        print("::notice::key repaired: removed %d line breaks inside values; the private key decodes" % dropped)
    except Exception as e:
        print("::error::key could not be repaired (%s). Please paste it again." % type(e).__name__)
        sys.exit(1)
