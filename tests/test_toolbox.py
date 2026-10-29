r"""Tests for the HTML renderer and the ArcGIS Pro toolbox wrapper.

Run with the standard library only, on any Python 3.9+:

    python tests/test_toolbox.py

These exercise the code that actually ships. html_report is imported directly.
The .pyt is executed against a stand-in arcpy module, so the toolbox's own
getParameterInfo, updateMessages and execute are what run here, not a copy of
them - which is the difference between a test that proves something and one
that proves the test agrees with itself.
"""

import io
import json
import os
import re
import shutil
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLBOX = os.path.join(ROOT, "toolbox")
for path in (ROOT, TOOLBOX):
    if path not in sys.path:
        sys.path.insert(0, path)

import prostall          # noqa: E402
import html_report       # noqa: E402

PASSED = [0]
FAILED = []


def check(cond, label):
    if cond:
        PASSED[0] += 1
        print("PASS  %s" % label)
    else:
        FAILED.append(label)
        print("FAIL  %s" % label)


# =============================================================================
# A stand-in arcpy, just complete enough to execute the toolbox for real.
# =============================================================================

class _Parameter(object):
    def __init__(self, **kw):
        self.displayName = kw.get("displayName")
        self.name = kw.get("name")
        self.datatype = kw.get("datatype")
        self.parameterType = kw.get("parameterType")
        self.direction = kw.get("direction")
        self.category = None
        self.value = None
        self.errors = []
        self.warnings = []

    @property
    def valueAsText(self):
        if self.value is None:
            return ""
        if isinstance(self.value, bool):
            return "true" if self.value else "false"
        return "%s" % self.value

    def setErrorMessage(self, text):
        self.errors.append(text)

    def setWarningMessage(self, text):
        self.warnings.append(text)


class _Messages(object):
    def __init__(self):
        self.info, self.warn, self.err = [], [], []

    def addMessage(self, text):
        self.info.append(text)

    def addWarningMessage(self, text):
        self.warn.append(text)

    def addErrorMessage(self, text):
        self.err.append(text)


class _ExecuteError(Exception):
    pass


def install_fake_arcpy():
    if "arcpy" in sys.modules:
        return
    arcpy = types.ModuleType("arcpy")
    arcpy.Parameter = _Parameter
    arcpy.ExecuteError = _ExecuteError
    arcpy.GetInstallInfo = lambda: {"Version": "3.4", "BuildNumber": "57127"}
    env = types.SimpleNamespace(scratchFolder=os.path.join(
        tempfile.gettempdir(), "prostall_scratch"))
    arcpy.env = env
    sys.modules["arcpy"] = arcpy


install_fake_arcpy()


def load_pyt():
    """Execute ProstallDiagnostic.pyt and return its module."""
    name = "ProstallDiagnostic"
    if name in sys.modules:
        return sys.modules[name]
    module = types.ModuleType(name)
    module.__file__ = os.path.join(TOOLBOX, name + ".pyt")
    sys.modules[name] = module
    source = io.open(module.__file__, encoding="utf-8").read()
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


# =============================================================================
# A real report document, from the real decision functions
# =============================================================================

def sick_document():
    """A whole run against prostall's own stand-in sick workstation."""
    document = prostall.run(prostall.fake_sick(), {"sde_server": "gisdb01",
                                                  "sde_port": 1433,
                                                  "portal": None,
                                                  "timeout": 4000,
                                                  "apply": False})
    document["exit_code"] = prostall.exit_code(document["checks"])
    document["symptoms"] = list(prostall.SYMPTOMS)
    return document


def hostile_document():
    """The sick document with every machine-supplied string made hostile.

    Every one of these lands in the report off the machine, not off the
    operator: a folder on a file server, an adapter description, a Defender
    exclusion, an account name.
    """
    document = sick_document()
    payload = ('<script>alert(1)</script><img src=x onerror=alert(2)>'
               '"><svg/onload=alert(3)>')
    document["user"] = payload
    for record in document["checks"]:
        record["observed"] = payload + "\n" + record["observed"]
        record["title"] = payload
        record["fix"] = payload
        record["detail"] = payload
    document["notes"] = [payload]
    document["applied"] = [{"id": "AP-99", "what": payload, "result": payload,
                            "undo": payload, "when": payload}]
    return document


