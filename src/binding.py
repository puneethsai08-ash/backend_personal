"""Load, validate, and compile hardware-CAD bindings."""

import json
import math
import os
import re
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError

from src.cad import (
    CADAssetError,
    export_robot_mjcf,
    metadata_for_path,
)
from src.wiring import get_pin_role


BASE_DIR = Path(__file__).resolve().parent.parent
BINDING_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class BindingError(ValueError):
    """Raised when a binding cannot be loaded or compiled."""


def load_binding(binding_id, project_root=BASE_DIR):
    if not BINDING_ID_PATTERN.fullmatch(binding_id):
        raise BindingError("Binding ID may contain only letters, numbers, '_' and '-'.")

    root = Path(project_root).resolve()
    binding_path = root / "bindings" / f"{binding_id}.yaml"
    schema_path = root / "schemas" / "binding.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        binding = yaml.safe_load(binding_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as error:
        raise BindingError(f"Unable to read binding '{binding_id}': {error}") from error
    try:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(binding)
    except (SchemaValidationError, TypeError, ValueError) as error:
        detail = getattr(error, "message", str(error))
        raise BindingError(f"Invalid binding '{binding_id}': {detail}") from error
    if binding.get("id") != binding_id:
        raise BindingError(f"Binding file '{binding_path.name}' declares a different ID.")
    return binding


