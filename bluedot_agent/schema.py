from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .config import load_yaml


class FilterValidationError(ValueError):
    pass


@dataclass(frozen=True)
class FilterSchema:
    numeric_ranges: dict[str, tuple[int, int]]
    selectable_values: dict[str, frozenset[str]]

    @classmethod
    def from_inventory(cls) -> "FilterSchema":
        provider = load_yaml("provider_inventory.yaml")["providers"]["bluedot"]
        numeric: dict[str, tuple[int, int]] = {}
        for name, definition in {
            **provider.get("numeric_sliders", {}),
            **provider.get("range_filters", {}),
        }.items():
            raw_range = definition.get("range") if isinstance(definition, dict) else None
            if not isinstance(raw_range, list) or len(raw_range) != 2:
                raise FilterValidationError(f"Inventory range for {name} is invalid")
            numeric[str(name)] = (int(raw_range[0]), int(raw_range[1]))

        selectable = {
            str(name): frozenset(str(item) for item in values)
            for name, values in provider.get("categorical_filters", {}).items()
        }
        return cls(numeric_ranges=numeric, selectable_values=selectable)

    def validate_range(self, name: str, value: Any) -> tuple[int, int]:
        if name not in self.numeric_ranges:
            raise FilterValidationError(f"Unknown numeric filter: {name}")
        if (
            not isinstance(value, (list, tuple))
            or len(value) != 2
            or isinstance(value[0], bool)
            or isinstance(value[1], bool)
            or not isinstance(value[0], int)
            or not isinstance(value[1], int)
        ):
            raise FilterValidationError(f"{name} must be [min, max] integers")

        minimum, maximum = int(value[0]), int(value[1])
        domain_min, domain_max = self.numeric_ranges[name]
        if minimum > maximum:
            raise FilterValidationError(f"{name} minimum cannot exceed maximum")
        if minimum < domain_min or maximum > domain_max:
            raise FilterValidationError(
                f"{name} must stay within {domain_min}-{domain_max}, got {minimum}-{maximum}"
            )
        return minimum, maximum

    def validate_selectable(self, group: str, values: Any) -> list[str]:
        allowed = self.selectable_values.get(group)
        if allowed is None:
            raise FilterValidationError(f"Unknown selectable filter group: {group}")
        if values is None:
            return []
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise FilterValidationError(f"{group} must be a list of strings")

        duplicates = [value for value, count in Counter(values).items() if count > 1]
        if duplicates:
            raise FilterValidationError(f"Duplicate {group}: {', '.join(duplicates)}")
        unknown = [value for value in values if value not in allowed]
        if unknown:
            raise FilterValidationError(f"Unknown {group}: {', '.join(unknown)}")
        return list(values)

    def validate_configuration(self, config: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(config, dict):
            raise FilterValidationError("Filter configuration must be an object")

        raw_sliders = config.get("sliders") or {}
        if not isinstance(raw_sliders, dict):
            raise FilterValidationError("sliders must be an object")
        sliders = {
            str(name): self.validate_range(str(name), value)
            for name, value in raw_sliders.items()
        }

        bpm = config.get("bpm")
        length = config.get("length")
        return {
            "sliders": sliders,
            "tags": self.validate_selectable("Tags", config.get("tags") or []),
            "genres": self.validate_selectable("Genres", config.get("genres") or []),
            "instruments": self.validate_selectable(
                "Instruments", config.get("instruments") or []
            ),
            "keys": self.validate_selectable("Keys", config.get("keys") or []),
            "bpm": self.validate_range("BPM", bpm) if bpm is not None else None,
            "length": self.validate_range("Length", length) if length is not None else None,
        }

    def json_schema(self) -> dict[str, Any]:
        slider_properties = {
            name: self._range_json_schema(name)
            for name in (
                "Mood",
                "Density",
                "Energy",
                "Gravity",
                "Ensemble",
                "Melody",
                "Tension",
                "Rhythm",
            )
        }
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "sliders": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": slider_properties,
                    "required": list(slider_properties),
                },
                "tags": self._selectable_json_schema("Tags"),
                "genres": self._selectable_json_schema("Genres"),
                "instruments": self._selectable_json_schema("Instruments"),
                "keys": self._selectable_json_schema("Keys"),
                "bpm": {"anyOf": [self._range_json_schema("BPM"), {"type": "null"}]},
                "length": {
                    "anyOf": [self._range_json_schema("Length"), {"type": "null"}]
                },
            },
            "required": [
                "sliders",
                "tags",
                "genres",
                "instruments",
                "keys",
                "bpm",
                "length",
            ],
        }

    def inventory_prompt(self) -> str:
        selectables = {
            group: sorted(values)
            for group, values in self.selectable_values.items()
        }
        return (
            "Numeric filter domains: "
            f"{self.numeric_ranges}. Selectable values: {selectables}. "
            "Tags describe mood, attitude, or musical character; Genres describe musical style; "
            "Instruments describe audible instrumentation; Keys is a supported hidden backend "
            "filter. Use only listed values. Prefer broad numeric filters and empty selectable "
            "lists unless the wording clearly asks for them. Blue Dot combines selectable values "
            "with AND, so use the fewest needed and do not encode the same idea in several groups. "
            "Normally choose one selectable value total; use values from two groups only for two "
            "independent explicit facts, such as Classical music with Strings. "
            "Blue Dot Collections are playlist navigation contexts, not track filters, and must "
            "not be returned."
        )

    def _range_json_schema(self, name: str) -> dict[str, Any]:
        minimum, maximum = self.numeric_ranges[name]
        return {
            "type": "array",
            "prefixItems": [
                {"type": "integer", "minimum": minimum, "maximum": maximum},
                {"type": "integer", "minimum": minimum, "maximum": maximum},
            ],
            "minItems": 2,
            "maxItems": 2,
            "description": f"Inclusive [min, max] for {name}; min must not exceed max.",
        }

    def _selectable_json_schema(self, group: str) -> dict[str, Any]:
        return {
            "type": "array",
            "items": {"type": "string", "enum": sorted(self.selectable_values[group])},
        }