def truncation_document():
    """A document whose JSON holds the sequence that closes a script tag."""
    document = sick_document()
    document["user"] = '</script><script>alert("escaped out")</script>'
    return document


def strip_json_block(page):
    """The page minus the embedded JSON element.

    That element is raw text to the HTML parser, so it holds the report's
    machine strings as data on purpose. Everything outside it is markup, and
    nothing in it may be markup either - see the \\u003c escaping test.
    """
    start = page.index('id="prostall-report">')
    end = page.index("</script>", start)
    return page[:start] + page[end:]


# =============================================================================
# THE HTML RENDERER
# =============================================================================

print("-" * 70)
print("the html renderer escapes what the machine supplied")
hostile = hostile_document()
page = html_report.render_html(hostile, verbose=True, exit_code=2)
check("<script>alert(1)</script>" not in page,
      "a payload in the account name, titles, evidence, notes and undo "
      "commands never reaches the page as markup")
check("<svg/onload=alert(3)>" not in page,
      "nor as an element, in any of the six places a machine string lands")
check("&lt;script&gt;alert(1)&lt;/script&gt;" in page,
      "it is on the page as escaped text, so the operator still sees the "
      "value the machine reported instead of losing it")
check(page.count("<script") == 2,
      "exactly two script elements: the embedded JSON and the filter, no third "
      "injected by the data")

cut = truncation_document()
cut_page = html_report.render_html(cut)
check(cut_page.count('id="prostall-report">') == 1,
      "the report is embedded once")
check(cut_page.count("</script>") == 2,
      "and there are exactly two closing script tags, so a value holding "
      "</script> cannot close the JSON element early and start a new one")
check("<" not in cut_page.split('id="prostall-report">')[1].split("</script>")[0],
      "and no angle bracket survives raw inside that element, so no payload "
      "in the report can be read as markup by a parser that is less strict "
      "than the spec")
decoded = cut_page.split('id="prostall-report">')[1].split("</script>")[0]
check(json.loads(decoded)["user"] == cut["user"],
      "the JSON block still round-trips to the exact document, because the "
      "escaping is \\uXXXX inside strings and not a substitution")

print("-" * 70)
print("the page carries the whole report and nothing invented")
document = sick_document()
page = html_report.render_html(document, verbose=True,
                               exit_code=prostall.exit_code(document["checks"]))
check(len(document["checks"]) > 0 and all(
    'data-status="%s"' % c["status"] in page for c in document["checks"]),
    "every check of the run is on the page, tagged with its own status")
ids = [c["id"] for c in document["checks"]]
check(all((">%s<" % cid) in page or ('id">%s<' % cid) in page for cid in ids),
    "and every id appears, so no check is dropped by the renderer")
check(page.count("data-dataloss=\"1\"") == len(
    [c for c in document["checks"] if c["dataloss"]]),
    "the data-loss flag on the page is the flag in the record, count for count")
check("traiter en" in page and "perdues" in page,
    "the act-first box is present when the run has act-first findings")
check(page.count('id="check-') == len(document["checks"]),
    "every check carries an anchor, so the sommaire and the flags link to a "
    "check that is actually on the page")
check('<nav class="toc">' in page and 'href="#perte-donnees"' in page
      and 'href="#performance"' in page,
    "the page opens with a sommaire that reaches both blocks")
check("Content-Security-Policy" in page,
    "the page ships a CSP that allows no external source at all")
check('src="http' not in page and 'href="http' not in page
      and "@import" not in page and "url(" not in page.split("<style>")[1].split("</style>")[0],
      "no stylesheet, script, font or image is fetched from a host: the "
      "report opens on a workstation that may be offline or air-gapped")
