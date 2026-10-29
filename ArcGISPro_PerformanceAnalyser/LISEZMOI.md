# ArcGIS Pro Performance Analyser — toolbox et rapport HTML

Une **Python Toolbox** (`.pyt`) qui expose le diagnostic de poste dans ArcGIS Pro
et rend le résultat en **un fichier HTML autonome** (aucune ressource externe,
filtres locaux, JSON embarqué pour le diff).

## Un seul fichier

Le moteur de diagnostic et le moteur de rendu sont **inlinés dans le `.pyt`**.
Il n'y a aucun module voisin à garder à côté, donc rien qui puisse manquer sur
le poste où le fichier atterrit.

| Fichier | Rôle |
|---|---|
| `ArcGISPro_PerformanceAnalyser.pyt` | **L'artefact livré.** Un outil, moteur et rendu inclus |
| `arcgis_pro_performance_analyser.py` | Le moteur de diagnostic et sa ligne de commande. Sans `arcpy` |
| `html_report.py` | Le rendu HTML. Fonction pure sur le document de rapport, sans `arcpy` |
| `toolbox_glue.py` | L'interface ArcGIS Pro. La seule partie qui importe `arcpy` |
| `build_toolbox.py` | Assemble les trois fichiers ci-dessus en un seul `.pyt` |

Le `.pyt` est **généré** : on modifie les sources, puis on lance
`python build_toolbox.py`. On ne modifie jamais le `.pyt` à la main —
`tests/test_toolbox.py` relance la génération et compare octet par octet, donc un
artefact qui a dérivé de ses sources ne peut pas rester dans le dépôt sans être
vu.

Les sources restent séparées parce qu'elles sont testables séparément : le
moteur se teste sans ArcGIS installé, le rendu est une fonction pure, et seule
l'interface a besoin d'`arcpy`. La fusion est une concaténation, et la
génération s'arrête si deux sources définissent un jour le même nom au niveau
module, parce que l'une masquerait l'autre silencieusement.

## Installation

