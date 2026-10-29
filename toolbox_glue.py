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
            "Diagnostique pourquoi ArcGIS Pro est lent sur ce poste, et ne "
            "rapporte jamais une trouvaille que la machine n'a pas "
            "produite. Rend un rapport HTML, contrôle par contrôle : ce qui "
            "a été mesuré, ce que cela coûte à ArcGIS Pro, et quoi faire. "
            "Lecture seule tant que les correctifs ne sont pas cochés.")
        self.tools = [Diagnose]
        self.canRunInBackground = False


class Diagnose(object):
    """The workstation diagnostic, with the result as HTML."""

    def __init__(self):
        self.label = "Diagnostiquer la lenteur d'ArcGIS Pro"
        self.description = (
            "L'OUTIL À LANCER. Lit ce poste — registre, stockage, "
            "redirection OneDrive, réseau, processeur, carte graphique, "
            "cache, journal d'événements — et rend un rapport HTML qui dit, "
            "contrôle par contrôle, ce qui a été mesuré, ce que cela coûte à "
            "ArcGIS Pro et comment le corriger. Trente-huit contrôles, dont "
            "treize portent sur des modifications qui peuvent se perdre, et "
            "un qui relève dans le journal d'événements les plantages, les "
            "suspensions et les fermetures sans arrêt propre. Lecture seule, "
            "sauf si vous cochez explicitement les correctifs. Écrit un HTML, "
            "un JSON et un texte. Les paramètres par défaut suffisent pour un "
            "premier passage : ne renseignez rien.")
        self.canRunInBackground = False
        self.category = "Diagnostic"

    def getParameterInfo(self):
        def hinted(param, tooltip, long_help):
            """Attache les deux champs d'aide qu'ArcGIS Pro affiche.

            `helpMessage` est l'infobulle derrière le petit point
            d'interrogation ; `parameterHelp` est le paragraphe du volet
            d'aide de l'outil. Les deux sont remplis ici plutôt que laissés au
            libellé, parce que le libellé doit rester assez court pour tenir
            dans le volet — et un libellé court ne peut pas porter d'exemple.
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
               "Où écrire les rapports. Laissez vide pour garder le défaut.",
               "<p><b>À quoi ça sert</b> : c'est le dossier où l'outil écrit "
               "ses trois fichiers — le rapport <b>HTML</b> (celui qu'on lit), "
               "le <b>JSON</b> (pour comparer deux passages) et le <b>TXT</b> "
               "(pour coller dans un ticket).</p>"
               "<p><b>Défaut</b> : <code>&lt;scratch&gt;\\ArcGISPro_Performance"
               "Analyser</code>. Le dossier est créé s'il n'existe pas.</p>"
               "<p><b>Exemple</b> : <code>C:\\Temp\\diag_analyser</code>. "
               "Choisissez un dossier <b>local</b>, jamais un partage réseau ni "
               "un dossier OneDrive : l'écriture doit rester rapide et ne "
               "dépendre d'aucun serveur. Un rapport écrit sur un partage "
               "synchronisé peut être lu à moitié.</p>"
               "<p><b>Rien d'existant n'est écrasé</b> : deux passages dans la "
               "même seconde produisent deux jeux de fichiers distincts.</p>")

        sde = arcpy.Parameter(
            displayName="Hôte de la géodatabase d'entreprise à sonder",
            name="sde_server",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        sde.category = "Sondes réseau (sur demande)"
        hinted(sde,
               "Nom du serveur SQL/Oracle de vos données. Vide = aucun hôte "
               "contacté.",
               "<p><b>À quoi ça sert</b> : une latence élevée vers ce serveur "
               "explique à elle seule un Pro lent à l'ouverture des cartes. Le "
               "contrôle DL-10 mesure le temps de réponse.</p>"
               "<p><b>Laissez vide si vous ne savez pas quoi mettre.</b> Vide, "
               "aucun paquet ne quitte la machine et DL-10 répond "
               "<code>Info</code> au lieu d'inventer une mesure.</p>"
               "<p>Renseigné, l'outil ouvre <b>une seule</b> connexion TCP, "
               "mesure le temps de réponse, puis referme. Il ne s'authentifie "
               "jamais et n'envoie aucun identifiant — il n'existe d'ailleurs "
               "aucun paramètre de mot de passe.</p>"
               "<p><b>Exemple</b> : <code>gisdb01</code> ou "
               "<code>gisdb01.monorg.ch</code>. C'est le serveur nommé dans "
               "vos fichiers de connexion <code>.sde</code> ; le contrôle "
               "DL-11 les liste pour vous.</p>")

        port = arcpy.Parameter(
            displayName="Port de la géodatabase",
            name="sde_port",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input")
        port.value = 1433
        port.category = "Sondes réseau (sur demande)"
        hinted(port,
               "Port du serveur. 1433 = SQL Server, le plus courant.",
               "<p><b>À quoi ça sert</b> : c'est le port sur lequel la sonde "
               "DL-10 se connecte. Un port fermé se lit comme un serveur "
               "injoignable, ce qui est une fausse piste si le moteur n'est "
               "simplement pas le bon.</p>"
               "<p><b>Défaut</b> : <code>1433</code> (SQL Server).</p>"
               "<p><b>Valeurs courantes</b> : <code>1433</code> SQL Server, "
               "<code>1521</code> Oracle, <code>5432</code> PostgreSQL.</p>"
               "<p><b>Exemple</b> : si vos <code>.sde</code> nomment un serveur "
               "PostgreSQL, mettez <code>5432</code>. Dans le doute, laissez "
               "1433 : l'outil ne devine jamais, il dit ce qu'il a trouvé.</p>"
               "<p>Les valeurs hors de 1 à 65535 sont refusées avant "
               "l'exécution.</p>")

        portal = arcpy.Parameter(
            displayName="Hôte du portail à sonder (port 443)",
            name="portal",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        portal.category = "Sondes réseau (sur demande)"
        hinted(portal,
               "Adresse de votre portail ou d'ArcGIS Online. Vide = aucun "
               "hôte contacté.",
               "<p><b>À quoi ça sert</b> : Pro interroge le portail au "
               "démarrage et pour chaque couche publiée. Un portail lent se "
               "lit comme un Pro lent à l'ouverture, sans qu'aucune couche "
               "soit en cause. Le contrôle PF-19 mesure cette réponse.</p>"
               "<p><b>Laissez vide si vous ne savez pas quoi mettre.</b></p>"
               "<p><b>Exemple</b> : <code>gis.monorg.ch</code> pour un Portal "
               "for ArcGIS interne, ou <code>www.arcgis.com</code> pour "
               "ArcGIS Online.</p>"
               "<p>Une seule connexion TCP sur le port 443, mesurée puis "
               "refermée. Aucun identifiant n'est envoyé, aucune page n'est "
               "téléchargée.</p>")

        timeout = arcpy.Parameter(
            displayName="Délai des sondes (millisecondes)",
            name="timeout",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input")
        timeout.value = 4000
        timeout.category = "Sondes réseau (sur demande)"
        hinted(timeout,
               "Plafond d'attente des sondes réseau. Une borne, pas une "
               "attente.",
               "<p><b>À quoi ça sert</b> : c'est le temps maximal que DL-10 et "
               "PF-19 attendent avant de déclarer l'hôte injoignable.</p>"
               "<p><b>Défaut</b> : <code>4000</code> ms.</p>"
               "<p><b>C'est une borne, pas une attente</b> : une sonde qui "
               "répond en 40 ms rend la main aussitôt. Rien n'est bloqué "
               "pendant quatre secondes quand le serveur est rapide.</p>"
               "<p><b>Exemple</b> : montez à <code>10000</code> sur une liaison "
               "VPN lente, pour ne pas lire « injoignable » sur un serveur qui "
               "répond en six secondes. Descendez à <code>1500</code> pour un "
               "passage rapide en atelier.</p>"
               "<p>Ce paramètre ne concerne <b>que</b> les sondes que vous avez "
               "demandées : videz les deux hôtes et il ne sert plus à "
               "rien.</p>")

        verbose = arcpy.Parameter(
            displayName="Détaillé",
            name="verbose",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        verbose.value = False
        hinted(verbose,
               "Affiche ce que l'outil attendait et ce qu'il a réellement "
               "lu.",
               "<p><b>À quoi ça sert</b> : à <b>prouver</b> un résultat à "
               "quelqu'un. Chaque contrôle montre alors la valeur attendue et "
               "la ligne brute lue sur la machine, en plus du verdict. C'est "
               "ce qu'il faut joindre quand le support demande « sur quoi vous "
               "basez-vous ? ».</p>"
               "<p><b>Défaut</b> : décoché.</p>"
               "<p>Décoché, le rapport reste complet et tous les verdicts sont "
               "là ; seules ces lignes de preuve sont repliées.</p>"
               "<p><b>Exemple</b> : cochez-le avant un appel au support Esri, "
               "puis joignez le <code>.txt</code> — il contiendra les valeurs "
               "brutes qui appuient chaque ligne.</p>")

        text = arcpy.Parameter(
            displayName="Écrire aussi le rapport texte",
            name="write_text",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        text.value = True
        hinted(text,
               "Ajoute un .txt, pratique à coller dans un ticket.",
               "<p><b>À quoi ça sert</b> : le <code>.txt</code> reprend le "
               "rapport HTML en texte brut. C'est le format à coller dans un "
               "appel au support ou dans un courriel, parce qu'il ne dépend "
               "d'aucun navigateur et qu'il passe dans n'importe quelle "
               "messagerie.</p>"
               "<p><b>Défaut</b> : coché.</p>"
               "<p><b>Exemple</b> : laissez-le coché. Décochez-le seulement si "
               "le dossier de sortie est soumis à un quota serré, ou si vous "
               "ne voulez qu'un seul fichier.</p>"
               "<p>Le JSON est écrit dans tous les cas : c'est lui qui permet "
               "de comparer deux passages à quelques jours d'écart.</p>")

        browser = arcpy.Parameter(
            displayName="Ouvrir le rapport HTML dans le navigateur",
            name="open_browser",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        browser.value = True
        hinted(browser,
               "Ouvre le rapport à la fin. Décochez pour un lot ou un "
               "modèle.",
               "<p><b>À quoi ça sert</b> : le rapport s'ouvre dans le "
               "navigateur par défaut dès qu'il est écrit, pour ne pas avoir à "
               "chercher le fichier.</p>"
               "<p><b>Défaut</b> : coché.</p>"
               "<p><b>Exemple</b> : décochez-le si l'outil tourne dans un "
               "modèle ModelBuilder ou dans un lot — une fenêtre qui s'ouvre à "
               "chaque itération bloque le lot. Décochez-le aussi si le "
               "navigateur est bloqué par stratégie de groupe.</p>"
               "<p><b>Le fichier est écrit dans tous les cas</b> et son chemin "
               "apparaît dans les messages de l'outil : rien n'est perdu si "
               "l'ouverture échoue.</p>")

        apply_fixes = arcpy.Parameter(
            displayName="Appliquer les correctifs (renomme le cache, épingle "
                        "le choix de carte graphique)",
            name="apply_fixes",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        apply_fixes.value = False
        apply_fixes.category = "Modifie la machine"
        hinted(apply_fixes,
               "SEUL paramètre qui modifie la machine. Décoché, l'outil est en "
               "lecture seule.",
               "<p><b>À quoi ça sert</b> : c'est l'interrupteur entre « lire » "
               "et « réparer ». Tant qu'il est décoché, l'outil ne fait que "
               "lire la machine et n'y change rien.</p>"
               "<p><b>Défaut</b> : <b>décoché</b>.</p>"
               "<p>Cochez-le et <b>deux correctifs seulement</b> s'appliquent, "
               "chacun uniquement si son propre contrôle l'a justifié :</p>"
               "<ul>"
               "<li><b>AP-01</b> renomme le dossier de cache ESRI en lui "
               "ajoutant un suffixe <code>.properf-&lt;date&gt;</code>. "
               "<b>Rien n'est supprimé</b> : l'ancien dossier reste sur le "
               "disque et Pro en reconstruit un neuf. Refusé depuis Pro, parce "
               "que Pro tient ce dossier.</li>"
               "<li><b>AP-02</b> épingle ArcGIS Pro sur la carte graphique "
               "hautes performances, en écrivant la préférence pour "
               "<code>ArcGISPro.exe</code> dans <code>HKCU</code> uniquement "
               "— jamais dans la ruche machine, donc sans droit "
               "administrateur.</li>"
               "</ul>"
               "<p><b>Chaque correctif appliqué affiche sa propre commande "
               "d'annulation</b>, dans les messages et dans le rapport. "
               "Copiez-la avant de fermer la fenêtre.</p>"
               "<p><b>Exemple</b> : faites d'abord un passage <b>décoché</b>, "
               "lisez le rapport, puis relancez coché seulement si AP-01 ou "
               "AP-02 y figure comme proposé.</p>")

        html_out = arcpy.Parameter(
            displayName="Rapport HTML",
            name="html_report",
            datatype="GPString",
            parameterType="Derived",
            direction="Output")
        hinted(html_out,
               "Sortie : chemin du rapport HTML. Ne se remplit pas à la main.",
               "<p><b>À quoi ça sert</b> : c'est une <b>sortie dérivée</b> — "
               "l'outil la remplit lui-même avec le chemin du rapport qu'il "
               "vient d'écrire.</p>"
               "<p><b>Ne la remplissez pas</b> : elle est en lecture seule et "
               "toute valeur saisie serait ignorée.</p>"
               "<p>Elle existe pour que l'outil puisse être <b>enchaîné</b> "
               "dans un modèle ModelBuilder.</p>"
               "<p><b>Exemple</b> : dans un modèle, reliez cette sortie à un "
               "outil « Envoyer un courrier » pour joindre automatiquement le "
               "rapport du jour.</p>")

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
