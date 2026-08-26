#!/usr/bin/env python3
"""Check that all files of a Canvas course exist locally and download missing ones.

Uses the Canvas REST API (https://unissvalbard.instructure.com) with a token
provided through the CANVAS_TOKEN environment variable. Requires only the
Python standard library — no pip install needed.

The configuration constants at the top of this file (BASE_URL, COURSE_ID,
COURSE_DIR, ...) must be adapted before first use. See README.md for details.
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = "https://unissvalbard.instructure.com"
COURSE_ID = 652
COURSE_DIR = "1) AT-334 - Arctic Marine Measurements Techniques, Operations and Transport"
MIRROR_DIR = "Canvas"
PER_PAGE = 100
SKIP_NAMES = {".DS_Store"}


def next_link(link_header):
    """Extract the URL of the next page from a Link header (RFC 5988).

    Canvas paginates API responses and signals the next page through a
    'Link' response header. Returns None when there is no next page.
    """
    if not link_header:
        return None
    for part in link_header.split(","):
        url, _, rel = part.partition(";")
        if 'rel="next"' in rel:
            return url.strip(" <>")
    return None


def api_get(path):
    """GET a paginated Canvas API endpoint and return the full list of items.

    Follows 'next' links until every page has been fetched. Fails with a
    clear message on missing/invalid token (HTTP 401) or network errors.
    """
    token = os.environ.get("CANVAS_TOKEN")
    if not token:
        sys.exit("Token manquant : export CANVAS_TOKEN=<ton token> (Canvas → Account → Settings → New Access Token)")
    items = []
    url = f"{BASE_URL}{path}" + ("&" if "?" in path else "?") + f"per_page={PER_PAGE}"
    while url:
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/json")
        try:
            resp = urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                sys.exit("Accès refusé (401) : token invalide ou expiré.")
            sys.exit(f"Erreur API {e.code} sur {url} : {e.read().decode()[:300]}")
        except urllib.error.URLError as e:
            sys.exit(f"Erreur réseau sur {url} : {e.reason}")
        body = json.loads(resp.read().decode())
        items.extend(body)
        url = next_link(resp.headers.get("Link"))
        resp.close()
    return items


def local_index(root):
    """Walk root recursively and index local files by lowercased name.

    Returns {name_lower: [(path, size), ...]}. Names are matched
    case-insensitively so a local copy counts regardless of its
    subfolder — the user may reorganize files freely.
    """
    index = {}
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden directories (.git, .ipynb_checkpoints, ...)
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if name in SKIP_NAMES:
                continue
            path = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            index.setdefault(name.lower(), []).append((path, size))
    return index


def download(url, dest_path, expected_size):
    """Download url to dest_path and verify its size.

    Writes to a temporary '.part' file first, then atomically renames it,
    so a failed download never leaves a partial file behind. Returns an
    error message on failure, or None on success.
    """
    token = os.environ.get("CANVAS_TOKEN")
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    tmp = dest_path + ".part"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    try:
        resp = urllib.request.urlopen(req, timeout=300)
    except urllib.error.HTTPError as e:
        return f"erreur HTTP {e.code}"
    except urllib.error.URLError as e:
        return f"erreur réseau : {e.reason}"
    with open(tmp, "wb") as fh:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            fh.write(chunk)
    resp.close()
    size = os.path.getsize(tmp)
    if expected_size is not None and size != expected_size:
        os.remove(tmp)
        return f"taille inattendue ({size} o ≠ {expected_size} o)"
    os.replace(tmp, dest_path)
    return None


def mirror_path(folder_id, folders, display_name):
    """Return the local mirror destination for a Canvas file.

    Format: COURSE_DIR/MIRROR_DIR/<canvas folder path>/<file name>.
    The root folder of the course ('course files') is stripped so the
    mirror starts right at the course's top-level folders.
    """
    full_name = folders.get(folder_id, "course files")
    parts = full_name.split("/")
    if len(parts) > 1 and parts[0].lower() in ("course files", "files"):
        parts = parts[1:]
    return os.path.join(COURSE_DIR, MIRROR_DIR, *parts, display_name)


def main():
    """CLI entry point: fetch the Canvas tree, compare with local files and
    download whatever is missing (or just report with --dry-run)."""
    dry_run = "--dry-run" in sys.argv
    if not os.path.isdir(COURSE_DIR):
        sys.exit(f"Dossier local introuvable : {COURSE_DIR}")
    if not os.environ.get("CANVAS_TOKEN"):
        sys.exit("Token manquant : export CANVAS_TOKEN=<ton token> (Canvas → Account → Settings → New Access Token)")

    print(f"Récupération de l'arborescence Canvas du cours {COURSE_ID}…")
    folders = {f["id"]: f["full_name"] for f in api_get(f"/api/v1/courses/{COURSE_ID}/folders")}
    files = api_get(f"/api/v1/courses/{COURSE_ID}/files")
    print(f"{len(files)} fichiers et {len(folders)} dossiers sur Canvas.")

    print("Indexation des fichiers locaux…")
    index = local_index(COURSE_DIR)

    ok = warn = missing = failed = 0
    # Group Canvas files by lowercased name to report duplicates
    by_name = {}
    for f in files:
        by_name.setdefault(f["display_name"].lower(), []).append(f)

    print()
    for f in files:
        name_lower = f["display_name"].lower()
        size = f.get("size")
        candidates = index.get(name_lower, [])
        if candidates:
            # Found locally: OK if a copy has the same size, warn otherwise
            if any(s == size for _, s in candidates):
                ok += 1
                continue
            warn += 1
            print(f"[!] Taille différente : {f['display_name']} (Canvas {size} o)")
            for path, s in candidates:
                print(f"      local : {path} ({s} o)")
            continue
        # Not found locally: download it into the mirror folder
        missing += 1
        dest = mirror_path(f.get("folder_id"), folders, f["display_name"])
        if dry_run:
            print(f"[+] Manquant (--dry-run, pas de téléchargement) : {f['display_name']}")
            continue
        err = download(f["url"], dest, size)
        if err:
            failed += 1
            print(f"[X] Échec de téléchargement : {f['display_name']} → {err}")
        else:
            print(f"[+] Téléchargé : {dest}")

    dupes = {k: v for k, v in by_name.items() if len(v) > 1}
    if dupes:
        print()
        print("Noms en doublon sur Canvas (chemins complets) :")
        for dup in sorted(dupes.values()):
            for d in dup:
                print(f"      {d['display_name']!r} → {mirror_path(d.get('folder_id'), folders, d['display_name'])}")

    print()
    print(f"Résumé : {ok} OK, {warn} taille différente, {missing} manquant(s)"
          + (", " + f"{failed} échec(s)" if failed else "")
          + (" (dry-run)" if dry_run else ""))
    sys.exit(1 if failed or warn else 0)


if __name__ == "__main__":
    main()