# Standalone Cast components

Run these from a clone of [slicer-cast-extension](https://github.com/cast-interface/slicer-cast-extension) **without** opening the Cast Interface module in 3D Slicer.

All runtime folders live under **`CastInterface/`**.

## Prerequisites

```bash
cd CastInterface
pip install -e cast_py_client
```

Python 3.9+ recommended.

---

## cast_hub/

Cast / FHIRcast hub (FastAPI + WebSockets).

```bash
cd CastInterface/cast_hub
pip install -r requirements.txt
python cast_hub.py --port 2018
```

- Admin: http://127.0.0.1:2018/api/hub/admin  
- Cloud deploy: [CastInterface/cast_hub/azure-webapp.md](../CastInterface/cast_hub/azure-webapp.md)

---

## cast_resource_servers/

Standalone resource servers (no Slicer UI).

```bash
cd CastInterface
pip install -r cast_resource_servers/requirements.txt
python cast_resource_servers/products/neuro_seg.py --local
```

`--local` uses `http://127.0.0.1:2018`. Default is cloud `SLICER-HUB-CLOUD`.

Product docs: [cast_resource_servers/docs/](../CastInterface/cast_resource_servers/docs/).

---

## cast_slicer_image_display/

Slicer as an image display client (`3DSLICER-ID` actor). Requires **3D Slicer** and an open DICOM database, but **not** the Cast Interface module.

```bash
cd CastInterface
Slicer --python-script cast_slicer_image_display/run_image_display.py -- --local --topic USER-1
```

Flags: `--local`, `--topic`, `--hub`, `--product-name`.

---

## cast_py_client/

Shared Python wire-protocol client (`CastClient`, `SlicerCastClient`).

```bash
cd CastInterface
pip install -e cast_py_client
```

```python
from cast_client import SlicerCastClient, HubConfig, SessionConfig
```

---

## Browser image display

VolView and OHIF ship in the hub deploy zip (see `CastInterface/cast_hub/make_zip.py`). For local dev, use vtk-js / VolView builds against the same hub port.
