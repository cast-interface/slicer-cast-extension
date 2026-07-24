"""Resolve CastInterface module root and Python import paths."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def extension_root() -> Path:
    """Installed or source module directory (parent of Lib/)."""
    return Path(__file__).resolve().parent.parent


def repo_root() -> Path:
    """Module directory containing bundled cast_hub/, cast_py_client/, etc."""
    env = os.environ.get("CAST_REPO_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    return extension_root()


def ensure_monorepo_import_paths() -> Path:
    """Add cast_py_client, RS runtime, and image-display lib to sys.path."""
    root = repo_root()
    extras = (
        root,
        root / "cast_py_client" / "src",
        root / "cast_resource_servers" / "runtime",
        root / "cast_resource_servers",
        root / "cast_slicer_image_display" / "lib",
    )
    for path in extras:
        s = str(path)
        if path.is_dir() and s not in sys.path:
            sys.path.insert(0, s)
    return root


def cast_hub_dir() -> Path:
    return repo_root() / "cast_hub"


def cast_hub_script() -> Path:
    return cast_hub_dir() / "cast_hub.py"


def resource_server_products_dir() -> Path:
    return repo_root() / "cast_resource_servers" / "products"
