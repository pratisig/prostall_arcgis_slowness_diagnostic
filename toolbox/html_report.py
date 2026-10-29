r"""Render a prostall report document as one self-contained HTML file.

A pure function over the document prostall.run() returns: no ArcGIS import, no
network, no template engine, no external asset. That matters twice over. The
report is opened from a file:// URL on a workstation that may be offline or
air-gapped, so a CDN link would be a broken page. And the report is full of
machine-supplied strings - account names, folder paths off a share, network
adapter descriptions, Defender exclusion paths, event-log text - so every one
of them is escaped on the way out. A folder on a file server whose name
contains markup must not become script in the operator's browser.

    import prostall, html_report
    doc = prostall.run(prostall.Env(), {...})
    open(path, "w", encoding="utf-8").write(html_report.render_html(doc))
"""

from __future__ import print_function

import json
import os

try:                                  # html.escape is stdlib on every Pro Python
    from html import escape as _esc
except ImportError:                   # pragma: no cover - Python 2 fallback
    from cgi import escape as _cgi_escape

    def _esc(text, quote=True):
        return _cgi_escape("%s" % text, quote)

# The five statuses, and nothing else: the same contract prostall enforces. A
# status the renderer does not know gets the neutral style, never a guess.
STATUS_CLASSES = {
    "Pass": "st-pass",
    "Warn": "st-warn",
    "Fail": "st-fail",
    "Info": "st-info",
    "Skipped": "st-skipped",
}

# Printed in this order in the summary bar, worst first, so a tally led by Pass
# cannot bury the finding under the count of everything that was fine.
STATUS_ORDER = ("Fail", "Warn", "Pass", "Info", "Skipped")

# What each status means, repeated on the page so the reader is not guessing.
STATUS_MEANING = {
    "Pass": "Measured, and it is what it should be.",
    "Warn": "Measured, and it is a contributing cause.",
    "Fail": "Measured, and it is a cause.",
    "Info": "Read, and it decides nothing.",
    "Skipped": "Not read at all. The probe threw, produced nothing, or was "
               "never asked to run.",
}

EXIT_MEANING = {
    0: "Nothing to act on.",
    1: "Performance findings, none of them bearing on lost edits.",
    2: "At least one finding bearing on lost edits.",
    3: "No finding, and nothing was determined either.",
    64: "A usage error, or the report could not be written.",
}


def esc(value):
    """Escape one value for an HTML text node or a quoted attribute."""
    return _esc("" if value is None else "%s" % value, quote=True)


def _multiline(text, css="observed"):
    """One paragraph per non-empty line, each escaped."""
    out = []
    for line in ("%s" % (text or "")).split("\n"):
        if line.strip():
            out.append('<div class="%s">%s</div>' % (css, esc(line)))
    return "".join(out)


