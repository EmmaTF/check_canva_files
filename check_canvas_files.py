#!/usr/bin/env python3
"""Check that all files of a Canvas course exist locally and download missing ones.

Uses the Canvas REST API (https://unissvalbard.instructure.com) with a token
provided through the CANVAS_TOKEN environment variable. Requires only the
Python standard library — no pip install needed.

The checkout must be placed at the root of the local course folder: the
course folder is resolved automatically as the checkout's parent directory,
so no path or course name has to be configured. Only BASE_URL and COURSE_ID
may need adapting — see README.md for details.

Course files are looked for in every place Canvas can hide them: the Files
area, the module items, and the pages of the course.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

BASE_URL = "https://unissvalbard.instructure.com"
COURSE_ID = 656
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COURSE_DIR = os.path.dirname(SCRIPT_DIR)
REPO_DIRNAME = os.path.basename(SCRIPT_DIR)
MIRROR_DIR = "Canvas"
PER_PAGE = 100
SKIP_NAMES = {".DS_Store"}
# Matches /courses/123/files/456, /files/456 and every suffix (/download, /preview)
FILE_URL_RE = re.compile(r"/(?:courses/(?:\d+/)?)?files/(\d+)")


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


def api_get(path, soft=False):
    """GET a paginated Canvas API endpoint and return the full list of items.

    Follows 'next' links until every page has been fetched. Fails with a
    clear message on missing/invalid token (HTTP 401) or network errors.
    With soft=True, an HTTP 403/404 returns None instead of stopping:
    Canvas may refuse one area of a course (e.g. /files) while the
    modules and the pages stay readable.
    """
    token = os.environ.get("CANVAS_TOKEN")
    if not token:
        sys.exit("Missing token: export CANVAS_TOKEN='<your token>' "
                 "(Canvas → Account → Settings → New Access Token)")
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
                sys.exit("Access denied (401): invalid or expired token.")
            if soft and e.code in (403, 404):
                return None
            sys.exit(f"API error {e.code} on {url}: {e.read().decode()[:300]}")
        except urllib.error.URLError as e:
            sys.exit(f"Network error on {url}: {e.reason}")
        body = json.loads(resp.read().decode())
        items.extend(body)
        url = next_link(resp.headers.get("Link"))
        resp.close()
    return items


def api_get_one(url, soft=False):
    """GET a single Canvas API object (not a list) and return it.

    Module items and pages point at the files they reference through a
    URL; this fetches such an object to get its real name, size and
    download URL. The url may be absolute or relative to BASE_URL. With
    soft=True, an HTTP 403/404 returns None.
    """
    token = os.environ.get("CANVAS_TOKEN")
    if not url.startswith("http"):
        url = f"{BASE_URL}{url}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            sys.exit("Access denied (401): invalid or expired token.")
        if soft and e.code in (403, 404):
            return None
        sys.exit(f"API error {e.code} on {url}: {e.read().decode()[:300]}")
    except urllib.error.URLError as e:
        sys.exit(f"Network error on {url}: {e.reason}")
    obj = json.loads(resp.read().decode())
    resp.close()
    return obj


def download_url(file_id):
    """Return the endpoint that serves the content of a course file."""
    return f"{BASE_URL}/courses/{COURSE_ID}/files/{file_id}/download"


class FileLinkParser(HTMLParser):
    """Collect the links of a page body that point at a Canvas file.

    A page body references its attachments with <a href> tags such as
    /courses/656/files/123/download. The link text is kept as a fallback
    name for when Canvas refuses to give the file metadata.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag != "a" or not self._href:
            return
        match = FILE_URL_RE.search(self._href)
        if match:
            label = " ".join("".join(self._text).split())
            self.links.append((int(match.group(1)), label))
        self._href = None
        self._text = []


def make_file(file_id, name, parts, size=None):
    """Build a Canvas file object from what is known about a file.

    Used when Canvas refuses to hand over the file metadata: the id is
    enough to download the content, and the size stays None so the
    download is not size-checked.
    """
    if not name:
        return None
    return {
        "id": file_id,
        "display_name": name,
        "size": size,
        "url": download_url(file_id),
        "folder_id": None,
        "_parts": parts,
    }


def file_from_id(file_id, fallback_name, parts):
    """Return the Canvas file object for a file id.

    Tries the API metadata first (real name, size, folder) and falls back
    to the given name when Canvas answers 403/404.
    """
    meta = api_get_one(f"/api/v1/courses/{COURSE_ID}/files/{file_id}", soft=True)
    if meta and meta.get("display_name"):
        meta = dict(meta)
        meta.setdefault("url", download_url(file_id))
        meta["_parts"] = parts
        return meta
    return make_file(file_id, fallback_name, parts)


def page_api_url(item):
    """Return the API URL of the page a module item points at, or None."""
    if "/api/v1/" in (item.get("url") or ""):
        return item["url"]
    page_url = item.get("page_url") or ""
    slug = page_url.rstrip("/").rsplit("/", 1)[-1]
    if not slug:
        return None
    return f"/api/v1/courses/{COURSE_ID}/pages/{urllib.parse.quote(slug)}"