def _connection_list(connection_manager, project_root):
    if connection_manager is not None:
        return connection_manager.get_connections()
    wiring_path = Path(project_root) / "output" / "wiring_config.json"
    if not wiring_path.is_file():
        return []
    try:
        data = json.loads(wiring_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BindingError(f"Unable to read wiring configuration: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("connections", []), list):
        raise BindingError("Wiring configuration must contain a connections list.")
    return data.get("connections", [])


def validate_binding(binding, registry, project_root=BASE_DIR, connection_manager=None):
    errors = []
    root = Path(project_root).resolve()
    links = binding.get("links", [])
    joints = binding.get("joints", [])
    component_bindings = binding.get("component_bindings", [])
    link_by_id = {link.get("id"): link for link in links}
    joint_by_id = {joint.get("id"): joint for joint in joints}
    root_link = binding.get("root_link")

    if len(link_by_id) != len(links):
        errors.append("CAD link IDs must be unique.")
    if len(joint_by_id) != len(joints):
        errors.append("Joint IDs must be unique.")
    if root_link not in link_by_id:
        errors.append(f"Root link '{root_link}' is not declared.")

    parent_by_child = {}
    for joint in joints:
        parent = joint.get("parent_link")
        child = joint.get("child_link")
        if parent not in link_by_id:
            errors.append(f"Joint '{joint.get('id')}' has unknown parent link '{parent}'.")
        if child not in link_by_id:
            errors.append(f"Joint '{joint.get('id')}' has unknown child link '{child}'.")
        if parent == child:
            errors.append(f"Joint '{joint.get('id')}' cannot connect a link to itself.")
        if child == root_link:
            errors.append(f"Root link '{root_link}' cannot be a joint child.")
        if child in parent_by_child:
            errors.append(f"Link '{child}' has more than one parent joint.")
        parent_by_child[child] = joint.get("id")
        axis = joint.get("axis", [0, 0, 1])
        axis_length = math.sqrt(sum(value * value for value in axis))
        if not math.isfinite(axis_length) or axis_length == 0:
            errors.append(f"Joint '{joint.get('id')}' must have a finite, non-zero axis.")
        limits = joint.get("range")
        if limits is not None and (
            not all(math.isfinite(value) for value in limits)
            or limits[0] >= limits[1]
        ):
            errors.append(f"Joint '{joint.get('id')}' must have an increasing finite range.")

    reachable = {root_link}
    changed = True
    while changed:
        changed = False
        for joint in joints:
            if joint.get("parent_link") in reachable and joint.get("child_link") not in reachable:
                reachable.add(joint.get("child_link"))
                changed = True
    for link_id in link_by_id:
        if link_id != root_link and link_id not in reachable:
            errors.append(f"Link '{link_id}' is orphaned from root '{root_link}'.")

    metadata_by_link = {}
    asset_paths_by_link = {}
    for link in links:
        link_id = link.get("id")
        asset_path = (root / link.get("asset", "")).resolve()
        try:
            asset_path.relative_to(root)
        except ValueError:
            errors.append(f"Link '{link_id}' asset path escapes the project root.")
            continue
        if not asset_path.is_file():
            errors.append(f"Link '{link_id}' CAD asset does not exist: {link.get('asset')}")
            continue
        try:
            metadata = metadata_for_path(asset_path)
        except CADAssetError as error:
            errors.append(f"Link '{link_id}' CAD asset is invalid: {error}")
            continue
        metadata_by_link[link_id] = metadata
        asset_paths_by_link[link_id] = asset_path

    bound_links = set()
    mapped_joints = {}
    seen_instances = set()
    for component_binding in component_bindings:
        instance_id = component_binding.get("instance_id")
        component_id = component_binding.get("component_id")
        if instance_id in seen_instances:
            errors.append(f"Duplicate component instance '{instance_id}'.")
        seen_instances.add(instance_id)
        component = registry.get(component_id)
        if component is None:
            errors.append(f"Unknown component '{component_id}' for instance '{instance_id}'.")
            continue
        link_id = component_binding.get("link_id")
        if link_id not in link_by_id:
            errors.append(f"Component '{instance_id}' references unknown link '{link_id}'.")
        else:
            bound_links.add(link_id)

        pins_by_id = {pin["id"]: pin for pin in component.get("pins", [])}
        mapped_pins = set()
        for pin_binding in component_binding.get("pin_bindings", []):
            pin_id = pin_binding.get("pin_id")
            role = pin_binding.get("role")
            if pin_id in mapped_pins:
                errors.append(f"Component '{instance_id}' maps pin '{pin_id}' more than once.")
            mapped_pins.add(pin_id)
            pin = pins_by_id.get(pin_id)
            if pin is None:
                errors.append(f"Component '{instance_id}' references unknown pin '{pin_id}'.")
                continue
            if pin.get("type") in {"power", "ground"}:
                errors.append(f"Component '{instance_id}' pin '{pin_id}' cannot have a functional role.")
                continue
            pin_role = get_pin_role(pin)
            if role == "control" and pin_role == "output":
                errors.append(f"Control pin '{pin_id}' of '{instance_id}' has output direction.")
            if role == "sensor" and pin_role == "input":
                errors.append(f"Sensor pin '{pin_id}' of '{instance_id}' has input direction.")
        for pin_id, pin in pins_by_id.items():
            if pin.get("type") not in {"power", "ground"} and pin_id not in mapped_pins:
                errors.append(f"Component '{instance_id}' has unmapped functional pin '{pin_id}'.")

        joint_id = component_binding.get("joint_id")
        if joint_id is None:
            continue
        joint = joint_by_id.get(joint_id)
        if joint is None:
            errors.append(f"Component '{instance_id}' references unknown joint '{joint_id}'.")
            continue
        if joint.get("type") == "fixed":
            errors.append(f"Fixed joint '{joint_id}' cannot be actuator-mapped.")
        if link_id != joint.get("child_link"):
            errors.append(f"Component '{instance_id}' must bind to child link '{joint.get('child_link')}'.")
        if component.get("category") != "actuator":
            errors.append(f"Only actuator components can map to joint '{joint_id}'.")
        if not any(item.get("role") == "control" for item in component_binding.get("pin_bindings", [])):
            errors.append(f"Actuator '{instance_id}' needs a control pin for joint '{joint_id}'.")
        if joint_id in mapped_joints:
            errors.append(f"Joint '{joint_id}' is mapped by more than one component instance.")
        mapped_joints[joint_id] = instance_id

    for link_id in link_by_id:
        if link_id != root_link and link_id not in bound_links:
            errors.append(f"Link '{link_id}' has no bound hardware component.")
    for joint in joints:
        if joint.get("type") != "fixed" and joint.get("id") not in mapped_joints:
            errors.append(f"Articulated joint '{joint.get('id')}' has no mapped actuator.")

    connections = _connection_list(connection_manager, root)
    bindings_by_component = {}
    for component_binding in component_bindings:
        bindings_by_component.setdefault(component_binding.get("component_id"), []).append(
            component_binding
        )
    reported_orphans = set()
    for connection in connections:
        for side in ("source", "target"):
            endpoint = connection.get(side, {})
            component_id = endpoint.get("component_id")
            pin_id = endpoint.get("pin_id")
            component = registry.get(component_id)
            if component is None or component.get("category") not in {"actuator", "sensor"}:
                continue
            matching_bindings = bindings_by_component.get(component_id, [])
            orphan_key = (component_id, pin_id)
            if not matching_bindings:
                if orphan_key not in reported_orphans:
                    errors.append(f"Wired component '{component_id}' has no CAD binding.")
                    reported_orphans.add(orphan_key)
                continue
            pin = next((item for item in component.get("pins", []) if item["id"] == pin_id), None)
            if pin is None or pin.get("type") in {"power", "ground"}:
                continue
            mapped = {
                item.get("pin_id")
                for component_binding in matching_bindings
                for item in component_binding.get("pin_bindings", [])
            }
            if pin_id not in mapped and orphan_key not in reported_orphans:
                errors.append(f"Wired pin '{pin_id}' of '{component_id}' is not mapped in CAD binding.")
                reported_orphans.add(orphan_key)

    return {
        "valid": not errors,
        "errors": errors,
        "metadata_by_link": metadata_by_link,
        "asset_paths_by_link": asset_paths_by_link,
    }


def compile_binding(
    binding,
    registry,
    project_root=BASE_DIR,
    output_dir=None,
    connection_manager=None,
):
    root = Path(project_root).resolve()
    requested_dir = Path(output_dir) if output_dir is not None else Path("output")
    destination = (requested_dir if requested_dir.is_absolute() else root / requested_dir).resolve()
    try:
        destination.relative_to(root)
    except ValueError as error:
        raise BindingError("Simulation output directory must remain within the project root.") from error

    validation = validate_binding(binding, registry, root, connection_manager)
    if not validation["valid"]:
        raise BindingError("; ".join(validation["errors"]))

    mesh_files = {
        link_id: os.path.relpath(path, destination).replace(os.sep, "/")
        for link_id, path in validation["asset_paths_by_link"].items()
    }
    mjcf = export_robot_mjcf(
        binding, validation["metadata_by_link"], mesh_files
    )
    destination.mkdir(parents=True, exist_ok=True)
    mjcf_path = destination / f"{binding['id']}.mjcf"
    mjcf_path.write_text(mjcf, encoding="utf-8")

    components_by_id = {component["id"]: component for component in registry.get_all()}
    if connection_manager is None:
        wiring_path = root / "output" / "wiring_config.json"
        wiring = (
            json.loads(wiring_path.read_text(encoding="utf-8"))
            if wiring_path.is_file()
            else {"schema_version": "1.0", "connections": []}
        )
    else:
        wiring = connection_manager.to_dict()
    bundle = {
        "schema_version": "1.0",
        "binding_id": binding["id"],
        "name": binding["name"],
        "mjcf": mjcf_path.relative_to(root).as_posix(),
        "links": [
            {
                **link,
                "metadata": validation["metadata_by_link"][link["id"]],
            }
            for link in binding["links"]
        ],
        "joints": binding["joints"],
        "component_bindings": [
            {
                **item,
                "component": components_by_id[item["component_id"]],
            }
            for item in binding["component_bindings"]
        ],
        "wiring": wiring,
    }
    (destination / "sim_bundle.json").write_text(
        json.dumps(bundle, indent=2), encoding="utf-8"
    )
    return bundle


def compile_binding_by_id(
    binding_id,
    registry,
    project_root=BASE_DIR,
    output_dir=None,
    connection_manager=None,
):
    binding = load_binding(binding_id, project_root)
    return compile_binding(
        binding, registry, project_root, output_dir, connection_manager
    )
