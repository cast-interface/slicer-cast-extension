# AGENTS.md — slicer-cast-extension

## Hub server (authoritative)

Change Cast hub code only in **`CastInterface/cast_hub/`** (`cast_hub.py`). Do not edit legacy `SlicerCastInterface/CastInterface/cast_api/` or `VolView/server/cast_api/`.

Default local port: **2018** (`python CastInterface/cast_hub/cast_hub.py --port 2018`).

## Monorepo layout (all-in CastInterface/)

| Path | Role |
|------|------|
| `CMakeLists.txt` | Extension superbuild at repo root |
| `CastInterface/` | Slicer module package (discovery: `CastInterface/CastInterface.py`) |
| `CastInterface/Lib/` | Module UI helpers |
| `CastInterface/cast_hub/` | FastAPI hub |
| `CastInterface/cast_resource_servers/` | RS framework + `products/` |
| `CastInterface/cast_slicer_image_display/` | Slicer ID runtime + `run_image_display.py` |
| `CastInterface/cast_py_client/` | Python `cast_client` (`pip install -e cast_py_client` from `CastInterface/`) |

Runtime path resolution: `CastInterface/Lib/repo_paths.py` — `extension_root()` / `repo_root()` = module dir (contains bundled `cast_hub/`). Optional `CAST_REPO_ROOT` override.

Dev copy helper: `tools/sync_extension.py` (not a Slicer module).

## Line endings

LF only for all text files.

## Frozen downstream (v0.1)

Do not edit vtk-js, VolView, OHIF for Cast work in this migration phase.

## Event-name parity

When wire helpers change, update `cast_py_client`, vtk-js `eventNames.js`, and hub handlers together.
