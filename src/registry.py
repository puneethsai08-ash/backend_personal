from pathlib import Path

from src.validator import (
    load_component,
    validate_component_data,
)


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_COMPONENT_DIR = BASE_DIR / "components"


class RegistryError(Exception):
    """Raised when component registration fails."""


class ComponentRegistry:
    """Loads, validates and manages RoboBench components."""

    def __init__(self, component_dir=None):
        self.component_dir = Path(
            component_dir or DEFAULT_COMPONENT_DIR
        )
        self.components = {}

    def load_all(self):
        """Load and register all YAML component files."""

        if not self.component_dir.exists():
            raise RegistryError(
                f"Component directory not found: {self.component_dir}"
            )

        files = sorted(
            self.component_dir.rglob("*.yaml")
        )

        if not files:
            raise RegistryError(
                f"No YAML component files found in {self.component_dir}"
            )

        self.components.clear()
        errors = []

        for file_path in files:
            try:
                data = load_component(file_path)

                validation_errors = validate_component_data(data)

                if validation_errors:
                    errors.append(
                        f"{file_path.name}: "
                        + "; ".join(validation_errors)
                    )
                    continue

                component = data["component"]
                component_id = component["id"]

                if component_id in self.components:
                    errors.append(
                        f"Duplicate component ID '{component_id}' "
                        f"in file {file_path.name}."
                    )
                    continue

                self.components[component_id] = component

            except Exception as error:
                errors.append(
                    f"{file_path.name}: {error}"
                )

        if errors:
            self.components.clear()
            raise RegistryError(
                "Component registry loading failed:\n- "
                + "\n- ".join(errors)
            )

        return len(self.components)

    def get(self, component_id):
        """Return a component by its unique ID."""

        return self.components.get(component_id)

    def get_all(self):
        """Return all registered components."""

        return list(self.components.values())

    def get_by_category(self, category):
        """Return components belonging to a category."""

        return [
            component
            for component in self.components.values()
            if component.get("category") == category
        ]

    def count(self):
        """Return the total number of registered components."""

        return len(self.components)

    def list_ids(self):
        """Return all registered component IDs."""

        return list(self.components.keys())


if __name__ == "__main__":
    registry = ComponentRegistry()

    try:
        total = registry.load_all()

        print("\nComponent Registry Loaded Successfully!")
        print(f"Total components: {total}")

        for component_id in registry.list_ids():
            component = registry.get(component_id)
            print(
                f"- {component_id} "
                f"({component['category']})"
            )

    except RegistryError as error:
        print(error)
