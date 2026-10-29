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
            "Deux outils.  1) Diagnostiquer la lenteur d'ArcGIS Pro : "
            "celui qu'on lance - il lit ce poste et rend un rapport HTML. "
            "2) Verifier l'analyseur : un controle du fichier lui-meme, a "
            "lancer une fois sur une nouvelle machine avant de croire un "
            "rapport. Lecture seule tant que les correctifs ne sont pas "
            "coches.")
        self.tools = [Diagnose, VerifyAnalyser]
        self.canRunInBackground = False


class Diagnose(object):
    """The workstation diagnostic, with the result as HTML."""

    def __init__(self):
        self.label = "Diagnostiquer la lenteur d'ArcGIS Pro"
        self.description = (
            "L'OUTIL A LANCER. Lit ce poste - registre, stockage, "
            "redirection OneDrive, reseau, cache - et rend un rapport HTML "
            "qui dit, controle par controle, ce qui a ete mesure, ce que "
            "cela coute a ArcGIS Pro et comment le corriger. Trente-six "
            "controles, dont treize portent sur des modifications qui "
            "peuvent se perdre. Lecture seule, sauf si vous cochez "
            "explicitement les correctifs. Ecrit un HTML, un JSON et un "
            "texte. Les parametres par defaut suffisent pour un premier "
            "passage : ne renseignez rien.")
        self.canRunInBackground = False
        self.category = "Diagnostic"

    def getParameterInfo(self):
        def hinted(param, tooltip, long_help):
            """Attach the two help fields ArcGIS Pro shows for a parameter.

            `helpMessage` is the tooltip behind the little question mark;
            `parameterHelp` is the paragraph in the tool's help panel. Both are
            filled in here rather than left to the display name, because the
            display name has to stay short enough to fit the pane, and a short
            label cannot carry an example.
            """
            param.helpMessage = tooltip
            param.parameterHelp = long_help
            return param

        out = arcpy.Parameter(
            displayName="Dossier de sortie",
            name="output_folder",
            datatype="DEFolder",
            parameterType="Optional",
            direction="Input")
        out.value = os.path.join(
            arcpy.env.scratchFolder or os.environ.get("TEMP") or ".",
            "ArcGISPro_PerformanceAnalyser")
        hinted(out,
               "Ou ecrire les rapports. Laisse vide pour garder le defaut.",
               "<p>Dossier ou l'outil ecrit ses trois fichiers : le rapport "
               "<b>HTML</b> (celui qu'on lit), le <b>JSON</b> (pour comparer "
               "deux passages) et le <b>TXT</b> (pour coller dans un ticket).</p>"
               "<p><b>Defaut</b> : <code>&lt;scratch&gt;\\ArcGISPro_Performance"
               "Analyser</code>. Le dossier est cree s'il n'existe pas.</p>"
               "<p><b>Exemple</b> : <code>C:\\Temp\\diag_analyser</code>. "
               "Choisissez un dossier <b>local</b>, pas un partage reseau : "
               "l'ecriture doit rester rapide et ne dependre d'aucun "
               "serveur.</p>"
               "<p>Rien d'existant n'est ecrase : deux passages dans la meme "
               "seconde produisent deux jeux de fichiers.</p>")

        sde = arcpy.Parameter(
            displayName="Hote de la geodatabase d'entreprise a sonder",
            name="sde_server",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        sde.category = "Sondes reseau (sur demande)"
        hinted(sde,
               "Nom du serveur SQL/Oracle de vos donnees. Vide = aucun "
               "hote contacte.",
               "<p><b>Laissez vide si vous ne savez pas quoi mettre.</b> Vide, "
               "aucun paquet ne quitte la machine et le controle DL-10 repond "
               "<code>Info</code> au lieu d'inventer une mesure.</p>"
               "<p>Renseigne, l'outil ouvre <b>une seule</b> connexion TCP, "
               "mesure le temps de reponse, puis referme. Il ne s'authentifie "
               "jamais et n'envoie aucun identifiant.</p>"
               "<p><b>Exemple</b> : <code>gisdb01</code> ou "
               "<code>gisdb01.monorg.ch</code>. C'est le serveur nomme dans "
               "vos fichiers de connexion <code>.sde</code>.</p>"
               "<p><b>A quoi ca sert</b> : une latence elevee vers ce serveur "
               "explique a elle seule un Pro lent a l'ouverture des cartes.</p>")

        port = arcpy.Parameter(
            displayName="Port de la geodatabase",
            name="sde_port",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input")
        port.value = 1433
        port.category = "Sondes reseau (sur demande)"
        hinted(port,
               "Port du serveur. 1433 = SQL Server (le plus courant).",
               "<p><b>Defaut</b> : <code>1433</code> (SQL Server).</p>"
               "<p><b>Valeurs courantes</b> : <code>1433</code> SQL Server, "
               "<code>1521</code> Oracle, <code>5432</code> PostgreSQL.</p>"
               "<p>Si vous ne connaissez pas le moteur, laissez 1433 : un port "
               "ferme repond « ferme », ce qui est deja une information, et "
               "l'outil ne devine jamais.</p>")

        portal = arcpy.Parameter(
            displayName="Hote du portail a sonder (port 443)",
            name="portal",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        portal.category = "Sondes reseau (sur demande)"
        hinted(portal,
               "Adresse de votre portail ou d'ArcGIS Online. Vide = aucun "
               "hote contacte.",
               "<p><b>Laissez vide si vous ne savez pas quoi mettre.</b></p>"
               "<p><b>Exemple</b> : <code>gis.monorg.ch</code> pour un Portal "
               "for ArcGIS interne, ou <code>www.arcgis.com</code> pour "
               "ArcGIS Online.</p>"
               "<p>Une seule connexion TCP sur le port 443, mesuree puis "
               "refermee. Aucun identifiant n'est envoye.</p>")

        timeout = arcpy.Parameter(
            displayName="Delai des sondes (millisecondes)",
            name="timeout",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input")
        timeout.value = 4000
        timeout.category = "Sondes reseau (sur demande)"
        hinted(timeout,
               "Duree maximale de chaque sonde. 4000 ms convient presque "
               "toujours.",
               "<p><b>Defaut</b> : <code>4000</code> ms (4 secondes).</p>"
               "<p>C'est une <b>borne</b>, pas une attente : une sonde qui "
               "repond en 40 ms rend la main en 40 ms. Le delai ne sert que "
               "pour un serveur injoignable.</p>"
               "<p>Augmentez a <code>10000</code> sur un reseau tres lent, "
               "descendez a <code>1500</code> pour un passage plus rapide.</p>")

        verbose = arcpy.Parameter(
            displayName="Detaille (valeur attendue et lignes de preuve)",
            name="verbose",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        verbose.value = False
        hinted(verbose,
               "Affiche ce que l'outil attendait et ce qu'il a reellement lu.",
               "<p><b>Defaut</b> : decoche.</p>"
               "<p>Cochez-le quand vous devez <b>prouver</b> un resultat a "
               "quelqu'un : chaque controle montre alors la valeur attendue et "
               "la ligne brute lue sur la machine, en plus du verdict.</p>"
               "<p>Decoche, le rapport reste complet ; seules ces lignes de "
               "preuve sont repliees.</p>")

        text = arcpy.Parameter(
            displayName="Ecrire aussi le rapport texte",
            name="write_text",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        text.value = True
        hinted(text,
               "Ajoute un .txt, pratique a coller dans un ticket.",
               "<p><b>Defaut</b> : coche.</p>"
               "<p>Le <code>.txt</code> reprend le rapport HTML en texte brut. "
               "C'est le format a coller dans un appel au support ou dans un "
               "courriel, parce qu'il ne depend d'aucun navigateur.</p>")

        browser = arcpy.Parameter(
            displayName="Ouvrir le rapport HTML dans le navigateur",
            name="open_browser",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        browser.value = True
        hinted(browser,
               "Ouvre le rapport a la fin. Decochez pour un lot ou un modele.",
               "<p><b>Defaut</b> : coche.</p>"
               "<p>Le rapport s'ouvre dans le navigateur par defaut. "
               "Decochez-le si l'outil tourne dans un modele ModelBuilder, ou "
               "si le navigateur est bloque par strategie de groupe : le fichier est ecrit dans "
               "tous les cas et son chemin apparait dans les messages.</p>")

        apply_fixes = arcpy.Parameter(
            displayName="Appliquer les correctifs (renomme le cache, epingle "
                        "le choix de carte graphique)",
            name="apply_fixes",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        apply_fixes.value = False
        apply_fixes.category = "Modifie la machine"
        hinted(apply_fixes,
               "SEUL parametre qui modifie la machine. Laisse decoche, "
               "l'outil est en lecture seule.",
               "<p><b>Defaut</b> : <b>decoche</b>. L'outil ne fait alors que "
               "lire.</p>"
               "<p>Coche, deux correctifs seulement, et chacun seulement si son "
               "propre controle l'a justifie :</p>"
               "<ul>"
               "<li><b>AP-01</b> renomme le dossier de cache ESRI en lui "
               "ajoutant un suffixe <code>.properf-&lt;date&gt;</code>. "
               "<b>Rien n'est supprime</b> : l'ancien dossier reste sur le "
               "disque et Pro en reconstruit un neuf. Refuse depuis Pro, parce "
               "que Pro tient ce dossier.</li>"
               "<li><b>AP-02</b> ecrit la preference « carte graphique "
               "hautes performances » pour <code>ArcGISPro.exe</code>, dans "
               "<code>HKCU</code> uniquement.</li>"
               "</ul>"
               "<p><b>Chaque correctif applique affiche sa propre commande "
               "d'annulation</b> dans les messages et dans le rapport. Copiez-"
               "la avant de fermer la fenetre.</p>")

        html_out = arcpy.Parameter(
            displayName="Rapport HTML",
            name="html_report",
            datatype="GPString",
            parameterType="Derived",
            direction="Output")
        hinted(html_out,
               "Sortie : chemin du rapport HTML. Ne se remplit pas a la main.",
               "<p><b>Sortie derivee</b> : l'outil la remplit lui-meme avec le "
               "chemin du rapport ecrit.</p>"
               "<p>Elle existe pour que l'outil puisse etre <b>enchaine</b> "
               "dans un modele ModelBuilder : un outil suivant peut reprendre "
               "ce chemin.</p>")

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
        self.label = "Verifier l'analyseur (autotest hors ligne)"
        self.description = (
            "PAS un diagnostic de votre poste. Cet outil verifie le "
            "FICHIER : il rejoue ses propres assertions sur des postes de "
            "travail de substitution et dit combien passent. A lancer une "
            "fois sur une nouvelle machine, avant de croire un rapport - "
            "cela prouve que la copie qu'on vous a donnee n'est pas "
            "abimee. Ne lit aucun registre, n'ecrit rien, ne contacte "
            "aucun hote. Aucun parametre a remplir.")
        self.canRunInBackground = False
        self.category = "Diagnostic"

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
        lines = captured.splitlines()
        total = len([l for l in lines if l.startswith(("PASS  ", "FAIL  "))])
        failed = [l for l in lines if l.startswith("FAIL  ")]
        not_run = [l for l in lines if l.startswith("SKIP  ")]
        tail = "" if not not_run else ", %d not run" % len(not_run)
        for line in not_run:
            messages.addWarningMessage("  %s" % line)
        if code == 0:
            messages.addMessage(
                "%d assertions, 0 failed%s, in %.1f s."
                % (total, tail, time.time() - started))
            parameters[0].value = "%d assertions, 0 failed%s" % (total, tail)
        else:
            for line in failed:
                messages.addErrorMessage("  %s" % line)
            messages.addErrorMessage(
                "%d of %d assertions failed%s." % (len(failed), total, tail))
            parameters[0].value = "%d of %d assertions failed%s" % (
                len(failed), total, tail)
            raise arcpy.ExecuteError()
        return
