#!/usr/bin/env python3
"""Create a deployment zip for Cast Hub (zip deploy, no Docker).

Builds pw46 worklist + reporting, syncs production builds from sibling repos into
cast_hub client folders, then packages everything under cast_hub/:

- volview-client/  <- VolView/dist  (served at /volview-client/)
- worklist-client/  <- pw46/worklist (built static; /worklist-client/)
- reporting-client/  <- pw46/reporting (built static; /reporting-client/)
- slicerlive/  <- pw46/SlicerLive/render/demos/ira (IRA; /slicerlive/)
- slim/  <- slim/build  (/slim/)
- OHIF-client/  <- Viewers/platform/app/dist  (/ohif/; sync only — build OHIF separately)

Run from any directory:
    python cast_hub/make_zip.py

Optional:
    python cast_hub/make_zip.py --output cast-hub.zip
    python cast_hub/make_zip.py --skip-build
    python cast_hub/make_zip.py --skip-sync

pw46 worklist / reporting: npm run build (run automatically unless --skip-build)
SlicerLive IRA: syncs prebuilt ira.js (+ idc-worker.js); build IRA separately if needed

OHIF: not built by this script; syncs existing Viewers/platform/app/dist when present
    (yarn build:cast-hub with PUBLIC_URL=/ohif/, APP_CONFIG=config/cast.js)

Slim for hub: pnpm run build:cast
    (PUBLIC_URL=/slim/, REACT_APP_CONFIG=cast, config file public/config/cast.js)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "tools",
    ".egg-info",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".ts", ".map"}
EXCLUDED_FILE_NAMES = {
    ".DS_Store",
    "cast-hub.zip",
    "package.json",
    "package-lock.json",
    ".gitignore",
    "LICENSE",
    # Local monorepo editable pin — Azure zip uses requirements-azure.txt instead.
    "requirements.txt",
}
EXCLUDED_DOC_SUFFIXES = {".md"}
# Written into the zip as requirements.txt (no -e ../cast_py_client).
AZURE_REQUIREMENTS_NAME = "requirements-azure.txt"

# (dest folder under cast_hub, CLI dest name for --*-dist override key)
CLIENT_SYNC_SPECS = (
    ("volview-client", "volview"),
    ("worklist-client", "worklist"),
    ("reporting-client", "reporting"),
    ("slicerlive", "slicerlive"),
    ("hub-mirror", "hubmirror"),
    ("slim", "slim"),
    ("OHIF-client", "ohif"),
)

# URL mount path in cast_hub.py (may differ from folder name)
MOUNT_PATH_BY_DEST = {
    "volview-client": "/volview-client/",
    "worklist-client": "/worklist-client/",
    "reporting-client": "/reporting-client/",
    "slicerlive": "/slicerlive/",
    "hub-mirror": "/hub-mirror/",
    "slim": "/slim/",
    "OHIF-client": "/ohif/",
}

# Repo folder names and dist paths under each repo (workspace layout).
REPO_NAMES = {
    "volview": "VolView",
    "worklist": "worklist",
    "reporting": "reporting",
    "slicerlive": "SlicerLive",
    "hubmirror": "SlicerLive",
    "slim": "slim",
    "ohif": "Viewers",
}
DIST_PARTS_UNDER_REPO = {
    "volview": ("dist",),
    "worklist": (),  # flat static tree (index.html + worklist.js + …)
    "reporting": (),
    "slicerlive": ("render", "demos", "ira"),
    "hubmirror": ("render", "demos", "hub-mirror"),
    "slim": ("build",),
    "ohif": ("platform", "app", "dist"),
}
# Keys that live under pw46/ rather than as a top-level sibling.
PW46_CLIENT_KEYS = frozenset({"worklist", "reporting", "slicerlive", "hubmirror"})

# Keys we build with ``npm run build`` before sync (pw46 flat static clients).
NPM_BUILD_KEYS = ("worklist", "reporting")

# Static files to ship for the IRA demo (ira.html is also written as index.html).
SLICERLIVE_IRA_FILES = ("ira.html", "ira.js", "idc-worker.js")
# hub-mirror LiveScene stream client (hub-mirror.html → index.html).
HUB_MIRROR_FILES = ("hub-mirror.html", "hub-mirror.js")


def find_repo_root(script_dir: Path, key: str) -> Path | None:
    """Locate client repos from cast_hub upward (workspace roots)."""
    repo_name = REPO_NAMES[key]
    for base in (script_dir, *script_dir.parents):
        if key == "slicerlive":
            for candidate in (base / "pw46" / "SlicerLive", base / "SlicerLive"):
                ira = candidate / "render" / "demos" / "ira" / "ira.html"
                if ira.is_file():
                    return candidate.resolve()
            continue
        if key == "hubmirror":
            for candidate in (base / "pw46" / "SlicerLive", base / "SlicerLive"):
                hm = candidate / "render" / "demos" / "hub-mirror" / "hub-mirror.html"
                if hm.is_file():
                    return candidate.resolve()
            continue
        if key in PW46_CLIENT_KEYS:
            under_pw46 = base / "pw46" / repo_name
            if under_pw46.is_dir() and (under_pw46 / "package.json").is_file():
                return under_pw46.resolve()
            direct = base / repo_name
            if (
                direct.is_dir()
                and (direct / "package.json").is_file()
                and (direct / "index.html").is_file()
            ):
                return direct.resolve()
            continue
        if key == "slim":
            direct = base / "slim"
            if direct.is_dir() and (direct / "package.json").is_file():
                return direct.resolve()
            continue
        under_pw = base / "ProjectWeek45" / repo_name
        if under_pw.is_dir():
            return under_pw.resolve()
        # cast-interface monorepo Viewers/
        if key == "ohif":
            under_ci = base / "cast-interface" / "Viewers"
            if under_ci.is_dir():
                return under_ci.resolve()
        direct = base / repo_name
        if direct.is_dir():
            return direct.resolve()
    return None


def default_dist_path(script_dir: Path, key: str) -> Path:
    repo_name = REPO_NAMES[key]
    repo_root = find_repo_root(script_dir, key)
    if repo_root is None:
        raise FileNotFoundError(
            f"Could not find {repo_name} repo in workspace "
            f"(searched from {script_dir})"
        )
    parts = DIST_PARTS_UNDER_REPO[key]
    return (repo_root / Path(*parts)).resolve() if parts else repo_root.resolve()


def should_include(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDED_DIR_NAMES:
        return False
    if any(part.endswith(".egg-info") for part in path.parts):
        return False
    if path.name in EXCLUDED_FILE_NAMES:
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if path.suffix.lower() in EXCLUDED_DOC_SUFFIXES:
        return False
    return True


def sync_dist_tree(src: Path, dest: Path) -> int:
    """Replace dest with a copy of src; require src/index.html. Returns file count."""
    index = src / "index.html"
    if not src.is_dir():
        raise FileNotFoundError(f"Source dist not found: {src}")
    if not index.is_file():
        raise FileNotFoundError(f"Source dist missing index.html: {index}")

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    file_count = 0
    for file_path in src.rglob("*"):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(src)
        if not should_include(rel):
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, target)
        file_count += 1
    return file_count


def sync_slicerlive_ira(src: Path, dest: Path) -> int:
    """Copy IRA demo static files; write ira.html as index.html for hub SPA mount."""
    if not src.is_dir():
        raise FileNotFoundError(f"Source dist not found: {src}")
    ira_html = src / "ira.html"
    ira_js = src / "ira.js"
    if not ira_html.is_file():
        raise FileNotFoundError(f"SlicerLive IRA missing ira.html: {ira_html}")
    if not ira_js.is_file():
        raise FileNotFoundError(
            f"SlicerLive IRA missing ira.js (build the demo first): {ira_js}"
        )

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    shutil.copy2(ira_html, dest / "index.html")
    file_count = 1
    for name in SLICERLIVE_IRA_FILES:
        src_file = src / name
        if not src_file.is_file():
            if name == "idc-worker.js":
                print(
                    f"Warning: {src_file} missing; IDC worker loads may fail",
                    file=sys.stderr,
                )
            continue
        shutil.copy2(src_file, dest / name)
        file_count += 1
    return file_count


def sync_hub_mirror(src: Path, dest: Path) -> int:
    """Copy hub-mirror demo; write hub-mirror.html as index.html for hub SPA mount."""
    if not src.is_dir():
        raise FileNotFoundError(f"Source dist not found: {src}")
    html = src / "hub-mirror.html"
    js = src / "hub-mirror.js"
    if not html.is_file():
        raise FileNotFoundError(f"hub-mirror missing hub-mirror.html: {html}")
    if not js.is_file():
        raise FileNotFoundError(
            f"hub-mirror missing hub-mirror.js (build the demo first): {js}"
        )

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    shutil.copy2(html, dest / "index.html")
    file_count = 1
    for name in HUB_MIRROR_FILES:
        src_file = src / name
        if not src_file.is_file():
            continue
        shutil.copy2(src_file, dest / name)
        file_count += 1
    return file_count


def find_cast_py_client(script_dir: Path) -> Path | None:
    """Locate CastInterface/cast_py_client next to cast_hub."""
    sibling = (script_dir.parent / "cast_py_client").resolve()
    if sibling.is_dir() and (sibling / "src" / "cast_client").is_dir():
        return sibling
    for base in script_dir.parents:
        candidate = base / "CastInterface" / "cast_py_client"
        if candidate.is_dir() and (candidate / "src" / "cast_client").is_dir():
            return candidate.resolve()
    return None


def add_tree_to_zip(
    zf: ZipFile,
    src_root: Path,
    arc_prefix: str,
) -> int:
    """Add files under src_root into the zip under arc_prefix/. Returns file count."""
    count = 0
    for file_path in sorted(src_root.rglob("*")):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(src_root)
        if not should_include(rel):
            continue
        arcname = f"{arc_prefix.rstrip('/')}/{rel.as_posix()}"
        zf.write(file_path, arcname)
        count += 1
    return count


def build_zip(source_dir: Path, output_zip: Path) -> tuple[int, dict[str, int]]:
    file_count = 0
    client_counts: dict[str, int] = {name: 0 for name, _ in CLIENT_SYNC_SPECS}
    azure_req = source_dir / AZURE_REQUIREMENTS_NAME
    with ZipFile(output_zip, "w", ZIP_DEFLATED) as zf:
        # Azure / Oryx expect requirements.txt — ship the azure variant (no editable pin).
        if azure_req.is_file():
            zf.write(azure_req, "requirements.txt")
            file_count += 1
            print(
                f"Packaged {AZURE_REQUIREMENTS_NAME} as requirements.txt "
                "(omitted -e ../cast_py_client)"
            )
        else:
            print(
                f"Warning: {AZURE_REQUIREMENTS_NAME} missing; "
                "zip will not include requirements.txt",
                file=sys.stderr,
            )

        for file_path in sorted(source_dir.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(source_dir)
            if not should_include(rel):
                continue
            # Already written as requirements.txt above.
            if rel.as_posix() == AZURE_REQUIREMENTS_NAME:
                continue
            arcname = rel.as_posix()
            zf.write(file_path, arcname)
            file_count += 1
            for client_name, _ in CLIENT_SYNC_SPECS:
                prefix = f"{client_name}/"
                if arcname.startswith(prefix):
                    client_counts[client_name] += 1
                    break

        py_client = find_cast_py_client(source_dir)
        if py_client is not None:
            n = add_tree_to_zip(zf, py_client, "cast_py_client")
            file_count += n
            print(f"Packaged cast_py_client/ ({n} files) from {py_client}")
            client_counts["cast_py_client"] = n
        else:
            print(
                "Warning: cast_py_client not found; hub may fail to import cast_client",
                file=sys.stderr,
            )

    return file_count, client_counts


def resolve_dist_arg(
    script_dir: Path,
    key: str,
    override: str | None,
) -> Path:
    if override:
        path = Path(override).expanduser()
        if path.is_absolute():
            return path.resolve()
        return (script_dir / path).resolve()
    return default_dist_path(script_dir, key)


def _npm_cmd() -> list[str]:
    """Prefer npm.cmd on Windows so CreateProcess finds it."""
    if os.name == "nt":
        return ["npm.cmd"]
    return ["npm"]


def build_npm_app(repo_root: Path, label: str) -> None:
    """Run ``npm run build`` in ``repo_root``; raise on failure."""
    package_json = repo_root / "package.json"
    if not package_json.is_file():
        raise FileNotFoundError(f"{label}: missing package.json at {repo_root}")
    print(f"Building {label} ({repo_root}) …")
    subprocess.run(
        [*_npm_cmd(), "run", "build"],
        cwd=repo_root,
        check=True,
    )
    print(f"Built {label}")


def build_pw46_clients(script_dir: Path) -> int:
    """Build worklist + reporting. Returns number of apps built; raises on hard fail."""
    built = 0
    for key in NPM_BUILD_KEYS:
        repo = find_repo_root(script_dir, key)
        if repo is None:
            print(
                f"Warning: {key} repo not found; skip npm build",
                file=sys.stderr,
            )
            continue
        try:
            build_npm_app(repo, key)
            built += 1
        except subprocess.CalledProcessError as err:
            raise RuntimeError(
                f"{key} npm run build failed (exit {err.returncode})"
            ) from err
    return built


def build_deploy_clients(script_dir: Path) -> int:
    """Build clients required for the Azure zip (pw46 worklist + reporting)."""
    return build_pw46_clients(script_dir)


def main() -> int:
    script_dir = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description="Sync hub SPA clients and create cast_hub zip deployment package"
    )
    parser.add_argument(
        "--output",
        default=str(script_dir / "cast-hub.zip"),
        help="Output zip path (default: cast_hub/cast-hub.zip)",
    )
    parser.add_argument(
        "--volview-dist",
        default=None,
        help="VolView production dist (default: <VolView>/dist in workspace)",
    )
    parser.add_argument(
        "--worklist-dist",
        default=None,
        help="pw46 worklist static root (default: <pw46>/worklist)",
    )
    parser.add_argument(
        "--reporting-dist",
        default=None,
        help="pw46 reporting static root (default: <pw46>/reporting)",
    )
    parser.add_argument(
        "--ohif-dist",
        default=None,
        help="OHIF viewer dist (default: Viewers/platform/app/dist)",
    )
    parser.add_argument(
        "--slim-dist",
        default=None,
        help="Slim production build (default: slim/build in workspace)",
    )
    parser.add_argument(
        "--slicerlive-dist",
        default=None,
        help="SlicerLive IRA static root (default: <SlicerLive>/render/demos/ira)",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip npm builds for pw46 worklist + reporting",
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="Zip cast_hub as-is without copying dist folders",
    )
    args = parser.parse_args()

    dist_overrides = {
        "volview": args.volview_dist,
        "worklist": args.worklist_dist,
        "reporting": args.reporting_dist,
        "ohif": args.ohif_dist,
        "slim": args.slim_dist,
        "slicerlive": args.slicerlive_dist,
        "hubmirror": None,
    }

    output_zip = Path(args.output).resolve()
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    if not args.skip_sync and not args.skip_build:
        try:
            build_deploy_clients(script_dir)
        except RuntimeError as err:
            print(f"Error: {err}", file=sys.stderr)
            return 1

    if not args.skip_sync:
        for dest_name, key in CLIENT_SYNC_SPECS:
            src = resolve_dist_arg(script_dir, key, dist_overrides.get(key))
            dest = script_dir / dest_name
            try:
                if key == "slicerlive":
                    count = sync_slicerlive_ira(src, dest)
                elif key == "hubmirror":
                    count = sync_hub_mirror(src, dest)
                else:
                    count = sync_dist_tree(src, dest)
                print(f"Synced {src} -> {dest_name}/ ({count} files)")
            except FileNotFoundError as err:
                print(f"Warning: {err}; skipping {dest_name}/", file=sys.stderr)

    if output_zip.exists():
        output_zip.unlink()

    for dest_name, _ in CLIENT_SYNC_SPECS:
        index = script_dir / dest_name / "index.html"
        if not index.is_file():
            mount = MOUNT_PATH_BY_DEST.get(dest_name, f"/{dest_name}/")
            print(
                f"Warning: {dest_name}/index.html not found; "
                f"hub will not serve {mount}",
                file=sys.stderr,
            )

    file_count, client_counts = build_zip(script_dir, output_zip)
    summary_parts = [
        f"{name}={client_counts.get(name, 0)}" for name, _ in CLIENT_SYNC_SPECS
    ]
    if "cast_py_client" in client_counts:
        summary_parts.append(f"cast_py_client={client_counts['cast_py_client']}")
    print(f"Created {output_zip} ({file_count} files; {', '.join(summary_parts)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
