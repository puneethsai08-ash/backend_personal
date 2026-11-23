"""STL ingestion and MJCF export for CAD assets."""

import hashlib
import json
import math
import re
import struct
from pathlib import Path
from xml.etree import ElementTree


BASE_DIR = Path(__file__).resolve().parent.parent
CAD_ASSET_DIR = BASE_DIR / "cad_assets"
ASSET_ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class CADAssetError(ValueError):
    """Raised when a CAD asset cannot be read or exported."""


def _parse_stl(contents):
    if len(contents) >= 84:
        triangle_count = struct.unpack_from("<I", contents, 80)[0]
        if len(contents) == 84 + triangle_count * 50:
            triangles = []
            offset = 84
            for _ in range(triangle_count):
                values = struct.unpack_from("<12fH", contents, offset)
                triangles.append(
                    [tuple(values[index:index + 3]) for index in (3, 6, 9)]
                )
                offset += 50
            return triangles

    try:
        text = contents.decode("ascii")
    except UnicodeDecodeError as error:
        raise CADAssetError("STL content is neither binary nor ASCII.") from error

    vertices = []
    for line in text.splitlines():
        parts = line.strip().split()
        if parts and parts[0].lower() == "vertex":
            if len(parts) != 4:
                raise CADAssetError("STL vertex must contain three coordinates.")
            try:
                vertices.append(tuple(float(value) for value in parts[1:]))
            except ValueError as error:
                raise CADAssetError("STL contains an invalid vertex.") from error

    if not vertices or len(vertices) % 3:
        raise CADAssetError("STL must contain complete triangle facets.")
    return [vertices[index:index + 3] for index in range(0, len(vertices), 3)]


def _cross(left, right):
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _dot(left, right):
    return sum(a * b for a, b in zip(left, right))


def _asset_metadata(contents, filename, asset_id, asset_file):
    triangles = _parse_stl(contents)
    vertices = []
    vertex_ids = {}
    edge_counts = {}

    for triangle in triangles:
        if any(not all(math.isfinite(value) for value in point) for point in triangle):
            raise CADAssetError("STL coordinates must be finite.")
        face = []
        for point in triangle:
            if point not in vertex_ids:
                vertex_ids[point] = len(vertices)
                vertices.append(point)
            face.append(vertex_ids[point])
        if len(set(face)) != 3:
            raise CADAssetError("STL contains a degenerate triangle.")
        for index in range(3):
            edge = tuple(sorted((face[index], face[(index + 1) % 3])))
            edge_counts[edge] = edge_counts.get(edge, 0) + 1

    if any(count != 2 for count in edge_counts.values()):
        raise CADAssetError("CAD mesh must be watertight.")

    signed_volume = 0.0
    first_moment = [0.0, 0.0, 0.0]
    second_moment = [[0.0] * 3 for _ in range(3)]
    for triangle in triangles:
        a, b, c = triangle
        tetra_volume = _dot(a, _cross(b, c)) / 6.0
        signed_volume += tetra_volume
        for axis in range(3):
            first_moment[axis] += tetra_volume * (a[axis] + b[axis] + c[axis]) / 4.0
        point_sum = [a[axis] + b[axis] + c[axis] for axis in range(3)]
        for row in range(3):
            for column in range(3):
                products = (
                    a[row] * a[column]
                    + b[row] * b[column]
                    + c[row] * c[column]
                )
                second_moment[row][column] += (
                    tetra_volume
                    * (point_sum[row] * point_sum[column] + products)
                    / 20.0
                )

    if not math.isfinite(signed_volume) or abs(signed_volume) <= 1e-12:
        raise CADAssetError("CAD mesh has zero or invalid volume.")

    volume = abs(signed_volume)
    center = [value / signed_volume for value in first_moment]
    orientation = 1.0 if signed_volume > 0 else -1.0
    second_moment = [
        [value * orientation for value in row] for row in second_moment
    ]
    inertia = []
    center_squared = _dot(center, center)
    for row in range(3):
        inertia_row = []
        for column in range(3):
            origin_inertia = (
                sum(second_moment[axis][axis] for axis in range(3))
                if row == column
                else 0.0
            ) - second_moment[row][column]
            parallel_axis = volume * (
                center_squared if row == column else 0.0
            ) - volume * center[row] * center[column]
            inertia_row.append(origin_inertia - parallel_axis)
        inertia.append(inertia_row)
    if not all(math.isfinite(value) for value in center):
        raise CADAssetError("CAD mesh has an invalid centre of mass.")
    if not all(math.isfinite(value) for row in inertia for value in row):
        raise CADAssetError("CAD mesh has an invalid inertia tensor.")
    if any(inertia[index][index] <= 0 for index in range(3)):
        raise CADAssetError("CAD mesh inertia must be positive.")

    dimensions = [
        max(point[axis] for point in vertices)
        - min(point[axis] for point in vertices)
        for axis in range(3)
    ]
    if any(not math.isfinite(value) or value <= 0 for value in dimensions):
        raise CADAssetError("CAD mesh has invalid or degenerate dimensions.")

    return {
        "id": asset_id,
        "filename": filename,
        "asset_file": asset_file,
        "format": "stl",
        "dimensions": dict(zip(("x", "y", "z"), dimensions)),
        "volume": volume,
        "center_of_mass": dict(zip(("x", "y", "z"), center)),
        "inertia": inertia,
        "watertight": True,
    }


