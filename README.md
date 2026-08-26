# Canvas File Checker

Python script (standard library only — no `pip install` needed) that checks that every file of a
Canvas course (<https://unissvalbard.instructure.com>) is present locally, and automatically
downloads whatever is missing.

> [Version française (French version)](README.fr.md)

## How it works

1. The script queries the **Canvas API** (token required) to list the full tree of a course:
   folders + files (name, size, download URL).
2. It **indexes the local files** of the course folder (matching by file name,
   case-insensitive, regardless of the subfolder — handy if you reorganize your files).
3. It compares:
   - name found + same size → **OK**
   - name found + different size → **warning** (the local copy may be outdated)
   - name not found → **automatic download** into `Canvas/` (a mirror of the Canvas tree)
4. Final report: number of files OK / different / downloaded.

## Prerequisites

- Python 3.8+ (tested with 3.14)
- A Canvas API token (see below)
- Enrollment in the course (the token must have access to it)

## Getting a Canvas token

1. Log in at <https://unissvalbard.instructure.com>
2. **Account** (top left) → **Settings**
3. In the **Approved Integrations** section → **New Access Token**
4. Give it a name (e.g. `file-checker`) and an expiration date, then copy the token (it is only
   shown once).

## Setup

1. **Place the checkout at the root of your local course folder** — the script resolves the course
   folder automatically as the *parent* of the checkout. No course name, no path to configure:

   ```
   Documents/
   └── <My course>/
       ├── canvas-file-checker/   ← the git clone
       ├── Lecture 1.pdf
       └── ...
   ```

   ```sh
   cd "<My course>"
   git clone https://github.com/EmmaTF/check_canva_files.git canvas-file-checker
   ```

2. **Set the course id** at the top of `check_canvas_files.py`:

   ```python
   BASE_URL  = "https://unissvalbard.instructure.com"
   COURSE_ID = 652     # course id from the Canvas URL
   ```

   ⚠️ The course id is the number in the URL: `https://unissvalbard.instructure.com/courses/<ID>/files`.

If the checkout is *not* at the root of a course folder, the script stops with an error telling you
exactly which folder it looked for.

## Usage

The token is passed through an environment variable (never in the code!):

**macOS / Linux:**

```sh
export CANVAS_TOKEN='<your token>'
```

**Windows — Command Prompt:**

```bat
set CANVAS_TOKEN=<your token>
```

**Windows — PowerShell:**

```powershell
$env:CANVAS_TOKEN="<your token>"
```

Try it without downloading anything (recommended first):

```sh
python3 check_canvas_files.py --dry-run    # macOS/Linux
py -3 check_canvas_files.py --dry-run      # Windows
```

Check + download the missing files:

```sh
python3 check_canvas_files.py
```

Missing files are downloaded to `<course folder>/Canvas/<canvas path>/<file>` (the course tree is
preserved, ready to be reused in another session).

## Platforms

**macOS / Linux**
- Python 3.8+ (`python3 --version`); install with Homebrew or your package manager if missing.
- Run with `python3 check_canvas_files.py`.
- To keep the token, add `export CANVAS_TOKEN='...'` to `~/.zshrc` (macOS) or `~/.bashrc` (Linux).

**Windows**
- Install Python from <https://www.python.org/downloads/> and tick **Add python.exe to PATH**.
- Run with `py -3 check_canvas_files.py` (or `python check_canvas_files.py`).
- To keep the token, add `set CANVAS_TOKEN=...` to your Command Prompt profile or
  `$env:CANVAS_TOKEN="..."` to your PowerShell profile.
- On Windows, characters forbidden in file names (`: ? * ...`, trailing dots/spaces) are replaced
  with `_` when downloading; file names on macOS/Linux are never altered.

## Updating

If you cloned with git, run `git pull` inside each checkout to get the latest version. If you have
several course folders, clone the repository once per course folder.

## Security

- **Never commit the token**: it is only passed via `CANVAS_TOKEN`, never stored in the repository
  or in git history.

## Files

- `check_canvas_files.py` — the script
- `README.md` — this document
- `README.fr.md` — French version of this document