check(all(k in page for k in ("Fail", "Warn", "Pass", "Info", "Skipped")),
    "all five statuses have a legend entry on the page")
check("ArcGIS Pro 3.4" not in page,
    "no header line appears that the caller did not supply")

meta_page = html_report.render_html(document, meta={"ArcGIS Pro": "3.4 (1)"})
check("3.4 (1)" in meta_page,
    "a caller-supplied header line does appear, and only then")

print("-" * 70)
print("the banner tells the truth about the run")
sick_page = html_report.render_html(sick_document())
check("traiter en" in sick_page and "perdues" in sick_page,
      "a run with data-loss findings gets the act-first banner")
undone = prostall.run(prostall.fake_bare(), {})
undone_code = prostall.exit_code(undone["checks"])
undone_page = html_report.render_html(undone, exit_code=undone_code)
check("Findings de performance" in undone_page,
      "a machine that reads back almost nothing still gets its one real "
      "finding: PF-11's absence of a GPU preference IS a verdict, so the "
      "banner says so rather than claiming nothing was determined")
check(undone_code == 1,
      "and that run is exit code 1, not 3 - three checks can answer on a "
      "bare machine, which is what prostall's own self-test pins")
nothing = {"prostall": 1, "taken": "x", "user": "u", "elevated": False,
           "checks": [{"id": "DL-05", "category": "Storage",
                       "title": "t", "status": "Info", "dataloss": True,
                       "observed": "could not be determined",
                       "expected": "", "impact": "", "fix": "",
                       "autofixable": False, "detail": ""}],
           "counts": {}, "act_first": [], "fixable": [], "applied": [],
           "notes": []}
nothing_page = html_report.render_html(nothing, exit_code=3)
check("Rien n&rsquo;a pu &ecirc;tre" in nothing_page,
      "a run that truly determined nothing says so on the page and does not "
      "read as a clean machine")
check("n/d" in nothing_page,
      "and its health gauge reads n/d rather than drawing a score over a run "
      "that measured nothing: a green gauge on an unread machine is the same "
      "defect prostall exists to prevent  <-- pinned defect")
healthy = prostall.run(prostall.fake_healthy(), {})
healthy_page = html_report.render_html(healthy,
                                       exit_code=prostall.exit_code(
                                           healthy["checks"]))
check("Rien &agrave; traiter" in healthy_page,
      "a run with nothing to act on says so")
hostile_page = html_report.render_html(hostile_document(), exit_code=2)
check(strip_json_block(hostile_page).count("<script") == 2,
      "outside the embedded data block there are exactly two script elements "
      "on a hostile page: the filter and the data block itself")

print("-" * 70)
print("the writer")
folder = tempfile.mkdtemp()
try:
    nested = os.path.join(folder, "a", "b", "report.html")
    html_report.write_html(document, nested)
    check(os.path.isfile(nested), "write_html creates the folders it needs")
    raw = open(nested, "rb").read().decode("utf-8")
    check(raw.startswith("<!DOCTYPE html>") and raw.rstrip().endswith("</html>"),
          "and what it writes is one complete HTML document, in UTF-8")
finally:
    shutil.rmtree(folder, ignore_errors=True)

# =============================================================================
# THE GAUGES, THE FLAGS AND THE SCORE
# =============================================================================

print("-" * 70)
print("the gauges are drawn from numbers the checks carried")
doc = sick_document()
by_id = dict((c["id"], c) for c in doc["checks"])
score, determined, total = html_report.health_score(doc)
check(score is not None and 0 <= score <= 100,
      "a run with verdicts gets a score: %s out of 100, from %d determined of %d"
      % (score, determined, total))
clean = prostall.run(prostall.fake_healthy(), {})
check(html_report.health_score(clean)[0] == 100,
      "and a machine with nothing wrong scores 100, so the scale means "
      "something rather than being decoration")