def asset_path_for_id(asset_id, asset_dir=CAD_ASSET_DIR):
    if not ASSET_ID_PATTERN.fullmatch(asset_id):
        raise CADAssetError("Invalid CAD asset ID.")
    path = Path(asset_dir) / f"{asset_id}.stl"
    if not path.is_file():
        raise CADAssetError(f"CAD asset '{asset_id}' was not found.")
    return path


def get_metadata(asset_id, asset_dir=CAD_ASSET_DIR):
    asset_path = asset_path_for_id(asset_id, asset_dir)
    metadata_path = asset_path.with_suffix(".metadata.json")
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CADAssetError(f"Unable to read metadata for '{asset_id}'.") from error


def metadata_for_path(asset_path):
    path = Path(asset_path)
    if path.suffix.lower() != ".stl":
        raise CADAssetError(f"Unsupported CAD format '{path.suffix}'.")
    try:
        contents = path.read_bytes()
    except OSError as error:
        raise CADAssetError(f"Unable to read CAD asset '{path.name}'.") from error
    asset_id = hashlib.sha256(contents + b".stl").hexdigest()
    return _asset_metadata(contents, path.name, asset_id, path.name)


def ingest_asset(contents, filename, asset_dir=CAD_ASSET_DIR):
    name = Path(filename.replace("\\", "/")).name
    extension = Path(name).suffix.lower()
    if extension in {".step", ".stp"}:
        raise CADAssetError("STEP parsing is not enabled; an OpenCASCADE adapter is required.")
    if extension != ".stl":
        raise CADAssetError(f"Unsupported CAD format '{extension}'; only STL is supported.")
    if not contents:
        raise CADAssetError("Uploaded CAD asset is empty.")

    asset_id = hashlib.sha256(contents + extension.encode("ascii")).hexdigest()
    asset_file = f"{asset_id}{extension}"
    metadata = _asset_metadata(contents, name, asset_id, asset_file)
    directory = Path(asset_dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / asset_file).write_bytes(contents)
    (directory / f"{asset_id}.metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )
    return metadata


def _xml_name(value):
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", value)
    if not name or not name[0].isalpha():
        name = f"model_{name}"
    return name


def _add_link_geometry(body, link_id, metadata, mesh_name, density):
    mass = metadata["volume"] * density
    if not math.isfinite(mass) or mass <= 0:
        raise CADAssetError(f"Link '{link_id}' has invalid mass.")
    inertia = metadata["inertia"]
    values = (
        inertia[0][0],
        inertia[1][1],
        inertia[2][2],
        inertia[0][1],
        inertia[0][2],
        inertia[1][2],
    )
    center = metadata["center_of_mass"]
    ElementTree.SubElement(
        body,
        "inertial",
        pos=f"{center['x']:.9g} {center['y']:.9g} {center['z']:.9g}",
        mass=f"{mass:.9g}",
        fullinertia=" ".join(f"{value * density:.9g}" for value in values),
    )
    ElementTree.SubElement(
        body,
        "geom",
        name=_xml_name(f"{link_id}_geometry"),
        type="mesh",
        mesh=mesh_name,
    )


def export_asset_mjcf(metadata, mesh_file, model_name=None, density=1000.0):
    if density <= 0:
        raise CADAssetError("Density must be greater than zero.")
    root = ElementTree.Element(
        "mujoco", model=_xml_name(model_name or metadata["id"])
    )
    ElementTree.SubElement(root, "compiler", angle="radian")
    assets = ElementTree.SubElement(root, "asset")
    mesh_name = _xml_name(metadata["id"])
    ElementTree.SubElement(assets, "mesh", name=mesh_name, file=str(mesh_file).replace("\\", "/"))
    worldbody = ElementTree.SubElement(root, "worldbody")
    body = ElementTree.SubElement(worldbody, "body", name="cad_asset")
    _add_link_geometry(body, "cad_asset", metadata, mesh_name, density)
    return ElementTree.tostring(root, encoding="unicode")


def export_robot_mjcf(binding, metadata_by_link, mesh_file_by_link, density=1000.0):
    if density <= 0:
        raise CADAssetError("Density must be greater than zero.")
    root = ElementTree.Element("mujoco", model=_xml_name(binding["name"]))
    ElementTree.SubElement(root, "compiler", angle="radian")
    assets = ElementTree.SubElement(root, "asset")
    for link in binding["links"]:
        ElementTree.SubElement(
            assets,
            "mesh",
            name=_xml_name(link["id"]),
            file=str(mesh_file_by_link[link["id"]]).replace("\\", "/"),
        )

    worldbody = ElementTree.SubElement(root, "worldbody")
    root_link = binding["root_link"]
    root_body = ElementTree.SubElement(worldbody, "body", name=_xml_name(root_link))
    body_by_link = {root_link: root_body}
    _add_link_geometry(
        root_body, root_link, metadata_by_link[root_link], _xml_name(root_link), density
    )
    joints_by_parent = {}
    for joint in binding["joints"]:
        joints_by_parent.setdefault(joint["parent_link"], []).append(joint)

    pending = list(joints_by_parent.get(root_link, []))
    while pending:
        joint = pending.pop(0)
        parent = body_by_link.get(joint["parent_link"])
        if parent is None:
            raise CADAssetError(f"Joint '{joint['id']}' has no exported parent.")
        child_link = joint["child_link"]
        child = ElementTree.SubElement(parent, "body", name=_xml_name(child_link))
        body_by_link[child_link] = child
        joint_type = joint["type"]
        if joint_type != "fixed":
            axis = joint.get("axis", [0, 0, 1])
            length = math.sqrt(sum(value * value for value in axis))
            if not math.isfinite(length) or length == 0:
                raise CADAssetError(f"Joint '{joint['id']}' has an invalid axis.")
            attributes = {
                "name": _xml_name(joint["id"]),
                "type": "slide" if joint_type == "prismatic" else "hinge",
                "axis": " ".join(f"{value / length:.9g}" for value in axis),
            }
            if joint.get("range") is not None:
                attributes["range"] = " ".join(str(value) for value in joint["range"])
                attributes["limited"] = "true"
            ElementTree.SubElement(child, "joint", attributes)
        _add_link_geometry(
            child, child_link, metadata_by_link[child_link], _xml_name(child_link), density
        )
        pending.extend(joints_by_parent.get(child_link, []))

    if len(body_by_link) != len(binding["links"]):
        raise CADAssetError("Not every bound link could be exported.")
    return ElementTree.tostring(root, encoding="unicode")
