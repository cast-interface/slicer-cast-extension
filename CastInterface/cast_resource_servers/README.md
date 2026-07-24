# Cast resource servers

Standalone Cast resource-server framework and product scripts.

## Install

From monorepo root:

```bash
pip install -e cast_py_client
pip install -r cast_resource_servers/requirements.txt
```

## Run a product

```bash
python cast_resource_servers/products/neuro_seg.py --local
```

See [docs/](docs/) for per-product guides.