def page_files(item, parts):
    """Return the files attached to the body of a Canvas page.

    Courses that keep everything in modules and pages often hide their
    material inside the page bodies, so the page HTML is parsed for file
    links. Returns (files, unreadable): unreadable is True when the page
    itself could not be fetched.
    """
    url = page_api_url(item)
    if not url:
        return [], True
    page = api_get_one(url, soft=True)
    if not page:
        return [], True
    parser = FileLinkParser()
    parser.feed(page.get("body") or "")
    parser.close()
    files = []
    for file_id, label in parser.links:
        file = file_from_id(file_id, label or f"file-{file_id}", parts)
        if file:
            files.append(file)
    return files, False


def module_files():
    """List every file the course modules lead to.

    Canvas exposes course files in three different places: the Files area,
    the module items of type 'File', and the pages of the course, whose
    bodies link to their attachments. A module can therefore hold no file
    item at all and still be where the course material lives.

    Returns (files, stats, denied): files is a list of Canvas file
    objects deduplicated by id, stats counts what was inspected, and
    denied is True when Canvas refused the modules listing itself.
    """
    files = []
    stats = {"items": 0, "file_items": 0, "pages": 0, "unreadable_pages": 0,
             "page_files": 0, "other_items": 0}
    seen = set()

    def add(file):
        if file and file.get("id") not in seen:
            seen.add(file["id"])
            files.append(file)

    modules = api_get(f"/api/v1/courses/{COURSE_ID}/modules", soft=True)
    if modules is None:
        return files, stats, True
    for module in modules:
        if module.get("workflow_state") == "unpublished":
            continue
        module_name = module.get("name") or "module"
        items = api_get(f"/api/v1/courses/{COURSE_ID}/modules/{module['id']}/items", soft=True) or []
        # Module items can be nested one level deep (sub_items)
        stack = list(items)
        while stack:
            item = stack.pop(0)
            stack = list(item.get("sub_items") or []) + stack
            stats["items"] += 1
            if item.get("type") == "File":
                stats["file_items"] += 1
                add(file_from_id(item.get("file_id") or item.get("content_id"),
                                 item.get("title"), [module_name]))
            elif item.get("type") == "Page":
                stats["pages"] += 1
                label = item.get("title") or "page"
                parts = [module_name] if label.lower() == module_name.lower() else [module_name, label]
                found, unreadable = page_files(item, parts)
                stats["unreadable_pages"] += int(unreadable)
                stats["page_files"] += len(found)
                for file in found:
                    add(file)
            else:
                stats["other_items"] += 1
    return files, stats, False


def local_index(root):
    """Walk root recursively and index local files by lowercased name.

    Returns {name_lower: [(path, size), ...]}. Names are matched
    case-insensitively so a local copy counts regardless of its
    subfolder — the user may reorganize files freely. The checkout
    itself and hidden directories (.git, .ipynb_checkpoints, ...) are
    skipped so the script never compares against its own files.
    """
    index = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if not d.startswith(".") and d != REPO_DIRNAME]
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
        return f"HTTP error {e.code}"
    except urllib.error.URLError as e:
        return f"network error: {e.reason}"
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
        return f"unexpected size ({size} bytes, expected {expected_size})"
    os.replace(tmp, dest_path)
    return None


def sanitize_component(name):
    """Replace characters that Windows forbids in file names with '_'.

    Applied on Windows only, so file names on macOS/Linux stay untouched.
    """
    if os.name != "nt":
        return name
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, "_")
    name = name.rstrip(" .")
    return name or "_"


def mirror_path(file, folders):
    """Return the local mirror destination for a Canvas file.

    Format: COURSE_DIR/MIRROR_DIR/<canvas folder path>/<file name>. The
    root folder of the course ('course files') is stripped so the mirror
    starts right at the course's top-level folders. A file with no
    usable folder is filed under the module and page it belongs to. Path
    parts are sanitized on Windows (forbidden characters, trailing
    dots/spaces).
    """
    parts = folders.get(file.get("folder_id"), "course files").split("/")
    if parts and parts[0].lower() in ("course files", "files"):
        parts = parts[1:]
    if not parts:
        parts = file.get("_parts") or []
    parts = [sanitize_component(p) for p in parts]
    return os.path.join(COURSE_DIR, MIRROR_DIR, *parts,
                        sanitize_component(file["display_name"]))


def probe(path):
    """Return the HTTP status code of an API endpoint, for --check.

    Never raises: the point of --check is to report what Canvas allows,
    including the endpoints that answer 403.
    """
    token = os.environ.get("CANVAS_TOKEN")
    req = urllib.request.Request(f"{BASE_URL}{path}")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        status = resp.status
        resp.close()
        return status
    except urllib.error.HTTPError as e:
        return e.code
    except urllib.error.URLError as e:
        return f"network error: {e.reason}"


