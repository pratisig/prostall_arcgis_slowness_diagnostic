r"""The ArcGIS Pro glue: two geoprocessing tools over the diagnostic engine
and the HTML renderer.

This file is a build input, not the shipped artefact. build_toolbox.py inlines
it below the engine and the renderer to produce the single file
ArcGISPro_PerformanceAnalyser/ArcGISPro_PerformanceAnalyser.pyt, and that one
file is what you add to ArcGIS Pro. It stays a separate source because it is
the only part that imports arcpy, so the engine and the renderer can be tested
on a machine with no ArcGIS at all.

The two tools appear under "ArcGIS Pro Performance Analyser".

Run "Diagnose ArcGIS Pro slowness" from the Geoprocessing pane. It writes
arcgis_pro_performance_analyser_<stamp>.html, .json and .txt into the output
folder and opens the HTML in the default browser.

Read this before you trust the numbers
--------------------------------------
Running the diagnostic from inside ArcGIS Pro means ArcGIS Pro is running.
That is not a detail:

  * DL-12 reports Pro as running, which is a data-loss finding in its own
    right and lands in the act-first list.
  * PF-22, the read of the .aprx layer refresh timers, is refused. Reading a
    project file while Pro may be saving it can make the save fail, so the
    tool refuses rather than cause the very failure it was run to explain.
  * AP-01, the cache fix, is refused for the same reason.

So a run from inside Pro is a workstation report minus the project-file
checks. For the complete report, close Pro and run arcgis_pro_performance_analyser.py from a command
prompt in the editor's own session. The toolbox exists for the run you can do
without leaving the application, and it says so on the page.

Nothing here signs in to anything, no host is contacted unless you name one,
and no machine state changes unless you tick "Apply the gated fixes".
"""

import os
import time

import arcpy

# BEGIN MERGE-IMPORTS
# build_toolbox.py replaces this block when it inlines the two modules into the
# single-file .pyt. There, the engine and the renderer are defined above in this
# same module, so the same qualified names are served from its globals.
import arcgis_pro_performance_analyser as engine
import html_report as report
# END MERGE-IMPORTS


def _pro_release():
    """The ArcGIS Pro release this toolbox is running under, or None."""
    try:
        return "%s (%s)" % (arcpy.GetInstallInfo()["Version"],
                            arcpy.GetInstallInfo()["BuildNumber"])
    except Exception:
        return None


def _unique(path):
    """A path that does not already exist.

    the analyser's own report writer stamps to the second, so two runs inside one
    second land on the same name and the second silently overwrites the first.
    """
    root, ext = os.path.splitext(path)
    stamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    candidate = "%s_%s%s" % (root, stamp, ext)
    counter = 1
    while os.path.exists(candidate):
        candidate = "%s_%s_%d%s" % (root, stamp, counter, ext)
        counter += 1
    return candidate


def _tail(text, lines=40):
    """The last N non-empty lines of a captured stream."""
    kept = [l for l in (text or "").splitlines() if l.strip()]
    return kept[-lines:]


class Toolbox(object):
    def __init__(self):
        self.label = "ArcGIS Pro Performance Analyser"
        self.alias = "properf"
        self.description = (
            "Diagnose why ArcGIS Pro is slow on this workstation, and never "
            "report a finding the machine did not produce. Read-only unless "
            "you enable the fixes.")
        self.tools = [Diagnose, VerifyAnalyser]
        self.canRunInBackground = False


