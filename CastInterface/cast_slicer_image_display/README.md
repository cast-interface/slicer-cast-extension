# Slicer image display client

Cast image display client for 3D Slicer (`imagingstudy-open`, `dicom-send`, etc.).

## Run without Cast Interface module

Requires 3D Slicer with DICOM database open:

```bash
pip install -e cast_py_client
Slicer --python-script cast_slicer_image_display/run_image_display.py -- --local --topic USER-1
```

## Library

Runtime code lives in `lib/` (`image_display_client_hub.py`, loaders, handlers).
