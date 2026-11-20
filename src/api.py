"""FastAPI integration layer for RoboBench Component Library."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

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
    description="API for components, wiring validation and connections.",
    version="1.0.0",
)


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