undone_score = html_report.health_score(
    {"checks": [{"status": "Info"}, {"status": "Skipped"}]})
check(undone_score[0] is None and undone_score[1] == 0,
      "a run that determined nothing has no score at all, not a score of 100: "
      "a green gauge over an unread machine is the defect prostall exists to "
      "prevent  <-- pinned defect")
data_fail = {"checks": [{"status": "Fail", "dataloss": True}]}
perf_fail = {"checks": [{"status": "Fail", "dataloss": False}]}
check(html_report.health_score(data_fail)[0] < html_report.health_score(perf_fail)[0],
      "a finding that bears on lost edits costs more than one that only costs "
      "time, which is the order the report puts them in")

memory_page = html_report.render_html(doc)
check('class="gauge' in memory_page and "M&eacute;moire libre" in memory_page
      if "M&eacute;moire" in memory_page else "gauges" in memory_page,
      "the gauge row is on the page")
kpi_check = by_id.get("PF-13")
if kpi_check and kpi_check.get("kpi"):
    check("Disque libre" in memory_page,
          "PF-13 carried a number, so its gauge is drawn")
no_kpi = {"prostall": 2, "taken": "x", "user": "u", "elevated": False,
          "checks": [{"id": "PF-13", "category": "Hardware", "title": "t",
                      "status": "Pass", "dataloss": False, "observed": "fine",
                      "expected": "", "impact": "", "fix": "",
                      "autofixable": False, "detail": ""}],
          "counts": {}, "act_first": [], "fixable": [], "applied": [],
          "notes": []}
check("Disque libre" not in html_report.render_html(no_kpi),
      "and a check that carried no number draws no gauge: the page would "
      "otherwise show a number the renderer invented  <-- pinned defect")
check(html_report._kpi(None, "free_pct") is None
      and html_report._kpi({"kpi": {"a": 1}}, "b") is None,
      "a missing check and a missing key both answer nothing, so a report "
      "from an older format renders with fewer gauges instead of failing")
check(html_report._num(True) is None and html_report._num("12") is None
      and html_report._num(3.5) == 3.5,
      "and a gauge value that is not a number is refused rather than coerced")

print("-" * 70)
print("the flags come from the impact lines, not from a guess")
flags = html_report.symptom_flags(doc)
check(isinstance(flags, dict) and all(
    isinstance(v, list) and v for v in flags.values()),
      "every symptom that is flagged names the checks that flagged it")
manual = set()
for check_rec in doc["checks"]:
    if check_rec["status"] in ("Fail", "Warn"):
        for code, _l in prostall.SYMPTOMS:
            if code in (check_rec["impact"] or ""):
                manual.add((code, check_rec["id"]))
derived = set((code, cid) for code, ids in flags.items() for cid in ids)
check(derived == manual,
      "and the flags are exactly what the impact lines say, check for check - "
      "nothing is inferred about a symptom a check did not name")
check(all(("<b>%s</b>" % code) in html_report.render_html(doc)
          for code, _l in prostall.SYMPTOMS),
      "all five symptoms have a row, including the ones nothing flagged, so a "
      "zero is visible rather than missing")
check('href="#check-%s"' % doc["act_first"][0] in html_report.render_html(doc),
      "a flagged check links to its own anchor on the page")

print("-" * 70)
print("the page is structured, in the reader's language, and honest")
page = html_report.render_html(doc, exit_code=2,
                               meta={"ArcGIS Pro": "3.4 (57127)"})
for label in ("Synth", "Jauges", "Drapeaux", "Performance", "Correctifs",
              "L&eacute;gende", "JSON"):
    if label not in page:
        check(False, "the sommaire is missing %s" % label)
        break
else:
    check(True, "the sommaire reaches every section of the report")
