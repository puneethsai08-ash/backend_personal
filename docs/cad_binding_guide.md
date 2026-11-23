# CAD Asset and Hardware-CAD Binding MVP

The MVP adds CAD ingestion and hardware-to-CAD validation without changing the
component registry, wiring rules, or connection manager. Its implementation is
kept flat in `src/cad.py` and `src/binding.py`.

## CAD assets

The asset endpoint accepts ASCII or binary STL files. Meshes must be closed and
have finite, non-degenerate geometry. Ingested files and JSON metadata are saved
under `cad_assets/` using a content-derived ID.

- `POST /cad/ingest` accepts a multipart `file` upload.
- `GET /cad/{asset_id}/metadata` returns dimensions, volume, centre of mass,
  and inertia.
- `GET /cad/{asset_id}/mjcf` returns an MJCF XML document.

STEP/STP parsing is intentionally unsupported until an OpenCASCADE adapter is
available. MJCF is an interchange artifact; this service does not run a
simulator.

## Hardware-CAD bindings

Bindings are YAML files in `bindings/` validated against
`schemas/binding.schema.json`. A binding maps CAD links and joints to registered
components and their functional pins. Validation checks asset paths and mesh
geometry, link reachability, component and pin references, pin roles, and
actuator mappings for articulated joints. Existing wiring is checked for
unmapped sensor and actuator pins.

- `POST /bindings/validate` with `{"binding_id":"demo_servo_bot"}` reports
  semantic errors.
- `POST /bindings/compile` writes `output/{binding_id}.mjcf` and
  `output/sim_bundle.json`.

There is no binding skeleton generator. Python API tests run with:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```
