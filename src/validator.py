import json
import yaml

from pathlib import Path
from jsonschema import Draft202012Validator


BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = BASE_DIR / "schemas" / "component.schema.json"


class ComponentValidationError(Exception):
    """Raised when component data cannot be loaded or validated."""


def load_schema():
    """Load and verify the component JSON Schema."""

    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as file:
            schema = json.load(file)

        Draft202012Validator.check_schema(schema)
        return schema

    except (OSError, json.JSONDecodeError, Exception) as error:
        raise ComponentValidationError(
            f"Unable to load component schema: {error}"
        ) from error


def load_component(file_path):
    """Load a YAML component definition."""

    path = Path(file_path)

    try:
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        if not isinstance(data, dict):
            raise ComponentValidationError(
                "Component YAML must contain a mapping."
            )

        return data

    except yaml.YAMLError as error:
        raise ComponentValidationError(
            f"Invalid YAML syntax: {error}"
        ) from error

    except OSError as error:
        raise ComponentValidationError(
            f"Unable to read component file: {error}"
        ) from error


def validate_schema(data, schema):
    """Validate component structure against JSON Schema."""

    validator = Draft202012Validator(schema)

    errors = sorted(
        validator.iter_errors(data),
        key=lambda error: list(error.absolute_path)
    )

    messages = []

    for error in errors:
        location = ".".join(
            str(part) for part in error.absolute_path
        ) or "root"

        messages.append(
            f"{location}: {error.message}"
        )

    return messages


def validate_pin_uniqueness(component):
    """Detect duplicate GPIO identifiers and physical pin numbers."""

    errors = []

    pins = component.get("pins", [])

    pin_ids = set()
    pin_numbers = set()

    for index, pin in enumerate(pins):

        if not isinstance(pin, dict):
            continue

        pin_id = pin.get("id")

        if pin_id is not None:
            if pin_id in pin_ids:
                errors.append(
                    f"Duplicate pin ID '{pin_id}' at pins[{index}]."
                )
            else:
                pin_ids.add(pin_id)

        pin_number = pin.get("number")

        if pin_number is not None:
            if pin_number in pin_numbers:
                errors.append(
                    f"Duplicate physical pin number "
                    f"'{pin_number}' at pins[{index}]."
                )
            else:
                pin_numbers.add(pin_number)

    return errors


def validate_electrical_properties(component):
    """Check electrical voltage and current ranges."""

    errors = []

    electrical = component.get("electrical", {})

    if not isinstance(electrical, dict):
        return errors

    voltage_min = electrical.get("input_voltage_min")
    voltage_max = electrical.get("input_voltage_max")

    if (
        isinstance(voltage_min, (int, float))
        and not isinstance(voltage_min, bool)
        and isinstance(voltage_max, (int, float))
        and not isinstance(voltage_max, bool)
    ):
        if voltage_min > voltage_max:
            errors.append(
                "input_voltage_min cannot exceed input_voltage_max."
            )

    current_min = electrical.get("operating_current_min")
    current_max = electrical.get("operating_current_max")

    if (
        isinstance(current_min, (int, float))
        and not isinstance(current_min, bool)
        and isinstance(current_max, (int, float))
        and not isinstance(current_max, bool)
    ):
        if current_min > current_max:
            errors.append(
                "operating_current_min cannot exceed "
                "operating_current_max."
            )

    return errors


def validate_component_data(data):
    """Run structural and semantic component validation."""

    schema = load_schema()

    errors = validate_schema(data, schema)

    if errors:
        return errors

    component = data["component"]

    errors.extend(validate_pin_uniqueness(component))
    errors.extend(validate_electrical_properties(component))

    return errors


def validate_component(file_path, verbose=True):
    """Load and validate a component YAML file."""

    try:
        data = load_component(file_path)
        errors = validate_component_data(data)

        if errors:
            if verbose:
                print("Component validation FAILED!")

                for error in errors:
                    print(f"- {error}")

            return False

        if verbose:
            print("Component validation SUCCESSFUL!")

        return True

    except ComponentValidationError as error:
        if verbose:
            print(f"Component validation FAILED: {error}")

        return False


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Validate RoboBench component YAML files."
    )

    parser.add_argument(
        "component_file",
        help="Path to the component YAML file."
    )

    args = parser.parse_args()

    component_file = Path(args.component_file)

    if not component_file.is_absolute():
        component_file = BASE_DIR / component_file

    success = validate_component(component_file)

    sys.exit(0 if success else 1)
