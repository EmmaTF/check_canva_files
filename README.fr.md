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

## Installation

1. **Place le checkout à la racine de ton dossier de cours local** — le script résout le dossier du
   cours automatiquement comme le *parent* du checkout. Aucun nom de cours ni chemin à configurer :

   ```
   Documents/
   └── <Mon cours>/
       ├── canvas-file-checker/   ← le clone git
       ├── Lecture 1.pdf
       └── ...
   ```

   ```sh
   cd "<Mon cours>"
   git clone https://github.com/EmmaTF/check_canva_files.git canvas-file-checker
   ```

2. **Règle l'id du cours** en tête de `check_canvas_files.py` :

   ```python
   BASE_URL  = "https://unissvalbard.instructure.com"
   COURSE_ID = 652     # id du cours dans l'URL Canvas
   ```

   ⚠️ L'id du cours est le nombre dans l'URL : `https://unissvalbard.instructure.com/courses/<ID>/files`.

Si le checkout n'est *pas* à la racine d'un dossier de cours, le script s'arrête avec une erreur
indiquant exactement le dossier qu'il cherchait.

## Utilisation

Le token se passe par variable d'environnement (jamais dans le code !) :

**macOS / Linux :**

```sh
export CANVAS_TOKEN='<ton token>'
```

**Windows — Invite de commandes :**

```bat
set CANVAS_TOKEN=<ton token>
```

**Windows — PowerShell :**

```powershell
$env:CANVAS_TOKEN="<ton token>"
```

Essai sans rien télécharger (recommandé en premier) :

```sh
python3 check_canvas_files.py --dry-run    # macOS/Linux
py -3 check_canvas_files.py --dry-run      # Windows
```

Vérification + téléchargement des fichiers manquants :

```sh
python3 check_canvas_files.py
```

Les fichiers manquants sont téléchargés dans `<dossier du cours>/Canvas/<chemin Canvas>/<fichier>`
(conserve l'arborescence du cours, réutilisable dans une autre session).

## Plateformes

**macOS / Linux**
- Python 3.8+ (`python3 --version`) ; installe-le avec Homebrew ou ton gestionnaire de paquets s'il manque.
- Lancement : `python3 check_canvas_files.py`.
- Pour conserver le token, ajoute `export CANVAS_TOKEN='...'` dans `~/.zshrc` (macOS) ou `~/.bashrc` (Linux).

**Windows**
- Installe Python depuis <https://www.python.org/downloads/> et coche **Add python.exe to PATH**.
- Lancement : `py -3 check_canvas_files.py` (ou `python check_canvas_files.py`).
- Pour conserver le token, ajoute `set CANVAS_TOKEN=...` au profil de l'invite de commandes ou
  `$env:CANVAS_TOKEN="..."` au profil PowerShell.
- Sur Windows, les caractères interdits dans les noms de fichiers (`: ? * ...`, espaces/traits finaux)
  sont remplacés par `_` au téléchargement ; les noms de fichiers sur macOS/Linux ne sont jamais modifiés.

## Mises à jour

Si tu as cloné avec git, lance `git pull` dans chaque checkout pour récupérer la dernière version.
Si tu as plusieurs dossiers de cours, clone le dépôt une fois par dossier de cours.

## Sécurité

- Ne committe **jamais** le token : il se passe uniquement par `CANVAS_TOKEN`, jamais stocké dans
  le dépôt ni dans l'historique git.

## Fichiers

- `check_canvas_files.py` — le script
- `README.md` — version anglaise
- `README.fr.md` — ce document