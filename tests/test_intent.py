import unittest

from bluedot_agent.intent import BlueDotIntent, IntentMapper, broaden_intent


class IntentMapperTest(unittest.TestCase):
    def test_broad_fallback_expands_any_intent_without_changing_selectables(self):
        for source in ("rule_based", "gemini", "chase_scene"):
            with self.subTest(source=source):
                intent = BlueDotIntent(
                    prompt="test",
                    preset_name=source,
                    sliders={"Mood": (3, 5), "Density": (2, 3)},
                    tags=["Chase"],
                    genres=["Soundtrack"],
                    instruments=["Piano"],
                    keys=["C"],
                    bpm=(110, 180),
                    length=(30, 120),
                )

                broad = broaden_intent(intent)

                self.assertEqual(broad.sliders, {"Mood": (2, 5), "Density": (1, 4)})
                self.assertEqual(broad.bpm, (100, 190))
                self.assertEqual(broad.length, (0, 150))
                self.assertEqual(broad.tags, ["Chase"])
                self.assertEqual(broad.genres, ["Soundtrack"])
                self.assertEqual(broad.instruments, ["Piano"])
                self.assertEqual(broad.keys, ["C"])
                self.assertEqual(broad.preset_name, source)

    def test_cozy_narration_maps_to_all_advanced_bluedot_sliders(self):
        intent = IntentMapper().map_prompt(
            "спокойный ненапряжный саундтрек под уютный нарратив",
            preset_name="cozy_narration",
        )

        self.assertEqual(intent.preset_name, "cozy_narration")
        self.assertEqual(
            intent.sliders,
            {
                "Mood": (3, 5),
                "Density": (1, 2),
                "Energy": (1, 2),
                "Gravity": (1, 3),
                "Ensemble": (1, 3),
                "Melody": (2, 4),
                "Tension": (1, 2),
                "Rhythm": (1, 2),
            },
        )
        self.assertEqual(intent.tags, [])
        self.assertEqual(intent.instruments, [])

    def test_broad_cozy_narration_is_less_restrictive(self):
        intent = IntentMapper().map_prompt(
            "спокойный ненапряжный саундтрек под уютный нарратив",
            preset_name="cozy_narration_broad",
        )

        self.assertEqual(intent.sliders["Density"], (1, 3))
        self.assertEqual(intent.sliders["Energy"], (1, 3))
        self.assertEqual(intent.sliders["Tension"], (1, 3))
        self.assertEqual(intent.sliders["Melody"], (1, 5))

    def test_light_cozy_narration_reduces_weight_heuristics(self):
        intent = IntentMapper().map_prompt(
            "спокойный ненапряжный саундтрек под уютный нарратив",
            preset_name="cozy_narration_light",
        )

        self.assertEqual(intent.sliders["Gravity"], (1, 2))
        self.assertEqual(intent.sliders["Ensemble"], (1, 2))
        self.assertEqual(intent.sliders["Density"], (1, 2))
        self.assertEqual(intent.sliders["Energy"], (1, 2))

    def test_chase_scene_maps_to_fast_tense_dense_filters(self):
        intent = IntentMapper().map_prompt(
            "динамичный трек под сцену погони",
            preset_name="chase_scene",
        )

        self.assertEqual(
            intent.sliders,
            {
                "Mood": (2, 5),
                "Density": (3, 5),
                "Energy": (4, 5),
                "Gravity": (3, 5),
                "Ensemble": (3, 5),
                "Melody": (1, 4),
                "Tension": (4, 5),
                "Rhythm": (4, 5),
            },
        )
        self.assertEqual(intent.tags, [])


if __name__ == "__main__":
    unittest.main()
