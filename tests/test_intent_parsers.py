import json
import unittest

from bluedot_agent.gemini import GeminiClient, GeminiError
from bluedot_agent.intent import (
    ConfiguredIntentMapper,
    FallbackIntentParser,
    GeminiIntentParser,
    IntentMapper,
    ProviderUnavailableError,
    RuleBasedIntentParser,
)
from bluedot_agent.schema import FilterSchema
from bluedot_agent.settings import ProviderCredentials


class IntentParserTest(unittest.TestCase):
    def setUp(self):
        self.schema = FilterSchema.from_inventory()

    def test_auto_rule_parser_uses_prompt_instead_of_fixed_preset(self):
        mapper = IntentMapper(
            schema=self.schema,
            auto_parser=RuleBasedIntentParser(self.schema),
        )
        calm = mapper.map_prompt("спокойный уютный нарратив", preset_name="auto")
        chase = mapper.map_prompt("динамичный трек под сцену погони", preset_name="auto")
        self.assertNotEqual(calm.sliders, chase.sliders)
        self.assertEqual(chase.tags, ["Chase"])
        self.assertEqual(chase.bpm, (110, 200))

    def test_gemini_uses_header_and_structured_schema(self):
        captured = {}
        response_config = {
            "sliders": {
                "Mood": [3, 5], "Density": [1, 3], "Energy": [2, 4],
                "Gravity": [1, 3], "Ensemble": [1, 3], "Melody": [2, 5],
                "Tension": [1, 2], "Rhythm": [2, 4],
            },
            "tags": ["Quirky"], "genres": ["Classical"],
            "instruments": [], "keys": [],
            "bpm": None, "length": None,
        }

        def transport(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return json.dumps(
                {"candidates": [{"content": {"parts": [{"text": json.dumps(response_config)}]}}]}
            ).encode()

        client = GeminiClient("secret", transport=transport)
        result = client.parse_filters("friendly", self.schema)
        request = captured["request"]
        body = json.loads(request.data.decode())
        prompt_text = body["contents"][0]["parts"][0]["text"]
        self.assertEqual(request.headers["X-goog-api-key"], "secret")
        self.assertNotIn("secret", request.full_url)
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
        self.assertIn("responseJsonSchema", body["generationConfig"])
        self.assertIn("Infer whole meaning, not keywords", prompt_text)
        self.assertNotIn("Interpret meaning holistically", prompt_text)
        self.assertIn("Gravity: light/weightless - heavy/serious", prompt_text)
        self.assertIn("Rhythm: free/subtle pulse - strong/driving pulse", prompt_text)
        self.assertIn(
            "genres",
            body["generationConfig"]["responseJsonSchema"]["properties"],
        )
        self.assertEqual(result["tags"], ["Quirky"])
        self.assertEqual(result["genres"], ["Classical"])

    def test_gemini_schema_omits_large_enum_inventory_rejected_by_api(self):
        captured = {}
        response_config = {
            "sliders": {
                "Mood": [1, 5], "Density": [1, 5], "Energy": [1, 5],
                "Gravity": [1, 5], "Ensemble": [1, 5], "Melody": [1, 5],
                "Tension": [1, 5], "Rhythm": [1, 5],
            },
            "tags": [], "genres": [], "instruments": [], "keys": [],
            "bpm": None, "length": None,
        }

        def transport(request, timeout):
            captured["body"] = json.loads(request.data.decode())
            return json.dumps(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": json.dumps(response_config)}]
                            }
                        }
                    ]
                }
            ).encode()

        GeminiClient(
            "secret",
            model="gemini-3.5-flash-lite",
            transport=transport,
        ).parse_filters("calm", self.schema)
        response_schema = captured["body"]["generationConfig"][
            "responseJsonSchema"
        ]

        self.assertNotIn("enum", json.dumps(response_schema))
        self.assertLess(
            len(json.dumps(response_schema, separators=(",", ":"))),
            3000,
        )

    def test_invalid_gemini_result_falls_back_with_visible_warning(self):
        class BrokenClient:
            def parse_filters(self, prompt, schema):
                raise GeminiError("offline")

        parser = FallbackIntentParser(
            GeminiIntentParser(BrokenClient(), self.schema),
            RuleBasedIntentParser(self.schema),
        )
        mapper = IntentMapper(schema=self.schema, auto_parser=parser)
        result = mapper.map_prompt("вкрадчивый загадочный трек", preset_name="auto")
        self.assertEqual(result.tags, ["Mysterious"])
        self.assertIn("offline", mapper.last_warning or "")

    def test_gemini_first_maps_free_form_meaning_instead_of_local_keyword_rule(self):
        captured_prompt = ""
        response_config = {
            "sliders": {
                "Mood": [2, 5], "Density": [1, 3], "Energy": [1, 4],
                "Gravity": [2, 5], "Ensemble": [2, 5], "Melody": [4, 5],
                "Tension": [1, 4], "Rhythm": [1, 4],
            },
            "tags": [], "genres": ["Celtic"],
            "instruments": [], "keys": [],
            "bpm": None, "length": None,
        }

        def transport(request, timeout):
            nonlocal captured_prompt
            body = json.loads(request.data.decode())
            captured_prompt = body["contents"][0]["parts"][0]["text"]
            return json.dumps(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": json.dumps(response_config)}]
                            }
                        }
                    ]
                }
            ).encode()

        parser = GeminiIntentParser(
            GeminiClient("secret", transport=transport),
            self.schema,
        )
        mapper = IntentMapper(
            schema=self.schema,
            auto_parser=parser,
            gemini_required=True,
        )

        intent = mapper.map_prompt("средневековый вайб", preset_name="auto")

        self.assertIn("средневековый вайб", captured_prompt)
        self.assertEqual(intent.preset_name, "gemini")
        self.assertEqual(intent.genres, ["Celtic"])
        self.assertEqual(intent.sliders["Melody"], (4, 5))
        self.assertNotEqual(intent.genres, ["Folk"])

    def test_rules_compose_new_genre_and_instrument_dimensions(self):
        mapper = IntentMapper(
            schema=self.schema,
            auto_parser=RuleBasedIntentParser(self.schema),
        )

        technology = mapper.map_prompt(
            "уверенное превосходство цифровых технологий",
            preset_name="auto",
        )
        aristocracy = mapper.map_prompt(
            "высокопарная аристократия XVIII века со струнными",
            preset_name="auto",
        )

        self.assertEqual(technology.tags, [])
        self.assertEqual(technology.genres, ["Electro"])
        self.assertEqual(technology.sliders["Energy"], (3, 5))
        self.assertEqual(aristocracy.genres, ["Classical"])
        self.assertEqual(aristocracy.instruments, ["Strings"])
        self.assertEqual(aristocracy.sliders["Melody"], (3, 5))

    def test_rules_interpret_medieval_vibe_instead_of_neutral_search(self):
        mapper = IntentMapper(
            schema=self.schema,
            auto_parser=RuleBasedIntentParser(self.schema),
        )

        intent = mapper.map_prompt("средневековый вайб", preset_name="auto")

        self.assertEqual(intent.genres, ["Folk"])
        self.assertEqual(intent.sliders["Melody"], (3, 5))
        self.assertNotEqual(
            set(intent.sliders.values()),
            {(1, 5)},
            "Recognized prompts must not silently produce a fully neutral search",
        )

    def test_configured_mapper_reads_provider_for_every_request(self):
        class MutableStore:
            current = ProviderCredentials("groq", "first-model", "first-key")

            def credentials(self):
                return self.current

        class Client:
            def __init__(self, provider):
                self.provider = provider

            def parse_filters(self, prompt, schema):
                return {
                    "sliders": {
                        name: [minimum, maximum]
                        for name, (minimum, maximum) in schema.numeric_ranges.items()
                        if name not in {"BPM", "Length"}
                    },
                    "tags": [],
                    "genres": [],
                    "instruments": [],
                    "keys": [],
                    "bpm": None,
                    "length": None,
                }

        calls = []
        store = MutableStore()

        def factory(provider, api_key, model):
            calls.append((provider, api_key, model))
            return Client(provider)

        mapper = ConfiguredIntentMapper(
            store,
            schema=self.schema,
            client_factory=factory,
        )
        first = mapper.map_prompt("first")
        store.current = ProviderCredentials("mistral", "second-model", "second-key")
        second = mapper.map_prompt("second")

        self.assertEqual(first.preset_name, "groq")
        self.assertEqual(second.preset_name, "mistral")
        self.assertEqual(
            calls,
            [
                ("groq", "first-key", "first-model"),
                ("mistral", "second-key", "second-model"),
            ],
        )

    def test_configured_mapper_converts_provider_failure_to_safe_error(self):
        class Store:
            def credentials(self):
                return ProviderCredentials("groq", "model", "secret")

        class BrokenClient:
            calls = 0

            def parse_filters(self, prompt, schema):
                self.calls += 1
                raise GeminiError("secret upstream details")

        client = BrokenClient()
        mapper = ConfiguredIntentMapper(
            Store(),
            schema=self.schema,
            client_factory=lambda provider, api_key, model: client,
        )

        with self.assertRaises(ProviderUnavailableError) as raised:
            mapper.map_prompt("request")
        self.assertNotIn("secret upstream details", str(raised.exception))
        self.assertEqual(client.calls, 2)

    def test_configured_mapper_retries_invalid_provider_result_once(self):
        class Store:
            def credentials(self):
                return ProviderCredentials("gemini", "model", "secret")

        class FlakyClient:
            calls = 0

            def parse_filters(self, prompt, schema):
                self.calls += 1
                if self.calls == 1:
                    return {
                        "sliders": {},
                        "tags": ["not-in-inventory"],
                        "genres": [],
                        "instruments": [],
                        "keys": [],
                        "bpm": None,
                        "length": None,
                    }
                return {
                    "sliders": {"Energy": [4, 5], "Rhythm": [4, 5]},
                    "tags": [],
                    "genres": ["Pop"],
                    "instruments": [],
                    "keys": [],
                    "bpm": [110, 140],
                    "length": None,
                }

        client = FlakyClient()
        mapper = ConfiguredIntentMapper(
            Store(),
            schema=self.schema,
            client_factory=lambda provider, api_key, model: client,
        )

        intent = mapper.map_prompt("молодёжный энергичный")

        self.assertEqual(client.calls, 2)
        self.assertEqual(intent.preset_name, "gemini")
        self.assertEqual(intent.genres, ["Pop"])
        self.assertEqual(intent.sliders["Energy"], (4, 5))

    def test_configured_mapper_discards_repeated_unknown_selectable_values(self):
        class Store:
            def credentials(self):
                return ProviderCredentials("gemini", "model", "secret")

        class Client:
            calls = 0

            def parse_filters(self, prompt, schema):
                self.calls += 1
                return {
                    "sliders": {"Energy": [3, 5], "Rhythm": [3, 5]},
                    "tags": [],
                    "genres": [],
                    "instruments": ["Brass"],
                    "keys": [],
                    "bpm": [100, 150],
                    "length": [60, 180],
                }

        client = Client()
        mapper = ConfiguredIntentMapper(
            Store(),
            schema=self.schema,
            client_factory=lambda provider, api_key, model: client,
        )

        intent = mapper.map_prompt("советский марш")

        self.assertEqual(client.calls, 2)
        self.assertEqual(intent.instruments, [])
        self.assertEqual(intent.sliders["Energy"], (3, 5))
        self.assertIsNone(intent.bpm)

    def test_configured_mapper_enforces_filter_budget(self):
        class Store:
            def credentials(self):
                return ProviderCredentials("mistral", "model", "secret")

        class Client:
            def parse_filters(self, prompt, schema):
                return {
                    "sliders": {
                        "Mood": [2, 5],
                        "Density": [2, 4],
                        "Energy": [2, 4],
                        "Gravity": [2, 4],
                        "Ensemble": [3, 5],
                        "Melody": [3, 5],
                        "Tension": [1, 3],
                        "Rhythm": [2, 4],
                    },
                    "tags": [
                        "Romantic",
                        "Warm",
                        "Whimsical",
                        "Soothing",
                        "Lighthearted",
                    ],
                    "genres": ["Acoustic", "Folk", "Indie"],
                    "instruments": ["Acoustic Guitar", "Piano", "Violin"],
                    "keys": ["C", "G", "F"],
                    "bpm": [80, 120],
                    "length": [120, 300],
                }

        mapper = ConfiguredIntentMapper(
            Store(),
            schema=self.schema,
            client_factory=lambda provider, api_key, model: Client(),
        )

        intent = mapper.map_prompt("романтика на пляже")
        active_sliders = {
            name: value
            for name, value in intent.sliders.items()
            if value != self.schema.numeric_ranges[name]
        }
        selectable_count = sum(
            len(values)
            for values in (
                intent.tags,
                intent.genres,
                intent.instruments,
                intent.keys,
            )
        )

        self.assertLessEqual(len(active_sliders), 4)
        self.assertLessEqual(selectable_count, 1)
        self.assertIsNone(intent.bpm)
        self.assertIsNone(intent.length)

    def test_configured_mapper_keeps_only_explicit_bpm_and_length(self):
        class Store:
            def credentials(self):
                return ProviderCredentials("mistral", "model", "secret")

        class Client:
            def parse_filters(self, prompt, schema):
                return {
                    "sliders": {},
                    "tags": [],
                    "genres": [],
                    "instruments": [],
                    "keys": [],
                    "bpm": [120, 120],
                    "length": [30, 30],
                }

        mapper = ConfiguredIntentMapper(
            Store(),
            schema=self.schema,
            client_factory=lambda provider, api_key, model: Client(),
        )

        implicit = mapper.map_prompt("секретный пляж")
        explicit = mapper.map_prompt("120 BPM, длительность 30 секунд")

        self.assertIsNone(implicit.bpm)
        self.assertIsNone(implicit.length)
        self.assertEqual(explicit.bpm, (120, 120))
        self.assertEqual(explicit.length, (30, 30))

    def test_configured_mapper_applies_filter_budget_before_search(self):
        class Store:
            def credentials(self):
                return ProviderCredentials("groq", "model", "secret")

        class Client:
            def parse_filters(self, prompt, schema):
                return {
                    "sliders": {
                        "Mood": [1, 2],
                        "Density": [3, 5],
                        "Energy": [4, 5],
                        "Gravity": [4, 5],
                        "Ensemble": [3, 5],
                        "Melody": [1, 2],
                        "Tension": [4, 5],
                        "Rhythm": [4, 5],
                    },
                    "tags": ["Suspenseful"],
                    "genres": [],
                    "instruments": [],
                    "keys": [],
                    "bpm": [120, 160],
                    "length": None,
                }

        mapper = ConfiguredIntentMapper(
            Store(),
            schema=self.schema,
            client_factory=lambda provider, api_key, model: Client(),
        )

        intent = mapper.map_prompt("Динамичный напряжённый детектив")

        self.assertEqual(intent.sliders["Mood"], (1, 2))
        self.assertEqual(intent.sliders["Energy"], (4, 5))
        self.assertEqual(intent.sliders["Tension"], (4, 5))
        self.assertEqual(intent.sliders["Rhythm"], (4, 5))
        self.assertEqual(intent.sliders["Density"], (1, 5))
        self.assertEqual(intent.sliders["Gravity"], (1, 5))
        self.assertEqual(intent.sliders["Ensemble"], (1, 5))
        self.assertEqual(intent.sliders["Melody"], (1, 5))
        self.assertIsNone(intent.bpm)
        self.assertEqual(intent.tags, ["Suspenseful"])


if __name__ == "__main__":
    unittest.main()
