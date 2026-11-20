"""Manage and export RoboBench wiring connections."""

import json
from pathlib import Path

from src.wiring import (
    validate_connection,
    WiringValidationError,
)


class ConnectionManagerError(Exception):
    """Raised when a wiring connection cannot be managed."""


class ConnectionManager:
    """Store and manage validated component connections."""

    def __init__(self, registry):
        self.registry = registry
        self.connections = []

    def add_connection(
        self,
        source_component_id,
        source_pin_id,
        target_component_id,
        target_pin_id,
    ):
        """Validate and add a connection between two components."""

        source_component = self.registry.get(source_component_id)
        target_component = self.registry.get(target_component_id)

        if source_component is None:
            raise ConnectionManagerError(
                f"Source component '{source_component_id}' not found."
            )

        if target_component is None:
            raise ConnectionManagerError(
                f"Target component '{target_component_id}' not found."
            )

        try:
            errors = validate_connection(
                source_component,
                source_pin_id,
                target_component,
                target_pin_id,
            )
        except WiringValidationError as error:
            raise ConnectionManagerError(str(error)) from error

        if errors:
            raise ConnectionManagerError(
                "Invalid connection: " + "; ".join(errors)
            )

        connection = {
            "source": {
                "component_id": source_component_id,
                "pin_id": source_pin_id,
            },
            "target": {
                "component_id": target_component_id,
                "pin_id": target_pin_id,
            },
        }

        if connection in self.connections:
            raise ConnectionManagerError(
                "This connection already exists."
            )

        self.connections.append(connection)

        return connection

    def remove_connection(
        self,
        source_component_id,
        source_pin_id,
        target_component_id,
        target_pin_id,
    ):
        """Remove an existing connection."""

        for connection in self.connections:
            source = connection["source"]
            target = connection["target"]

            if (
                source["component_id"] == source_component_id
                and source["pin_id"] == source_pin_id
                and target["component_id"] == target_component_id
                and target["pin_id"] == target_pin_id
            ):
                self.connections.remove(connection)
                return True

        return False

    def get_connections(self):
        """Return all registered connections."""

        return list(self.connections)

    def count(self):
        """Return the total number of connections."""

        return len(self.connections)

    def to_dict(self):
        """Return the complete wiring configuration as a dictionary."""

        return {
            "schema_version": "1.0",
            "connections": self.get_connections(),
        }

    def save_json(self, file_path):
        """Export the wiring configuration to a JSON file."""

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as file:
            json.dump(
                self.to_dict(),
                file,
                indent=4,
            )

        return path


if __name__ == "__main__":
    from src.registry import ComponentRegistry

    registry = ComponentRegistry()
    registry.load_all()

    manager = ConnectionManager(registry)

    try:
        manager.add_connection(
            "SENSOR_ULTRASONIC_GENERIC",
            "ECHO",
            "MCU_STM32F407",
            "PA0",
        )

        manager.add_connection(
            "MCU_STM32F407",
            "PB0",
            "ACTUATOR_SERVO_GENERIC",
            "SIGNAL",
        )

        output_path = manager.save_json(
            "output/wiring_config.json"
        )

        print("Wiring configuration created successfully!")
        print(f"Total connections: {manager.count()}")
        print(f"Exported to: {output_path}")

    except ConnectionManagerError as error:
        print(f"Connection error: {error}")