def _embedded_json(document):
    """The report as JSON, safe inside a <script> element.

    Content inside a script element is raw text to the HTML parser: nothing in
    it is markup until the closing tag. So two things have to be true. The
    closing sequence must not appear, and the whole block must stay valid
    JSON. Escaping the three characters that matter as \\uXXXX gives both, and
    keeps the raw machine strings - a folder name off a file server, an
    adapter description - out of the page as literal markup entirely.
    """
    blob = json.dumps(document, indent=1, sort_keys=True, ensure_ascii=True)
    return (blob.replace("&", "\\u0026").replace("<", "\\u003c")
                .replace(">", "\\u003e").replace(u"\u2028", "\\u2028")
                .replace(u"\u2029", "\\u2029"))


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#16191d;--mut:#5b6672;--line:#dfe3e8;
--pass:#1a7f37;--warn:#9a6700;--fail:#b42318;--info:#0b5cad;--skip:#5b6672}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 "Segoe UI",system-ui,-apple-system,Arial,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:24px 20px 80px}
header h1{font-size:22px;margin:0 0 4px}
header .sub{color:var(--mut);font-size:13px}
header .sub b{color:var(--ink);font-weight:600}
.banner{margin:18px 0;padding:14px 16px;border-radius:8px;border:1px solid;
background:#fff}
.banner.act{border-color:var(--fail);background:#fff5f4}
.banner.calm{border-color:var(--pass);background:#f2fbf5}
.banner.undone{border-color:var(--info);background:#f3f8ff}
.banner h2{font-size:15px;margin:0 0 8px}
.banner ul{margin:0;padding-left:20px}
.bar{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 6px}
.pill{padding:5px 11px;border-radius:999px;font-size:12px;font-weight:600;
border:1px solid var(--line);background:#fff;color:var(--mut)}
.pill.fail{color:var(--fail);border-color:#f3c1bd}
.pill.warn{color:var(--warn);border-color:#eed9a4}
.pill.pass{color:var(--pass);border-color:#bfe3c8}
.pill.info{color:var(--info);border-color:#b9d5f2}
.pill.skip{color:var(--skip)}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0 18px}
.controls input{flex:1 1 220px;padding:8px 10px;border:1px solid var(--line);
border-radius:6px;font:inherit;background:#fff}
.controls button{padding:8px 12px;border:1px solid var(--line);border-radius:6px;
background:#fff;font:inherit;cursor:pointer}
.controls button[aria-pressed=true]{background:#16191d;color:#fff;border-color:#16191d}
section h2{font-size:13px;letter-spacing:.09em;text-transform:uppercase;
color:var(--mut);margin:26px 0 10px;border-bottom:1px solid var(--line);
padding-bottom:6px}
.check{background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:13px 15px;margin:10px 0}
.check.is-fail{border-left:4px solid var(--fail)}
.check.is-warn{border-left:4px solid var(--warn)}
.check.is-pass{border-left:4px solid var(--pass)}
.check.is-info{border-left:4px solid var(--info)}
.check.is-skipped{border-left:4px solid var(--skip)}
.chead{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline}
.chead .id{font:600 13px ui-monospace,Consolas,monospace;color:var(--mut)}
.chead .ttl{font-weight:600}
.chead .cat{font-size:11px;color:var(--mut);border:1px solid var(--line);
border-radius:4px;padding:1px 6px;margin-left:auto}
.badge{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
border-radius:4px;padding:2px 7px}
.st-pass{background:#e6f4ea;color:var(--pass)}
.st-warn{background:#fdf3dc;color:var(--warn)}
.st-fail{background:#fde7e5;color:var(--fail)}
.st-info{background:#e7f0fb;color:var(--info)}
.st-skipped{background:#eceff2;color:var(--skip)}
.observed{white-space:pre-wrap;word-break:break-word;font:13px/1.55 ui-monospace,
Consolas,"Courier New",monospace;margin-top:8px}
.kv{margin-top:8px;font-size:13px}
.kv .k{display:inline-block;min-width:64px;color:var(--mut);
text-transform:uppercase;font-size:11px;letter-spacing:.06em;vertical-align:top}
.kv .v{display:inline}
details{margin-top:8px}
details summary{cursor:pointer;font-size:12px;color:var(--mut)}
details .observed{font-size:12px}
.fixes li,.notes li{margin:4px 0}
code{background:#eceff2;border-radius:4px;padding:1px 5px;
font:12px ui-monospace,Consolas,monospace}
pre.undo{background:#16191d;color:#f3f5f7;padding:10px 12px;border-radius:6px;
overflow-x:auto;font:12px ui-monospace,Consolas,monospace}
.key{margin:14px 0;padding:12px 15px;background:#fff;border:1px solid var(--line);
border-radius:8px;font-size:13px}
.key dl{display:grid;grid-template-columns:76px 1fr;gap:4px 12px;margin:8px 0 0}
.key dt{font-weight:700}
.key dd{margin:0;color:var(--mut)}
footer{margin-top:28px;color:var(--mut);font-size:12px;border-top:1px solid
var(--line);padding-top:12px}
footer a{color:var(--info)}
[hidden]{display:none!important}
@media print{body{background:#fff}.controls{display:none}
.check{break-inside:avoid;border:1px solid #ccc}details{display:none}}
@media (prefers-color-scheme:dark){
:root{--bg:#101317;--card:#171b21;--ink:#e8eaed;--mut:#9aa4b0;--line:#2a313a;
--pass:#4ac26b;--warn:#e3b341;--fail:#f2726a;--info:#6fa8dc}
.controls input,.controls button,.pill{background:#171b21;color:var(--ink)}
.controls button[aria-pressed=true]{background:#e8eaed;color:#101317}
.st-pass{background:#12321c;color:var(--pass)}
.st-warn{background:#3a2e10;color:var(--warn)}
.st-fail{background:#3d1512;color:var(--fail)}
.st-info{background:#12283d;color:var(--info)}
.st-skipped{background:#232931;color:var(--skip)}
.banner.act{background:#25100e;border-color:var(--fail)}
.banner.calm{background:#0f2417;border-color:var(--pass)}
.banner.undone{background:#0e1c2c;border-color:var(--info)}
code,.key .k{background:#232931}}
"""

JS = """
(function(){
  var cards = Array.prototype.slice.call(document.querySelectorAll('.check'));
  var search = document.getElementById('q');
  var mode = 'all';
  function apply(){
    var needle = (search.value || '').toLowerCase();
    var shown = 0;
    cards.forEach(function(c){
      var okMode = mode === 'all' ||
        (mode === 'findings' ? c.dataset.finding === '1' :
         mode === 'dataloss' ? c.dataset.dataloss === '1' :
         mode === 'performance' ? c.dataset.dataloss !== '1' :
         c.dataset.status === mode);
      var okText = !needle || c.textContent.toLowerCase().indexOf(needle) !== -1;
      var ok = okMode && okText;
      c.hidden = !ok;
      if (ok) { shown++; }
    });
    document.getElementById('shown').textContent = shown;
    ['DATA LOSS','PERFORMANCE'].forEach(function(h){
      var s = document.querySelector('section[data-block="'+h+'"]');
      if (!s) { return; }
      var any = s.querySelectorAll('.check:not([hidden])').length > 0;
      s.hidden = !any;
    });
  }
  Array.prototype.forEach.call(document.querySelectorAll('[data-mode]'),
    function(b){
      b.addEventListener('click', function(){
        mode = b.getAttribute('data-mode');
        document.querySelectorAll('[data-mode]').forEach(function(o){
          o.setAttribute('aria-pressed', o === b ? 'true' : 'false');
        });
        apply();
      });
    });
  search.addEventListener('input', apply);
  apply();
})();
"""


def _counts(document):
    """[(status, n)] for the five statuses, worst first, from the records."""
    checks = document.get("checks") or []
    given = document.get("counts") or {}
    out = []
    for status in STATUS_ORDER:
        if status in given:
            out.append((status, given[status]))
        else:
            out.append((status, len([c for c in checks
                                     if c.get("status") == status])))
    return out


def _banner(document):
    """The one box at the top. Act-first, or why there is nothing to act on."""
    checks = document.get("checks") or []
    by_id = dict((c.get("id"), c) for c in checks)
    act = document.get("act_first") or []
    if act:
        items = "".join(
            "<li><b>%s</b> &mdash; %s</li>"
            % (esc(cid), esc((by_id.get(cid) or {}).get("title", "")))
            for cid in act)
        return ('<div class="banner act"><h2>Act on these first &mdash; they '
                'bear on the vanished edits</h2><ul>%s</ul></div>' % items)
    verdicts = [c for c in checks if c.get("status") in ("Fail", "Warn")]
    if verdicts:
        return ('<div class="banner undone"><h2>Performance findings only'
                '</h2><p>%d finding(s), none of them bearing on lost edits.'
                '</p></div>' % len(verdicts))
    determined = [c for c in checks if c.get("status") == "Pass"
                  and c.get("id") not in ("DL-00", "DL-12")]
    if not determined:
        return ('<div class="banner undone"><h2>Nothing was determined'
                '</h2><p>No finding, and nothing was measured either. Run it '
                'in the editor&rsquo;s own session on Windows. This is exit '
                'code 3, not a clean machine.</p></div>')
    return ('<div class="banner calm"><h2>Nothing to act on</h2>'
            '<p>Every check that could be read came back clean.</p></div>')


def _check_card(check):
    status = check.get("status", "")
    cls = STATUS_CLASSES.get(status, "st-skipped")
    parts = ['<article class="check is-%s" data-status="%s" data-finding="%s" '
             'data-dataloss="%s">'
             % (cls.replace("st-", ""), esc(status),
                "1" if status in ("Fail", "Warn") else "0",
                "1" if check.get("dataloss") else "0")]
    parts.append('<div class="chead"><span class="id">%s</span>'
                 '<span class="badge %s">%s</span>'
                 '<span class="ttl">%s</span>'
                 '<span class="cat">%s</span></div>'
                 % (esc(check.get("id")), cls, esc(status),
                    esc(check.get("title")), esc(check.get("category"))))
    parts.append(_multiline(check.get("observed")))
    for key, field in (("impact", "impact"), ("fix", "fix")):
        value = check.get(field)
        if value and status in ("Warn", "Fail"):
            parts.append('<div class="kv"><span class="k">%s</span>'
                         '<span class="v">%s</span></div>'
                         % (key, esc(value)))
    extras = []
    if check.get("expected"):
        extras.append('<div class="kv"><span class="k">expected</span>'
                      '<span class="v">%s</span></div>'
                      % esc(check.get("expected")))
    for key, field in (("impact", "impact"), ("fix", "fix")):
        value = check.get(field)
        if value and status not in ("Warn", "Fail"):
            extras.append('<div class="kv"><span class="k">%s</span>'
                          '<span class="v">%s</span></div>'
                          % (key, esc(value)))
    if check.get("detail"):
        extras.append('<div class="kv"><span class="k">evidence</span></div>'
                      + _multiline(check.get("detail")))
    if check.get("autofixable"):
        extras.append('<div class="kv"><span class="k">fixable</span>'
                      '<span class="v">yes &mdash; re-run with the fixes '
                      'enabled</span></div>')
    if extras:
        parts.append('<details><summary>expected, evidence and the manual '
                     'fix</summary>%s</details>' % "".join(extras))
    parts.append("</article>")
    return "".join(parts)


def _section(document, heading, wanted):
    checks = [c for c in (document.get("checks") or [])
              if bool(c.get("dataloss")) is wanted]
    if not checks:
        return ""
    return ('<section data-block="%s"><h2>%s</h2>%s</section>'
            % (esc(heading), esc(heading),
               "".join(_check_card(c) for c in checks)))


def _fixes(document):
    parts = []
    notes = document.get("notes") or []
    if notes:
        parts.append("<section><h2>Fix gates</h2><ul class='notes'>")
        for note in notes:
            parts.append("<li><code>%s</code></li>" % esc(note))
        parts.append("</ul></section>")
    applied = document.get("applied") or []
    if applied:
        parts.append("<section><h2>Applied on this run</h2>")
        for record in applied:
            parts.append(
                '<div class="check is-warn"><div class="chead">'
                '<span class="id">%s</span><span class="badge st-warn">'
                'applied</span><span class="ttl">%s</span></div>'
                '<div class="kv"><span class="k">result</span><span class="v">'
                '<code>%s</code></span></div>'
                '<div class="kv"><span class="k">undo</span></div>'
                '<pre class="undo">%s</pre></div>'
                % (esc(record.get("id")), esc(record.get("what")),
                   esc(record.get("result")), esc(record.get("undo"))))
        parts.append("</section>")
    return "".join(parts)


def _key():
    rows = "".join(
        "<dt>%s</dt><dd>%s</dd>" % (esc(s), esc(STATUS_MEANING[s]))
        for s in STATUS_ORDER)
    return ('<div class="key"><b>What each status means.</b> Only Pass, Warn '
            'and Fail are verdicts. Info and Skipped are not: a check that '
            'says it did not measure cannot carry one.<dl>%s</dl></div>' % rows)


def _symptoms(document):
    rows = document.get("symptoms") or []
    if not rows:
        return ""
    items = "".join("<li><b>%s</b> &mdash; %s</li>" % (esc(c), esc(t))
                    for c, t in rows)
    return ('<div class="key"><b>Symptom key used in the impact lines.</b>'
            '<ul style="margin:8px 0 0;padding-left:20px">%s</ul></div>'
            % items)


def render_html(document, verbose=False, exit_code=None, meta=None):
    """The whole report as one HTML string.

    verbose widens the cards to show the expected text and the evidence lines
    without opening each one. meta is an optional dict of extra header lines
    the caller knows and the document does not, such as the ArcGIS Pro release
    the toolbox ran under.
    """
    checks = document.get("checks") or []
    tally = " ".join('<span class="pill %s">%s %d</span>'
                     % (s.lower(), s.upper(), n)
                     for s, n in _counts(document))
    code = exit_code
    if code is None:
        code = document.get("exit_code")
    head = ['<div class="wrap"><header>',
            "<h1>ArcGIS Pro workstation diagnostic</h1>",
            '<div class="sub">prostall report format %s &middot; taken '
            '<b>%s UTC</b> &middot; user <b>%s</b> &middot; elevated '
            '<b>%s</b></div>'
            % (esc(document.get("prostall")), esc(document.get("taken")),
               esc(document.get("user")), esc(document.get("elevated")))]
    if code is not None:
        head.append('<div class="sub">exit code <b>%s</b> &mdash; %s</div>'
                    % (esc(code), esc(EXIT_MEANING.get(code, "unknown"))))
    for name, value in sorted((meta or {}).items()):
        head.append('<div class="sub">%s <b>%s</b></div>'
                    % (esc(name), esc(value)))
    head.append("</header>")

    controls = ['<div class="controls">',
                '<input id="q" type="search" placeholder="Filter by id, title '
                'or text&hellip;" aria-label="Filter">',
                '<button data-mode="all" aria-pressed="true">All</button>',
                '<button data-mode="findings" aria-pressed="false">'
                'Findings only</button>',
                '<button data-mode="dataloss" aria-pressed="false">'
                'Data loss</button>',
                '<button data-mode="performance" aria-pressed="false">'
                'Performance</button>']
    for status in STATUS_ORDER:
        controls.append('<button data-mode="%s" aria-pressed="false">%s'
                        '</button>' % (esc(status), esc(status)))
    controls.append('<span class="pill">shown <b id="shown">%d</b></span>'
                    % len(checks))
    controls.append("</div>")

    body = ["".join(head), '<div class="bar">%s</div>' % tally, _banner(document),
            "".join(controls), _symptoms(document),
            _section(document, "DATA LOSS", True),
            _section(document, "PERFORMANCE", False),
            _fixes(document), _key()]

    body.append(
        "<section><h2>The same report as JSON</h2>"
        "<p style='font-size:13px;color:var(--mut)'>Diff this against a "
        "workstation that is known to be fast. Every timestamp is UTC, so two "
        "machines in different time zones do not disagree on a dated line. "
        "The report carries the account name, local paths, connection file "
        "names and exclusion paths &mdash; read it before you send it to "
        "anyone.</p>"
        '<details><summary>show the JSON document</summary>'
        '<pre class="undo">%s</pre></details></section>'
        % esc(json.dumps(document, indent=1, sort_keys=True)))

    body.append(
        '<footer>Generated by prostall. Read-only unless the fixes were '
        'explicitly enabled. The network probes ran only against the hosts '
        'named on the command line. Nothing here deletes anything.</footer>')
    body.append("</div>")

    return ("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
            "<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, "
            "initial-scale=1\">\n"
            "<meta name=\"referrer\" content=\"no-referrer\">\n"
            "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src "
            "'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
            "img-src data:\">\n"
            "<title>ArcGIS Pro diagnostic &mdash; %s</title>\n"
            "<style>%s</style>\n</head>\n<body>\n%s\n"
            "<script type=\"application/json\" id=\"prostall-report\">%s"
            "</script>\n<script>%s</script>\n</body>\n</html>\n"
            % (esc(document.get("taken")), CSS, "".join(body),
               _embedded_json(document), JS))


def write_html(document, path, verbose=False, exit_code=None, meta=None):
    """Render and write the report. Returns the path that was written."""
    folder = os.path.dirname(os.path.abspath(path))
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    handle = open(path, "wb")
    try:
        handle.write(render_html(document, verbose, exit_code, meta)
                     .encode("utf-8"))
    finally:
        handle.close()
    return path