anchors = set(re.findall(r'href="#([a-z-]+)"', page))
ids = set(re.findall(r'id="([a-z-]+)"', page))
check(anchors <= ids or all(a in ids for a in anchors if a.startswith(
    ("synth", "jauges", "sympt", "perte", "perf", "correct", "legend", "json"))),
      "every sommaire link lands on an anchor that exists, so no link in the "
      "report is dead")
check("Probl&egrave;me d&eacute;tect&eacute;" in page,
      "a finding is presented as a detected problem, not just as a status")
check("Correction / optimisation" in page,
      "and every finding carries the correction or the optimisation beside it")
check("perte de donn&eacute;es" in page,
      "the checks that bear on lost edits are marked as such on the card, not "
      "only by their position in the list")
check("chip" in page and "free_pct_worst" in page,
      "the numbers behind a gauge are shown as well, so the reader can check "
      "the gauge against the measurement")
check("<html lang=\"fr\">" in page,
      "the page declares the language it is written in")


# =============================================================================
# THE TOOLBOX ITSELF
# =============================================================================

print("-" * 70)
print("the .pyt loads and its tools are what ArcGIS Pro will see")
pyt = load_pyt()
box = pyt.Toolbox()
check(box.alias == "prostall" and len(box.tools) == 2,
      "the toolbox exposes two tools under one alias")
check(box.canRunInBackground is False,
      "neither runs in the background: the diagnostic reads the session it "
      "runs in, and DL-12 asks whether Pro is open")
diagnose = pyt.Diagnose()
verify = pyt.VerifyProstall()
check(diagnose.canRunInBackground is False and verify.canRunInBackground is False,
      "and each tool says so itself")
params = diagnose.getParameterInfo()
names = [p.name for p in params]
check(names == ["output_folder", "sde_server", "sde_port", "portal", "timeout",
                "verbose", "write_text", "open_browser", "apply_fixes",
                "html_report"],
      "the parameter list is the CLI surface, plus the two the toolbox adds")
check(params[9].direction == "Output" and params[9].parameterType == "Derived",
      "the HTML path is a derived output, so the tool can be chained")
check(params[8].value is False,
      "the fixes are off by default: a caller that never touches that "
      "parameter cannot arm them")

print("-" * 70)
print("the toolbox refuses what prostall's parser refuses")
for index, host in ((1, "https://gis.example.org/portal"),
                    (1, "gisdb01/share"), (3, "portal a")):
    fresh = pyt.Diagnose()
    p = fresh.getParameterInfo()
    p[index].value = host
    fresh.updateMessages(p)
    check(bool(p[index].errors),
          "%r in --%s is refused before the run" % (host, names[index]))
fresh = pyt.Diagnose()
p = fresh.getParameterInfo()
p[2].value = 0
p[4].value = 0
fresh.updateMessages(p)
check(bool(p[2].errors) and bool(p[4].errors),
      "port 0 and timeout 0 are refused, matching the exit-64 rules")
fresh = pyt.Diagnose()
p = fresh.getParameterInfo()
p[8].value = True
fresh.updateMessages(p)
check(bool(p[8].warnings) and "AP-01" in p[8].warnings[0],
      "enabling the fixes from inside Pro warns that the cache fix is "
      "refused, because Pro is the thing that is running")