1. Copier `ArcGISPro_PerformanceAnalyser.pyt` dans un emplacement stable, par
   exemple `C:\GIS\Tools\`.
2. Dans ArcGIS Pro : volet **Catalogue → Toolboxes → Add Toolbox**, pointer sur
   ce fichier.
3. L'outil apparaît sous **« ArcGIS Pro Performance Analyser »**.

C'est tout : il n'y a pas d'étape 4. Prérequis : ArcGIS Pro 3.x (Python 3.9+),
bibliothèque standard uniquement.

## L'outil

### Diagnostiquer la lenteur d'ArcGIS Pro

**C'est l'outil à lancer.**

Lit le poste et écrit `arcgis_pro_performance_analyser_<horodatage>.html`,
`.json` et `.txt` dans le dossier de sortie, puis ouvre le HTML dans le
navigateur par défaut.

**Pour un premier passage, ne remplissez rien** : les valeurs par défaut
suffisent, et aucun hôte ne sera contacté.

| Paramètre | Défaut | Ce qu'il faut mettre |
|---|---|---|
| Dossier de sortie | `<scratch>\ArcGISPro_PerformanceAnalyser` | Rien, ou un dossier **local** comme `C:\Temp\diag`. Jamais un partage réseau |
| Hôte de la géodatabase d'entreprise à sonder | vide | **Vide si vous ne savez pas.** Sinon le serveur nommé dans vos `.sde`, ex. `gisdb01` |
| Port de la géodatabase | 1433 | 1433 SQL Server, 1521 Oracle, 5432 PostgreSQL. Dans le doute, laissez 1433 |
| Hôte du portail à sonder (port 443) | vide | **Vide si vous ne savez pas.** Ex. `gis.monorg.ch` ou `www.arcgis.com` |
| Délai des sondes (ms) | 4000 | Une **borne**, pas une attente : une sonde qui répond en 40 ms rend la main aussitôt |
| Détaillé | décoché | À cocher quand il faut **prouver** un résultat : ajoute la valeur attendue et la ligne brute lue |
| Écrire aussi le rapport texte | coché | Le `.txt` est le format à coller dans un ticket |
| Ouvrir le rapport HTML dans le navigateur | coché | À décocher dans un modèle ModelBuilder |
| Appliquer les correctifs | **décoché** | **Seul paramètre qui modifie la machine.** Voir ci-dessous |

Chaque paramètre porte une **infobulle** (le point d'interrogation) et un
**paragraphe d'aide** dans le panneau d'aide de l'outil, avec son défaut et
un exemple.

**Si vous cochez « Appliquer les correctifs »**, deux correctifs seulement,
et chacun seulement si son propre contrôle l'a justifié :

- **AP-01** renomme le dossier de cache ESRI en lui ajoutant
  `.properf-<date>`. **Rien n'est supprimé** : l'ancien dossier reste sur le
  disque et Pro en reconstruit un neuf. Refusé depuis Pro, qui tient ce
  dossier.
- **AP-02** écrit la préférence « carte graphique hautes performances » pour
  `ArcGISPro.exe`, dans `HKCU` uniquement.

Chacun affiche **sa propre commande d'annulation** dans les messages et dans
le rapport. Copiez-la avant de fermer la fenêtre.

Le chemin du HTML est un **paramètre de sortie dérivé** : l'outil peut être
enchaîné dans un modèle ModelBuilder.

### L'autotest hors ligne n'est plus dans la boîte à outils

Une version précédente livrait un second outil, « Vérifier l'analyseur ». Il ne
lisait **rien** sur le poste : il vérifiait le *fichier*, en rejouant les
assertions internes du moteur sur des postes de travail de substitution. Le
confondre avec un diagnostic était facile, et cette confusion coûte plus cher
que la garantie ne rapporte : **l'outil a été retiré de la boîte à outils.**

Il reste disponible en ligne de commande, pour le développement :

```
python arcgis_pro_performance_analyser.py --self-test   # 727 assertions
```

Une assertion que la machine ne peut pas lancer est annoncée `SKIP` avec sa
raison, et comptée dans **aucun** des deux nombres : un contrôle non exécuté
n'est pas un contrôle réussi.

> **Défaut corrigé.** Une version précédente lançait ses processus de test avec
> `sys.executable`. Sous ArcGIS Pro, `sys.executable` n'est **pas** `python.exe`
> mais `C:\Program Files\ArcGIS\Pro\bin\ArcGISPro.exe` : l'autotest ouvrait donc
> une seconde copie d'ArcGIS Pro à l'écran de l'éditrice, laquelle ignorait
> l'argument et ne se terminait jamais — d'où un échec `TimeoutExpired` après
> deux minutes. L'interpréteur est maintenant **résolu par son nom**, et
> l'autotest annonce `SKIP` plutôt que de lancer ce qui n'est pas un
> interpréteur. L'outil de diagnostic n'a jamais été touché : il ne lance que
> `powershell.exe` et `wevtutil.exe`, par leur chemin complet dans `System32`.

## ⚠️ À lire avant d'interpréter un résultat lancé depuis Pro

Lancer le diagnostic **depuis ArcGIS Pro** signifie qu'ArcGIS Pro est ouvert.
Ce n'est pas un détail :

- **DL-12** signale Pro en cours d'exécution — c'est une trouvaille de perte de
  données à part entière, elle remonte dans la liste « act on these first ».
- Les **cinq contrôles qui lisent le fichier projet — PF-01, PF-09, PF-10,
  PF-14 et PF-22 — sont refusés**. Lire un `.aprx` pendant que Pro peut
  l'enregistrer peut faire échouer l'enregistrement : l'outil refuse plutôt que
  de provoquer la panne qu'on lui demande d'expliquer. Chacun répond `Info` avec
  sa raison, jamais un verdict inventé.
- **AP-01** (le correctif de cache) est **refusé** pour la même raison.

Un lancement depuis Pro est donc un rapport poste **moins** les contrôles de
fichier projet. Pour le rapport complet : fermer Pro et lancer
`python arcgis_pro_performance_analyser.py` en ligne de commande, **dans la
session de l'éditrice**, sans élévation.

Rien ici ne s'authentifie nulle part, aucun hôte n'est contacté sauf ceux que
vous nommez, et rien ne change sur la machine tant que « Apply the gated fixes »
reste décoché.

## Le rapport HTML

Une seule page, autonome, en français :

### Sommaire

Une barre qui reste en haut de page et mène à chaque section, avec le nombre de
contrôles de chaque bloc. Le lien « Perte de données » passe en rouge quand il
contient quelque chose.

### KPI

Sept cartes : **santé globale** (0–100), anomalies, avertissements, trouvailles
de perte de données, contrôles conformes, non déterminés, et **couverture de
mesure**.

Le score coûte 12 points par anomalie et 6 par avertissement — 18 et 9 quand la
trouvaille porte sur des modifications perdues. **Un lancement qui n'a rien pu
mesurer n'a pas de score du tout** : la jauge affiche `n/d`. Un cadran vert sur
un poste illisible serait exactement le défaut que cet outil existe pour
empêcher, déplacé en aval.

### Jauges

Cadres SVG inline : santé globale, couverture de mesure, mémoire libre, disque
libre du pire volume, latence du partage, liaison réseau négociée, taille du
cache ESRI.

**Chaque nombre vient d'un `kpi` que le contrôle a porté**, jamais d'une phrase
relue. Un contrôle qui n'a pas rendu de nombre ne dessine pas de jauge : la page
afficherait sinon un chiffre inventé par le moteur de rendu. `make_check` refuse
un `kpi` qui n'est pas un dictionnaire de nombres — une chaîne ou un booléen est
refusé.

### Drapeaux

Une ligne par symptôme S1 à S5, qui compte les contrôles en anomalie dont la
ligne d'impact nomme ce symptôme, avec un lien vers chacun. Les cinq lignes sont
toujours là, y compris à zéro : un zéro doit être visible, pas absent. Rien n'est
déduit — un contrôle dont l'impact ne nomme aucun symptôme n'en drape aucun.

### Chaque contrôle

Une carte avec : le badge de statut, le marqueur « perte de données », le
**problème détecté**, l'**impact**, et la **correction / optimisation** juste à
côté. La valeur attendue, la preuve et le correctif manuel sont repliés. Les
nombres mesurés apparaissent en pastilles, pour vérifier la jauge contre la
mesure.

### Le reste

Les portes des correctifs, la commande d'annulation de tout ce qui a été
appliqué, la légende des cinq statuts, et le document JSON embarqué pour le
diff. Un en-tête `Content-Security-Policy` n'autorise aucune source externe ;
mode sombre et feuille de style d'impression inclus.

### Sécurité du rendu

Le rapport est plein de chaînes fournies **par la machine**, pas par
l'opérateur : noms de comptes, chemins sur un partage, descriptions de cartes
réseau, chemins d'exclusion Defender, texte du journal d'événements. Un nom de
dossier sur un serveur de fichiers peut donc contenir du balisage.

Le moteur de rendu échappe systématiquement tout ce qu'il écrit, et le bloc JSON
embarqué encode `<`, `>` et `&` en `\u003c` / `\u003e` / `\u0026` : aucune
chaîne du rapport ne peut être lue comme du balisage, et aucune ne peut fermer
l'élément `<script>` en avance. Le JSON se décode toujours à l'identique.
`tests/test_toolbox.py` le vérifie sur un document où chaque champ est un
payload.

## Sources

Les seuils de cet outil sont **les siens** : ce sont des tolérances choisies pour
décider « conforme / à surveiller », pas des limites publiées par Esri. Ce qui
suit est la documentation Esri consultée pour écrire les pistes de correction,
avec ce qu'elle apporte réellement ici.

| Source | Ce qu'on y prend |
|---|---|
| [Settings that affect data access performance](https://doc.esri.com/en/arcgis-pro/latest/get-started/layer-map-project-perf-optimization.html) — documentation officielle ArcGIS Pro 3.7 | Reprojection à la volée quand les données ne sont pas dans la même référence spatiale (PF-01) ; coût des jointures et des requêtes de définition non sélectives (PF-14) ; poids des étiquettes et des `feature weights` (PF-14) ; intérêt des plages d'échelle de visibilité |
| [Troubleshooting Performance Issues in ArcGIS Pro](https://community.esri.com/t5/arcgis-pro-documents/troubleshooting-performance-issues-in-arcgis-pro/ta-p/1025516) — Esri Community | Pilote de carte graphique à prendre chez le fabricant ; antivirus à écarter temporairement pour isoler la cause (PF-17) ; `WARP` dans le readout = Pro émule la carte graphique sur le processeur ; historique de géotraitement stocké dans le `.aprx` (PF-10) ; ne garder ouverts que les cartes et mises en page utiles (PF-10) |
| [Why is ArcGIS Pro so slow?](https://community.esri.com/t5/arcgis-pro-questions/why-is-arcgis-pro-so-slow/td-p/508005/page/5) — Esri Community | Renommer les dossiers `ESRI` de `AppData\Local` et `AppData\Roaming` pour tester le cache (AP-01) ; autoriser `ArcGISPro.exe` dans le pare-feu Windows Defender ; latence réseau et données locales contre données en partage |

Ces pages ont été **relues lors de cette modification**. Elles ne sont pas
citées dans le code : les seuils chiffrés de l'outil restent les siens, et le
rapport le dit.

## Vérifier

```
python tests/test_toolbox.py      # 86 assertions : rendu, interface et .pyt généré
python arcgis_pro_performance_analyser.py --self-test   # 727 assertions sur le diagnostic
python build_toolbox.py --check   # le .pyt livré est bien ce que ses sources produisent
```

`tests/test_toolbox.py` n'a besoin que de la bibliothèque standard : il exécute
le `.pyt` contre un module `arcpy` de substitution, donc ce sont bien
`getParameterInfo`, `updateMessages` et `execute` de la toolbox qui tournent,
jusqu'à l'écriture réelle des trois fichiers.

Un détail que ce test épingle : le `.pyt` embarque **sa propre copie** du moteur.
Remplacer `run()` dans le module importé séparément ne change donc rien à ce que
fait l'outil — le test remplace la fonction dans le `.pyt`, et vérifie que les
deux ne sont pas le même objet, pour qu'un futur test ne puisse pas passer à
côté en patchant la mauvaise copie.

## Confidentialité

Le rapport contient le nom du compte, des chemins locaux, des noms de fichiers
de connexion (les noms seulement, jamais le contenu) et des chemins d'exclusion.
**Le relire avant de l'envoyer à qui que ce soit.**