def check_access():
    """Report which parts of the course the current token can read."""
    print(f"Checking access to course {COURSE_ID}…")
    endpoints = [
        ("course", f"/api/v1/courses/{COURSE_ID}"),
        ("folders", f"/api/v1/courses/{COURSE_ID}/folders"),
        ("Files tab", f"/api/v1/courses/{COURSE_ID}/files"),
        ("modules", f"/api/v1/courses/{COURSE_ID}/modules"),
    ]
    codes = {}
    for label, path in endpoints:
        status = probe(path)
        codes[label] = status
        print(f"  {label:<12} {status}")

    print()
    if any(c == 401 for c in codes.values()):
        print("401: invalid or expired token. Create a new one "
              "(Account → Settings → New Access Token).")
    elif any(c == 403 for c in codes.values()):
        refused = ", ".join(k for k, c in codes.items() if c == 403)
        print(f"403 on: {refused}.")
        print("Canvas denies that part of the course to this token. Most likely:\n"
              "  - the token was created before you enrolled in the course\n"
              "  - the token was created with limited rights\n"
              "The script carries on with what is readable (often the modules and pages).")
    else:
        print("Access is fine. Run the script to sync the files.")


def main():
    """CLI entry point: fetch the course files, compare with the local ones
    and download whatever is missing (or just report with --dry-run)."""
    dry_run = "--dry-run" in sys.argv
    if not os.path.isdir(COURSE_DIR):
        sys.exit(
            f"Local course folder not found: {COURSE_DIR}\n"
            "The checkout must be placed at the root of the local course folder\n"
            "(e.g. Documents/<My course>/canvas-file-checker/). See README.md."
        )
    if not os.environ.get("CANVAS_TOKEN"):
        sys.exit("Missing token: export CANVAS_TOKEN='<your token>' "
                 "(Canvas → Account → Settings → New Access Token)")
    if "--check" in sys.argv:
        check_access()
        return

    print(f"Fetching the Canvas tree of course {COURSE_ID}…")
    folder_list = api_get(f"/api/v1/courses/{COURSE_ID}/folders", soft=True) or []
    folders = {f["id"]: f["full_name"] for f in folder_list}

    files = api_get(f"/api/v1/courses/{COURSE_ID}/files", soft=True)
    if files is None:
        print("Files tab not readable (403) for this token — continuing with the modules.")
        files = []
    else:
        print(f"{len(files)} files and {len(folders)} folders in the Files tab.")

    # The modules and their pages hold files that /files does not list
    mod_files, stats, denied = module_files()
    known = {f.get("id") for f in files}
    added = [f for f in mod_files if f.get("id") not in known]
    files.extend(added)
    if denied:
        print("Modules not readable (403) for this token.")
    else:
        print(f"Modules: {stats['items']} items "
              f"({stats['file_items']} file, {stats['pages']} page, "
              f"{stats['other_items']} other) → {len(added)} new file(s).")
        if stats["pages"]:
            print(f"Pages: {stats['page_files']} attachment(s) found"
                  + (f", {stats['unreadable_pages']} page(s) unreadable"
                     if stats["unreadable_pages"] else "")
                  + ".")

    if not files:
        sys.exit(
            "No readable file: neither the Files tab nor the modules answered.\n"
            f"Check that the token can read course {COURSE_ID}:\n"
            "  - you are enrolled in that course on unissvalbard.instructure.com\n"
            "  - the token exists (Account → Settings → New Access Token) and has not expired\n"
            "  - COURSE_ID in the script matches the course URL"
        )

    print("Indexing local files…")
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
            # Size unknown (Canvas hid the metadata): the local name match is enough
            if size is None:
                ok += 1
                continue
            # Found locally: OK if a copy has the same size, warn otherwise
            if any(s == size for _, s in candidates):
                ok += 1
                continue
            warn += 1
            print(f"[!] Size mismatch: {f['display_name']} (Canvas {size} bytes)")
            for path, s in candidates:
                print(f"      local: {path} ({s} bytes)")
            continue
        # Not found locally: download it into the mirror folder
        missing += 1
        dest = mirror_path(f, folders)
        if dry_run:
            print(f"[+] Missing (--dry-run, nothing downloaded): {f['display_name']}")
            continue
        err = download(f["url"], dest, size)
        if err:
            failed += 1
            print(f"[X] Download failed: {f['display_name']} → {err}")
        else:
            print(f"[+] Downloaded: {dest}")

    dupes = {k: v for k, v in by_name.items() if len(v) > 1}
    if dupes:
        print()
        print("Duplicate names on Canvas (full paths):")
        for dup in sorted(dupes.values()):
            for d in dup:
                print(f"      {d['display_name']!r} → {mirror_path(d, folders)}")

    print()
    print(f"Summary: {ok} OK, {warn} size mismatch, {missing} missing"
          + (f", {failed} failed" if failed else "")
          + (" (dry-run)" if dry_run else ""))
    sys.exit(1 if failed or warn else 0)


if __name__ == "__main__":
    main()
