# Canvas File Checker

Script Python (stdlib uniquement — aucun `pip install`) qui vérifie que tous les fichiers d'un cours
Canvas (<https://unissvalbard.instructure.com>) sont bien présents en local, et télécharge automatiquement
ceux qui manquent.

> [English version (Version anglaise)](README.md)

## Principe

1. Le script interroge l'**API Canvas** (token requis) pour lister l'arborescence complète d'un cours :
   dossiers + fichiers (nom, taille, URL de téléchargement).
2. Il **indexe les fichiers locaux** du dossier du cours (correspondance par nom de fichier,
   insensible à la casse, peu importe le sous-dossier — pratique si tu réorganises tes fichiers).
3. Il compare :
   - nom trouvé + même taille → **OK**
   - nom trouvé + taille différente → **avertissement** (copie locale possiblement obsolète)
   - nom introuvable → **téléchargement automatique** dans `Canvas/` (miroir de l'arborescence Canvas)
4. Rapport final : nombre de fichiers OK / différents / téléchargés.

## Prérequis

- Python 3.8+ (testé avec 3.14)
- Un token d'API Canvas (voir ci-dessous)
- Être inscrit·e au cours (le token doit avoir accès au cours)

## Obtenir un token Canvas

1. Connecte-toi sur <https://unissvalbard.instructure.com>
2. **Account** (en haut à gauche) → **Settings**
3. Section **Approved Integrations** → **New Access Token**
4. Donne un nom (ex. `file-checker`) et une date d'expiration, puis copie le token (il n'est affiché qu'une fois).

## Configuration

Le script se configure en tête de fichier (`check_canvas_files.py`) :

```python
BASE_URL  = "https://unissvalbard.instructure.com"
COURSE_ID = 652                            # id du cours dans l'URL Canvas
COURSE_DIR = "1) AT-334 - ..."             # dossier local du cours
MIRROR_DIR = "Canvas"                      # dossier miroir des fichiers téléchargés
```

⚠️ L'id du cours est le nombre dans l'URL : `https://unissvalbard.instructure.com/courses/<ID>/files`.

## Utilisation

Le token se passe par variable d'environnement (jamais dans le code !) :

```sh
export CANVAS_TOKEN='<ton token>'
```

Essai sans rien télécharger (recommandé en premier) :

```sh
python3 check_canvas_files.py --dry-run
```

Vérification + téléchargement des fichiers manquants :

```sh
python3 check_canvas_files.py
```

Les fichiers manquants sont téléchargés dans `<dossier du cours>/Canvas/<chemin Canvas>/<fichier>`
(conserve l'arborescence du cours, réutilisable dans une autre session).

## Sécurité

- Ne committe **jamais** le token : il se passe uniquement par `CANVAS_TOKEN`, jamais stocké dans
  le dépôt ni dans l'historique git.

## Fichiers

- `check_canvas_files.py` — le script
- `README.md` — version anglaise
- `README.fr.md` — ce document