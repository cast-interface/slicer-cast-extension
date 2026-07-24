# slicer-cast-extension

3D Slicer **Cast Interface** extension: hub, resource servers, image display, and Python client under `CastInterface/` — runnable **without** opening the module UI.

**GitHub:** [cast-interface/slicer-cast-extension](https://github.com/cast-interface/slicer-cast-extension)

## Layout

| Path | Purpose |
|------|---------|
| [`CastInterface/`](CastInterface/) | Slicer module package (`CastInterface.py`, `Lib/`, `Resources/`, bundled runtime) |
| `CastInterface/cast_hub/` | FastAPI Cast hub (`cast_hub.py`) |
| `CastInterface/cast_resource_servers/` | Resource-server framework + products |
| `CastInterface/cast_slicer_image_display/` | Slicer image display runtime + CLI |
| `CastInterface/cast_py_client/` | Python `cast_client` package |
| [`docs/`](docs/) | Extension docs (module docs under `docs/module/`) |

CMake install copies `CastInterface/` into `qt-scripted-modules/CastInterface/` (module scripts + bundled folders).

## Quick start (no Cast Interface module)

```bash
cd CastInterface

# One-time: shared Python client
pip install -e cast_py_client

# Terminal 1 — Hub
cd cast_hub && pip install -r requirements.txt && python cast_hub.py --port 2018

# Terminal 2 — Resource server (example)
python cast_resource_servers/products/neuro_seg.py --local

# Terminal 3 — Slicer image display (Slicer required; module NOT required)
Slicer --python-script cast_slicer_image_display/run_image_display.py -- --local --topic USER-1
```

Admin UI: http://127.0.0.1:2018/api/hub/admin

See [docs/standalone-components.md](docs/standalone-components.md) for details.

## 3D Slicer extension

Build from this repo (`CMakeLists.txt` at repo root, module in `CastInterface/`). For dev, add the **repo root** to Additional module paths — Slicer discovers `CastInterface/CastInterface.py`.

Optional sync into an installed module directory:

```bash
export SLICER_CAST_EXTENSION="/path/to/qt-scripted-modules/CastInterface"
python tools/sync_extension.py --bundle
```

Override module root at runtime with `CAST_REPO_ROOT` when needed.

## License

MIT — see [LICENSE](LICENSE).
