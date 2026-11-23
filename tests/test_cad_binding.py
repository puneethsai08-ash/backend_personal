import shutil
from pathlib import Path
from xml.etree import ElementTree

from fastapi.testclient import TestClient
import pytest

import src.api as api
import src.cad as cad
from src.binding import compile_binding, load_binding, validate_binding
from src.registry import ComponentRegistry


BASE_DIR = Path(__file__).resolve().parent.parent


def load_registry():
    registry = ComponentRegistry()
    registry.load_all()
    return registry


def test_stl_ingestion_metadata_and_mjcf(tmp_path):
    contents = (BASE_DIR / "cad_assets" / "demo_tetra.stl").read_bytes()
    metadata = cad.ingest_asset(contents, "demo_tetra.stl", tmp_path)

    assert metadata["watertight"] is True
    assert metadata["volume"] == pytest.approx(0.04 * 0.012 * 0.004 / 6)
    assert metadata["dimensions"]["x"] == pytest.approx(0.04)
    assert len(metadata["inertia"]) == 3
    assert cad.get_metadata(metadata["id"], tmp_path) == metadata

    xml = cad.export_asset_mjcf(metadata, metadata["asset_file"])
    root = ElementTree.fromstring(xml)
    assert root.tag == "mujoco"
    assert root.find("./asset/mesh").get("file") == metadata["asset_file"]
    assert float(root.find(".//inertial").get("mass")) > 0


def test_stl_ingestion_rejects_open_and_unsupported_meshes(tmp_path):
    contents = b"""solid open
facet normal 0 0 1
outer loop
vertex 0 0 0
vertex 1 0 0
vertex 0 1 0
endloop
endfacet
endsolid open
"""
    with pytest.raises(cad.CADAssetError, match="watertight"):
        cad.ingest_asset(contents, "open.stl", tmp_path)
    with pytest.raises(cad.CADAssetError, match="OpenCASCADE"):
        cad.ingest_asset(b"ISO-10303-21;", "assembly.step", tmp_path)


def test_binding_validation_and_compilation(tmp_path):
    shutil.copytree(BASE_DIR / "bindings", tmp_path / "bindings")
    shutil.copytree(BASE_DIR / "schemas", tmp_path / "schemas")
    shutil.copytree(BASE_DIR / "cad_assets", tmp_path / "cad_assets")
    registry = load_registry()
    binding = load_binding("demo_servo_bot", tmp_path)

    result = validate_binding(binding, registry, tmp_path)
    assert result["valid"] is True
    assert result["errors"] == []

    bundle = compile_binding(binding, registry, tmp_path, output_dir=tmp_path / "output")
    assert bundle["binding_id"] == "demo_servo_bot"
    assert len(bundle["links"]) == 3
    assert len(bundle["joints"]) == 2
    root = ElementTree.parse(tmp_path / bundle["mjcf"]).getroot()
    assert root.tag == "mujoco"
    assert root.find(".//joint[@name='servo_joint']").get("type") == "hinge"


def test_cad_and_binding_api(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    shutil.copytree(BASE_DIR / "bindings", project_root / "bindings")
    shutil.copytree(BASE_DIR / "schemas", project_root / "schemas")
    shutil.copytree(BASE_DIR / "cad_assets", project_root / "cad_assets")
    monkeypatch.setattr(api, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(cad, "CAD_ASSET_DIR", tmp_path / "uploads")
    api.connection_manager.connections.clear()

    try:
        with TestClient(api.app) as client:
            contents = (BASE_DIR / "cad_assets" / "demo_tetra.stl").read_bytes()
            ingested = client.post(
                "/cad/ingest",
                files={"file": ("sample.stl", contents, "model/stl")},
            )
            assert ingested.status_code == 201
            asset_id = ingested.json()["id"]
            assert client.get(f"/cad/{asset_id}/metadata").status_code == 200
            mjcf = client.get(f"/cad/{asset_id}/mjcf")
            assert mjcf.headers["content-type"] == "application/xml"
            assert "<mujoco" in mjcf.text

            validation = client.post(
                "/bindings/validate",
                json={"binding_id": "demo_servo_bot"},
            )
            assert validation.status_code == 200
            assert validation.json() == {"valid": True, "errors": []}

            compilation = client.post(
                "/bindings/compile",
                json={"binding_id": "demo_servo_bot"},
            )
            assert compilation.status_code == 200
            assert compilation.json()["binding_id"] == "demo_servo_bot"
            assert (project_root / compilation.json()["mjcf"]).is_file()
    finally:
        api.connection_manager.connections.clear()
