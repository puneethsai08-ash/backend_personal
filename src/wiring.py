"""Connection compatibility validation for RoboBench components."""

from src.validator import ComponentValidationError


INPUT_FUNCTIONS = {
    "digital_input",
    "analog_input",
    "trigger_input",
    "pwm_control",
    "motor_direction_control",
    "motor_speed_control",
}

OUTPUT_FUNCTIONS = {
    "digital_output",
    "analog_output",
    "analog_light_output",
    "echo_output",
}


class WiringValidationError(Exception):
    """Raised when component wiring data is invalid."""


def find_pin(component, pin_id):
    """Find a pin using its logical ID."""

    if not isinstance(component, dict):
        raise WiringValidationError("Invalid component definition.")

    for pin in component.get("pins", []):
        if pin.get("id") == pin_id:
            return pin

    raise WiringValidationError(
        f"Pin '{pin_id}' not found in component "
        f"'{component.get('id', 'unknown')}'."
    )


def get_pin_role(pin):
    """Determine whether a pin behaves as input or output."""

    direction = pin.get("direction")

    if direction in ("input", "output", "bidirectional"):
        return direction

    functions = set(pin.get("functions", []))

    has_input = bool(functions & INPUT_FUNCTIONS)
    has_output = bool(functions & OUTPUT_FUNCTIONS)

    if has_input and has_output:
        return "bidirectional"

    if has_input:
        return "input"

    if has_output:
        return "output"

    return None


def check_pin_type_compatibility(source_pin, target_pin):
    """Check whether two pin types can be connected."""

    source_type = source_pin.get("type")
    target_type = target_pin.get("type")

    compatible_types = {
        "gpio": {"gpio", "digital"},
        "digital": {"gpio", "digital"},
        "analog": {"analog"},
        "power": {"power"},
        "ground": {"ground"},
    }

    return target_type in compatible_types.get(
        source_type, set()
    )


def validate_connection(
    source_component,
    source_pin_id,
    target_component,
    target_pin_id,
):
    """
    Validate a directed connection from source to target.

    Returns an empty list when the connection is valid.
    Otherwise returns a list of validation errors.
    """

    errors = []

    source_pin = find_pin(source_component, source_pin_id)
    target_pin = find_pin(target_component, target_pin_id)

    source_type = source_pin.get("type")
    target_type = target_pin.get("type")

    # Power and ground connections are checked separately.
    if source_type in ("power", "ground") or target_type in (
        "power", "ground"
    ):
        if source_type != target_type:
            errors.append(
                "Power and ground pins cannot be connected "
                "to incompatible pin types."
            )

        return errors

    if not check_pin_type_compatibility(source_pin, target_pin):
        errors.append(
            f"Incompatible pin types: "
            f"{source_type} -> {target_type}."
        )

    source_role = get_pin_role(source_pin)
    target_role = get_pin_role(target_pin)

    if source_role not in ("output", "bidirectional"):
        errors.append(
            f"Source pin '{source_pin_id}' is not configured "
            "as an output."
        )

    if target_role not in ("input", "bidirectional"):
        errors.append(
            f"Target pin '{target_pin_id}' is not configured "
            "as an input."
        )

    return errors


def can_connect(
    source_component,
    source_pin_id,
    target_component,
    target_pin_id,
):
    """Return True when a connection is valid."""

    try:
        return not validate_connection(
            source_component,
            source_pin_id,
            target_component,
            target_pin_id,
        )
    except WiringValidationError:
        return False


if __name__ == "__main__":
    print("RoboBench Wiring Compatibility Engine")
    print("Import validate_connection() to validate connections.")
