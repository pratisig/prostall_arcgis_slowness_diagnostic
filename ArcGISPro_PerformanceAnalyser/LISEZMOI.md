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
| `ArcGISPro_PerformanceAnalyser.pyt` | **L'artefact livré.** Deux outils, moteur et rendu inclus |
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
3. Les deux outils apparaissent sous **« ArcGIS Pro Performance Analyser »**.

C'est tout : il n'y a pas d'étape 4. Prérequis : ArcGIS Pro 3.x (Python 3.9+),
bibliothèque standard uniquement.

## Les deux outils

### 1. Diagnose ArcGIS Pro slowness

Lit le poste et écrit `arcgis_pro_performance_analyser_<horodatage>.html`,
`.json` et `.txt` dans le dossier de sortie, puis ouvre le HTML dans le
navigateur par défaut.

| Paramètre | Défaut | Effet |
|---|---|---|
| Output folder | `<scratch>\ArcGISPro_PerformanceAnalyser` | Où écrire les trois fichiers |
| Enterprise geodatabase host to probe | vide | Sonde TCP bornée, connect uniquement, sans identifiant. Vide = aucun hôte contacté |
| Geodatabase port | 1433 | Port de cette sonde |
| Portal host to probe | vide | Sonde TCP sur 443 |
| Probe timeout (ms) | 4000 | Borne de chaque sonde |
| Verbose | décoché | Ajoute le texte « attendu » et les lignes de preuve |
| Also write the plain-text report | coché | Écrit aussi le `.txt` |
| Open the HTML report in the default browser | coché | Ouvre le rapport |
| Apply the gated fixes | **décoché** | Seul paramètre qui modifie la machine |

Le chemin du HTML est un **paramètre de sortie dérivé** : l'outil peut être
enchaîné dans un modèle ModelBuilder.

### 2. Verify the analyser (offline self-test)

Lance les assertions internes du moteur sur des postes de travail de
substitution (708 assertions). Ne lit aucun registre, n'écrit rien, ne contacte
aucun hôte. À lancer avant de faire confiance à un rapport sur une nouvelle
machine : cela vérifie que le fichier qu'on vous a donné passe toujours ses
propres tests.

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

## Vérifier

```
python tests/test_toolbox.py      # 82 assertions : rendu, interface et .pyt généré
python arcgis_pro_performance_analyser.py --self-test   # 708 assertions sur le diagnostic
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
