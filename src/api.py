"""FastAPI integration layer for RoboBench Component Library."""

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from pydantic import BaseModel

import src.binding as binding_service
import src.cad as cad_service
from src.registry import ComponentRegistry, RegistryError
from src.connection_manager import (
    ConnectionManager,
    ConnectionManagerError,
)
from src.wiring import (
    validate_connection,
    WiringValidationError,
)


app = FastAPI(
    title="RoboBench Component Library API",
    description="API for hardware components, wiring, CAD assets, and bindings.",
    version="1.0.0",
)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Initialize component registry and connection manager.
registry = ComponentRegistry()

try:
    registry.load_all()
except RegistryError as error:
    raise RuntimeError(
        f"Unable to initialize component registry: {error}"
    ) from error

connection_manager = ConnectionManager(registry)


class ConnectionRequest(BaseModel):
    source_component_id: str
    source_pin_id: str
    target_component_id: str
    target_pin_id: str


class BindingRequest(BaseModel):
    binding_id: str


@app.get("/")
def home():
    return {
        "message": "RoboBench Component Library API is running.",
        "version": "1.0.0",
    }


@app.get("/components")
def get_components():
    return {
        "total": registry.count(),
        "components": registry.get_all(),
    }


@app.get("/components/category/{category}")
def get_components_by_category(category: str):
    components = registry.get_by_category(category)

    return {
        "category": category,
        "total": len(components),
        "components": components,
    }


@app.get("/components/{component_id}")
def get_component(component_id: str):
    component = registry.get(component_id)

    if component is None:
        raise HTTPException(
            status_code=404,
            detail=f"Component '{component_id}' not found.",
        )

    return component


@app.post("/connections/validate")
def validate_wiring(request: ConnectionRequest):
    source = registry.get(request.source_component_id)
    target = registry.get(request.target_component_id)

    if source is None or target is None:
        raise HTTPException(
            status_code=404,
            detail="Source or target component not found.",
        )

    try:
        errors = validate_connection(
            source,
            request.source_pin_id,
            target,
            request.target_pin_id,
        )

    except WiringValidationError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }


@app.post("/connections", status_code=201)
def create_connection(request: ConnectionRequest):
    try:
        connection = connection_manager.add_connection(
            request.source_component_id,
            request.source_pin_id,
            request.target_component_id,
            request.target_pin_id,
        )

        return {
            "message": "Connection created successfully.",
            "connection": connection,
        }

    except ConnectionManagerError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@app.get("/connections")
def get_connections():
    return {
        "total": connection_manager.count(),
        "connections": connection_manager.get_connections(),
    }


@app.get("/connections/export")
def export_connections():
    return connection_manager.to_dict()


@app.post("/cad/ingest", status_code=201)
async def ingest_cad_asset(file: UploadFile = File(...)):
    try:
        return cad_service.ingest_asset(
            await file.read(),
            file.filename or "",
            cad_service.CAD_ASSET_DIR,
        )
    except cad_service.CADAssetError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/cad/{asset_id}/metadata")
def get_cad_metadata(asset_id: str):
    try:
        return cad_service.get_metadata(asset_id, cad_service.CAD_ASSET_DIR)
    except cad_service.CADAssetError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/cad/{asset_id}/mjcf")
def get_cad_mjcf(asset_id: str):
    try:
        metadata = cad_service.get_metadata(asset_id, cad_service.CAD_ASSET_DIR)
        asset_path = cad_service.asset_path_for_id(asset_id, cad_service.CAD_ASSET_DIR)
        return Response(
            content=cad_service.export_asset_mjcf(metadata, asset_path.name),
            media_type="application/xml",
        )
    except cad_service.CADAssetError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/bindings/validate")
def validate_hardware_binding(request: BindingRequest):
    try:
        binding = binding_service.load_binding(request.binding_id, PROJECT_ROOT)
    except binding_service.BindingError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    result = binding_service.validate_binding(
        binding,
        registry,
        PROJECT_ROOT,
        connection_manager=connection_manager,
    )
    return {"valid": result["valid"], "errors": result["errors"]}


@app.post("/bindings/compile")
def compile_hardware_binding(request: BindingRequest):
    try:
        return binding_service.compile_binding_by_id(
            request.binding_id,
            registry,
            PROJECT_ROOT,
            connection_manager=connection_manager,
        )
    except binding_service.BindingError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
