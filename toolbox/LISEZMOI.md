# prostall pour ArcGIS Pro — toolbox et rapport HTML

Une **Python Toolbox** (`.pyt`) qui expose `prostall.py` dans ArcGIS Pro et rend
le résultat en **un fichier HTML autonome** (aucune ressource externe, filtres
locaux, JSON embarqué pour le diff).

Trois fichiers, à garder ensemble :

| Fichier | Rôle |
|---|---|
| `ProstallDiagnostic.pyt` | La toolbox : deux outils, leurs paramètres, leurs messages |
| `html_report.py` | Le rendu HTML. Fonction pure sur le document de rapport, sans `arcpy` |
| `prostall.py` | Le diagnostic lui-même (à la racine du dépôt, à copier ici) |

## Installation

1. Copier ce dossier `toolbox/` dans un emplacement stable, par exemple
   `C:\GIS\Tools\prostall_toolbox\`.
2. Y copier `prostall.py` depuis la racine du dépôt. Les trois fichiers doivent
   être dans le **même** dossier : le `.pyt` ajoute son propre dossier à
   `sys.path` avant d'importer les modules voisins.
3. Dans ArcGIS Pro : volet **Catalogue → Toolboxes → Add Toolbox**, pointer sur
   `ProstallDiagnostic.pyt`.
4. Les deux outils apparaissent sous **« prostall - ArcGIS Pro slowness »**.

Prérequis : ArcGIS Pro 3.x (Python 3.9+), bibliothèque standard uniquement.
`prostall` n'utilise ni `arcpy` ni le package `arcgis`.

## Les deux outils

### 1. Diagnose ArcGIS Pro slowness

Lit le poste et écrit `prostall_<horodatage>.html`, `.json` et `.txt` dans le
dossier de sortie, puis ouvre le HTML dans le navigateur par défaut.

| Paramètre | Défaut | Effet |
|---|---|---|
| Output folder | `<scratch>\prostall` | Où écrire les trois fichiers |
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

### 2. Verify prostall (offline self-test)

Lance les assertions internes de prostall sur des postes de travail de
substitution (les 708 assertions). Ne lit aucun registre, n'écrit rien, ne
contacte aucun hôte. À lancer avant de faire confiance à un rapport sur une
nouvelle machine.

## ⚠️ À lire avant d'interpréter un résultat lancé depuis Pro

Lancer le diagnostic **depuis ArcGIS Pro** signifie qu'ArcGIS Pro est ouvert.
Ce n'est pas un détail :

- **DL-12** signale Pro en cours d'exécution — c'est une trouvaille de perte de
  données à part entière, elle remonte dans la liste « act on these first ».
- **PF-22** (lecture des temporisateurs de rafraîchissement dans le `.aprx`)
  est **refusée**. Lire un fichier projet pendant que Pro peut l'enregistrer
  peut faire échouer l'enregistrement : l'outil refuse plutôt que de provoquer
  la panne qu'on lui demande d'expliquer.
- **AP-01** (le correctif de cache) est **refusé** pour la même raison.

Un lancement depuis Pro est donc un rapport poste **moins** les contrôles de
fichier projet. Pour le rapport complet : fermer Pro et lancer
`python prostall.py` en ligne de commande, **dans la session de l'éditrice**,
sans élévation.

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
un poste illisible serait exactement le défaut que prostall existe pour
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

`html_report.py` échappe systématiquement tout ce qu'il écrit, et le bloc JSON
embarqué encode `<`, `>` et `&` en `\u003c` / `\u003e` / `\u0026` : aucune
chaîne du rapport ne peut être lue comme du balisage, et aucune ne peut fermer
l'élément `<script>` en avance. Le JSON se décode toujours à l'identique.
`tests/test_toolbox.py` le vérifie sur un document où chaque champ est un
payload.

## Vérifier

```
python tests/test_toolbox.py      # 77 assertions sur le rendu et la toolbox
python prostall.py --self-test    # 708 assertions sur le diagnostic
```

`tests/test_toolbox.py` n'a besoin que de la bibliothèque standard : il exécute
le `.pyt` contre un module `arcpy` de substitution, donc ce sont bien
`getParameterInfo`, `updateMessages` et `execute` de la toolbox qui tournent,
jusqu'à l'écriture réelle des trois fichiers.

## Confidentialité

Le rapport contient le nom du compte, des chemins locaux, des noms de fichiers
de connexion (les noms seulement, jamais le contenu) et des chemins d'exclusion.
**Le relire avant de l'envoyer à qui que ce soit.**
