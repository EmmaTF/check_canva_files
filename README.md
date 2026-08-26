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

## Configuration

Configure the script at the top of `check_canvas_files.py`:

```python
BASE_URL  = "https://unissvalbard.instructure.com"
COURSE_ID = 652                            # course id from the Canvas URL
COURSE_DIR = "1) AT-334 - ..."             # local folder of the course
MIRROR_DIR = "Canvas"                      # mirror folder for downloaded files
```

⚠️ The course id is the number in the URL: `https://unissvalbard.instructure.com/courses/<ID>/files`.

## Usage

The token is passed through an environment variable (never in the code!):

```sh
export CANVAS_TOKEN='<your token>'
```

Try it without downloading anything (recommended first):

```sh
python3 check_canvas_files.py --dry-run
```

Check + download the missing files:

```sh
python3 check_canvas_files.py
```

Missing files are downloaded to `<course folder>/Canvas/<canvas path>/<file>` (the course tree is
preserved, ready to be reused in another session).

## Security

- **Never commit the token**: it is only passed via `CANVAS_TOKEN`, never stored in the repository
  or in git history.

## Files

- `check_canvas_files.py` — the script
- `README.md` — this document
- `README.fr.md` — French version of this document