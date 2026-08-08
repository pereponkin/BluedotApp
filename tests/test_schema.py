import unittest

from bluedot_agent.schema import FilterSchema, FilterValidationError


class FilterSchemaTest(unittest.TestCase):
    def setUp(self):
        self.schema = FilterSchema.from_inventory()

    def test_inventory_contains_every_bluedot_filter(self):
        self.assertEqual(
            set(self.schema.numeric_ranges),
            {
                "Mood",
                "Density",
                "Energy",
                "Gravity",
                "Ensemble",
                "Melody",
                "Tension",
                "Rhythm",
                "BPM",
                "Length",
            },
        )
        self.assertEqual(
            set(self.schema.selectable_values),
            {"Tags", "Genres", "Instruments", "Keys"},
        )

    def test_rejects_reversed_and_out_of_domain_ranges(self):
        with self.assertRaisesRegex(FilterValidationError, "minimum cannot exceed"):
            self.schema.validate_range("Mood", [5, 1])
        with self.assertRaisesRegex(FilterValidationError, "within 1-5"):
            self.schema.validate_range("Energy", [0, 2])

    def test_rejects_unknown_or_duplicate_selectable_values(self):
        with self.assertRaisesRegex(FilterValidationError, "Unknown Tags"):
            self.schema.validate_selectable("Tags", ["Not a real tag"])
        with self.assertRaisesRegex(FilterValidationError, "Duplicate Instruments"):
            self.schema.validate_selectable("Instruments", ["Piano", "Piano"])

    def test_validates_complete_configuration(self):
        result = self.schema.validate_configuration(
            {
                "sliders": {"Mood": [3, 5], "Energy": [1, 2]},
                "tags": ["Curious"],
                "genres": ["Classical"],
                "instruments": ["Piano"],
                "keys": ["C"],
                "bpm": [60, 100],
                "length": [30, 180],
            }
        )
        self.assertEqual(result["sliders"]["Mood"], (3, 5))
        self.assertEqual(result["genres"], ["Classical"])
        self.assertEqual(result["bpm"], (60, 100))


if __name__ == "__main__":
    unittest.main()