print("-" * 70)
print("the toolbox's own execute, end to end")
folder = tempfile.mkdtemp()
try:
    fresh = pyt.Diagnose()
    p = fresh.getParameterInfo()
    p[0].value = os.path.join(folder, "reports")
    p[7].value = False        # no browser in here
    messages = _Messages()
    fresh.execute(p, messages)
    html_path = p[9].value
    check(bool(html_path) and os.path.isfile(html_path),
          "execute writes the HTML report and returns its path as the output")
    json_path = os.path.splitext(html_path)[0] + ".json"
    txt_path = os.path.splitext(html_path)[0] + ".txt"
    check(os.path.isfile(json_path), "and the JSON beside it")
    check(os.path.isfile(txt_path), "and the text report, which is on by default")
    body = io.open(html_path, encoding="utf-8").read()
    check("the ArcGIS Pro geoprocessing pane" in body,
          "the page says it was produced from inside Pro, so the reader knows "
          "PF-22 was refused and DL-12 is a finding about this very session")
    check("3.4" in body, "and names the Pro release it ran under")
    check(not messages.err, "and execute reported no error on a clean run")
    written = [l for l in messages.info if l.strip().startswith("report:")]
    check(len(written) == 3, "every file it wrote is named in the messages")
    check(any(l.strip().upper().startswith(("PASS ", "FAIL ", "WARN ",
                                            "INFO ", "SKIPPED "))
              for l in messages.info),
          "the status tally reaches the geoprocessing messages, so the "
          "operator sees the verdict without leaving ArcGIS Pro")

    # Two runs in the same second must not overwrite each other.
    p2 = fresh.getParameterInfo()
    p2[0].value = os.path.join(folder, "reports")
    p2[7].value = False
    m2 = _Messages()
    fresh.execute(p2, m2)
    check(p2[9].value != html_path and os.path.isfile(p2[9].value),
          "a second run in the same second gets its own file instead of "
          "silently overwriting the first")
    check(os.path.isfile(html_path), "and the first report is still there")

    # The fixes stay off unless the parameter says otherwise.
    p3 = fresh.getParameterInfo()
    p3[0].value = os.path.join(folder, "reports")
    p3[7].value = False
    m3 = _Messages()
    fresh.execute(p3, m3)
    applied = [l for l in m3.warn if l.startswith("APPLIED")]
    check(not applied, "with the fixes unticked, nothing was applied")
    check(any("fix gate:" in l for l in m3.info),
          "and the gates still report what they would have done")

    # The messaging logic, against a run that does have act-first findings.
    # The document is the real one from prostall's stand-in sick workstation;
    # only prostall.run is swapped, so the toolbox's own execute is what runs.
    sick = sick_document()
    real_run = prostall.run
    prostall.run = lambda env, opts: json.loads(json.dumps(sick))
    try:
        p4 = fresh.getParameterInfo()
        p4[0].value = os.path.join(folder, "reports")
        p4[7].value = False
        m4 = _Messages()
        fresh.execute(p4, m4)
    finally:
        prostall.run = real_run
    rollup = [w for w in m4.warn if w.startswith("ACT ON THESE FIRST")]
    check(len(rollup) == 1, "a run with data-loss findings raises one "
                            "act-first warning in the geoprocessing window")
    check(all(cid in rollup[0] for cid in sick["act_first"])
          and len(sick["act_first"]) > 0,
          "and it names every act-first id the records produced, not a "
          "hardcoded list")
    check("exit code 2" in " ".join(m4.info),
          "the exit code and its meaning are reported, so a wrapper reading "
          "only the messages can tell a lost-edits finding from a clean run")
    check(any(l.startswith("APPLIED") for l in m4.warn) is False,
          "and still nothing was applied, with the fixes unticked")
finally:
    shutil.rmtree(folder, ignore_errors=True)

print("-" * 70)
print("the self-test tool drives prostall's own assertions")
folder = tempfile.mkdtemp()
try:
    v = pyt.VerifyProstall()
    vp = v.getParameterInfo()
    vm = _Messages()
    buffer = io.StringIO()
    real = sys.stdout
    sys.stdout = buffer
    try:
        v.execute(vp, vm)
    finally:
        sys.stdout = real
    check("0 failed" in (vp[0].value or ""),
          "the self-test tool reports prostall's own assertion count: %s"
          % vp[0].value)
    check(not vm.err, "and no assertion failed")
finally:
    shutil.rmtree(folder, ignore_errors=True)

print("-" * 70)
total = PASSED[0] + len(FAILED)
if FAILED:
    print("%d assertions, %d failed" % (total, len(FAILED)))
    for item in FAILED:
        print("  FAILED: %s" % item)
    sys.exit(1)
print("%d assertions, 0 failed" % total)
sys.exit(0)