class Diagnose(object):
    """The workstation diagnostic, with the result as HTML."""

    def __init__(self):
        self.label = "Diagnose ArcGIS Pro slowness"
        self.description = (
            "Read this workstation's registry, storage, OneDrive redirection, "
            "network and cache state, and report which of it explains a slow "
            "ArcGIS Pro session and which of it could lose an edit. Read-only "
            "unless the fixes are enabled. Writes an HTML, a JSON and a text "
            "report.")
        self.canRunInBackground = False
        self.category = "Diagnose"

    def getParameterInfo(self):
        out = arcpy.Parameter(
            displayName="Output folder",
            name="output_folder",
            datatype="DEFolder",
            parameterType="Optional",
            direction="Input")
        out.value = os.path.join(
            arcpy.env.scratchFolder or os.environ.get("TEMP") or ".",
            "ArcGISPro_PerformanceAnalyser")

        sde = arcpy.Parameter(
            displayName="Enterprise geodatabase host to probe",
            name="sde_server",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        sde.category = "Network probes (opt-in)"

        port = arcpy.Parameter(
            displayName="Geodatabase port",
            name="sde_port",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input")
        port.value = 1433
        port.category = "Network probes (opt-in)"

        portal = arcpy.Parameter(
            displayName="Portal host to probe (port 443)",
            name="portal",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        portal.category = "Network probes (opt-in)"

        timeout = arcpy.Parameter(
            displayName="Probe timeout (milliseconds)",
            name="timeout",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input")
        timeout.value = 4000
        timeout.category = "Network probes (opt-in)"

        verbose = arcpy.Parameter(
            displayName="Verbose (expected text and evidence lines)",
            name="verbose",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        verbose.value = False

        text = arcpy.Parameter(
            displayName="Also write the plain-text report",
            name="write_text",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        text.value = True

        browser = arcpy.Parameter(
            displayName="Open the HTML report in the default browser",
            name="open_browser",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        browser.value = True

        apply_fixes = arcpy.Parameter(
            displayName="Apply the gated fixes (renames the cache aside, pins "
                        "the GPU preference)",
            name="apply_fixes",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        apply_fixes.value = False
        apply_fixes.category = "Changes machine state"

        html_out = arcpy.Parameter(
            displayName="HTML report",
            name="html_report",
            datatype="GPString",
            parameterType="Derived",
            direction="Output")

        return [out, sde, port, portal, timeout, verbose, text, browser,
                apply_fixes, html_out]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        """Refuse what the analyser's own parser would refuse, before it runs."""
        port = parameters[2].value
        if port is not None and not 1 <= int(port) <= 65535:
            parameters[2].setErrorMessage(
                "The port must be between 1 and 65535, got %s." % port)
        timeout = parameters[4].value
        if timeout is not None and int(timeout) < 1:
            parameters[4].setErrorMessage(
                "The timeout must be at least 1 millisecond.")
        for index, flag in ((1, "geodatabase host"), (3, "portal host")):
            host = parameters[index].valueAsText
            if host:
                problem = engine.host_problem(host)
                if problem:
                    parameters[index].setErrorMessage(
                        "%r is not a host name: %s" % (host, problem))
        if parameters[8].value:
            parameters[8].setWarningMessage(
                "You are running this from inside ArcGIS Pro, so DL-12 reports "
                "Pro as running and the cache fix (AP-01) is refused. Only the "
                "GPU preference (AP-02) can apply. Both print their own undo "
                "command, and neither deletes anything. Run arcgis_pro_performance_analyser.py from a "
                "command prompt with Pro closed for the full set of fixes.")
        return

    def execute(self, parameters, messages):
        folder = (parameters[0].valueAsText
                  or os.path.join(os.environ.get("TEMP") or ".", "ArcGISPro_PerformanceAnalyser"))
        opts = {
            "sde_server": parameters[1].valueAsText or None,
            "sde_port": int(parameters[2].value or 1433),
            "portal": parameters[3].valueAsText or None,
            "timeout": int(parameters[4].value or 4000),
            "apply": bool(parameters[8].value),
        }
        verbose = bool(parameters[5].value)

        messages.addMessage("ArcGIS Pro Performance Analyser %d - reading this workstation."
                            % engine.REPORT_VERSION)
        if opts["sde_server"] or opts["portal"]:
            messages.addMessage(
                "Network probes: %s"
                % ", ".join(filter(None, [opts["sde_server"], opts["portal"]])))
        else:
            messages.addMessage(
                "No host will be contacted. Name a geodatabase or portal host "
                "to add the two bounded TCP probes.")
        messages.addMessage(
            "Note: a project folder that already lives on a share is read, "
            "because that is what Pro does when it opens the project, and "
            "PF-03 times one listing of it.")

        started = time.time()
        env = engine.Env()
        document = engine.run(env, opts)
        code = engine.exit_code(document["checks"])
        document["exit_code"] = code
        document["symptoms"] = list(engine.SYMPTOMS)
        messages.addMessage("Read %d checks in %.1f s."
                            % (len(document["checks"]), time.time() - started))

        if not os.path.isdir(folder):
            os.makedirs(folder)
        html_path = _unique(os.path.join(folder, "arcgis_pro_performance_analyser.html"))
        json_path = os.path.splitext(html_path)[0] + ".json"

        meta = {}
        release = _pro_release()
        if release:
            meta["ArcGIS Pro"] = release
        meta["ran from"] = "the ArcGIS Pro geoprocessing pane, so Pro was open"

        report.write_html(document, html_path, verbose, code, meta)
        handle = open(json_path, "wb")
        try:
            import json as _json
            handle.write(_json.dumps(document, indent=1, sort_keys=True)
                         .encode("utf-8"))
        finally:
            handle.close()
        written = [html_path, json_path]

        if parameters[6].value:
            text_path = os.path.splitext(html_path)[0] + ".txt"
            handle = open(text_path, "wb")
            try:
                handle.write(("\n".join(engine.render(document, verbose))
                              + "\n").encode("utf-8"))
            finally:
                handle.close()
            written.append(text_path)

        # The summary, in the messages window, so the operator sees the
        # verdict without leaving ArcGIS Pro.
        for status, count in engine.counts(document["checks"]):
            if count:
                messages.addMessage("  %-8s %d" % (status.upper(), count))
        if document["act_first"]:
            messages.addWarningMessage(
                "ACT ON THESE FIRST - they bear on the vanished edits: %s"
                % ", ".join(document["act_first"]))
        for note in document["notes"]:
            messages.addMessage("  fix gate: %s" % note)
        for record in document["applied"]:
            messages.addWarningMessage(
                "APPLIED [%s] %s  undo: %s"
                % (record["id"], record["result"], record["undo"]))
        for path in written:
            messages.addMessage("  report: %s" % path)

        parameters[9].value = html_path

        if parameters[7].value:
            try:
                import webbrowser
                webbrowser.open("file:///" + html_path.replace("\\", "/"))
                messages.addMessage("Opened the HTML report in the default "
                                    "browser.")
            except Exception as exc:
                messages.addWarningMessage(
                    "Could not open a browser (%s). The report is at %s"
                    % (exc, html_path))

        messages.addMessage(
            "The report carries the account name, local paths, connection file "
            "names and exclusion paths. Read it before you send it to anyone.")
        messages.addMessage("Analyser exit code %d: %s"
                            % (code, report.EXIT_MEANING.get(code, "?")))
        return


class VerifyAnalyser(object):
    """Run the analyser's own offline assertions.

    The tool's whole claim is that it never reports a finding the machine did
    not produce, and that claim is enforced by the engine's own offline
    assertions over its decision functions. Run this before you trust a report from a new machine.
    It reads no registry, writes nothing and contacts no host.
    """

    def __init__(self):
        self.label = "Verify the analyser (offline self-test)"
        self.description = (
            "Run the analyser's offline assertions over its own decision "
            "functions, on stand-in workstations, and report how many passed. "
            "Reads no registry, writes nothing, contacts no host.")
        self.canRunInBackground = False
        self.category = "Diagnose"

    def getParameterInfo(self):
        result = arcpy.Parameter(
            displayName="Result",
            name="result",
            datatype="GPString",
            parameterType="Derived",
            direction="Output")
        return [result]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        import contextlib
        import io

        buffer = io.StringIO()
        started = time.time()
        try:
            with contextlib.redirect_stdout(buffer):
                code = engine.self_test()
        except Exception as exc:
            messages.addErrorMessage("The self-test could not run: %s: %s"
                                     % (type(exc).__name__, exc))
            raise arcpy.ExecuteError()
        captured = buffer.getvalue()
        for line in _tail(captured, 25):
            messages.addMessage("  %s" % line)
        total = len([l for l in captured.splitlines()
                     if l.startswith(("PASS  ", "FAIL  "))])
        failed = [l for l in captured.splitlines() if l.startswith("FAIL  ")]
        if code == 0:
            messages.addMessage(
                "%d assertions, 0 failed, in %.1f s."
                % (total, time.time() - started))
            parameters[0].value = "%d assertions, 0 failed" % total
        else:
            for line in failed:
                messages.addErrorMessage("  %s" % line)
            messages.addErrorMessage(
                "%d of %d assertions failed." % (len(failed), total))
            parameters[0].value = "%d of %d assertions failed" % (
                len(failed), total)
            raise arcpy.ExecuteError()
        return
