import json
import unittest

from bluedot_agent.llm import (
    OpenAICompatibleClient,
    ProviderRequestError,
    create_client,
)
from bluedot_agent.schema import FilterSchema


RESPONSE_CONFIG = {
    "sliders": {
        "Mood": [2, 5],
        "Density": [1, 3],
        "Energy": [1, 4],
        "Gravity": [2, 5],
        "Ensemble": [2, 5],
        "Melody": [4, 5],
        "Tension": [1, 4],
        "Rhythm": [1, 4],
    },
    "tags": [],
    "genres": ["Celtic"],
    "instruments": [],
    "keys": [],
    "bpm": None,
    "length": None,
}


class ProviderClientTest(unittest.TestCase):
    def setUp(self):
        self.schema = FilterSchema.from_inventory()

    def test_groq_uses_openai_contract_and_structured_output(self):
        captured = {}

        def transport(request, timeout):
            captured["request"] = request
            return json.dumps(
                {"choices": [{"message": {"content": json.dumps(RESPONSE_CONFIG)}}]}
            ).encode()

        client = OpenAICompatibleClient(
            "groq",
            "secret",
            model="openai/gpt-oss-120b",
            transport=transport,
        )

        result = client.parse_filters("средневековый вайб", self.schema)

        request = captured["request"]
        body = json.loads(request.data.decode())
        self.assertEqual(
            request.full_url,
            "https://api.groq.com/openai/v1/chat/completions",
        )
        self.assertEqual(request.headers["Authorization"], "Bearer secret")
        self.assertEqual(request.headers["User-agent"], "BlueDotAgent/0.2")
        self.assertEqual(body["model"], "openai/gpt-oss-120b")
        self.assertEqual(body["response_format"]["type"], "json_schema")
        self.assertTrue(body["response_format"]["json_schema"]["strict"])
        self.assertIn(
            "Infer whole meaning, not keywords",
            body["messages"][0]["content"],
        )
        self.assertNotIn(
            "Interpret meaning holistically",
            body["messages"][0]["content"],
        )
        self.assertEqual(result["genres"], ["Celtic"])

    def test_groq_schema_uses_named_range_bounds(self):
        captured = {}

        def transport(request, timeout):
            captured["body"] = json.loads(request.data.decode())
            return json.dumps(
                {"choices": [{"message": {"content": json.dumps(RESPONSE_CONFIG)}}]}
            ).encode()

        OpenAICompatibleClient(
            "groq",
            "secret",
            model="openai/gpt-oss-120b",
            transport=transport,
        ).parse_filters("request", self.schema)

        response_schema = captured["body"]["response_format"]["json_schema"][
            "schema"
        ]

        def range_schemas(value):
            if isinstance(value, dict):
                if set(value.get("properties", {})) == {"min", "max"}:
                    yield value
                for child in value.values():
                    yield from range_schemas(child)
            elif isinstance(value, list):
                for child in value:
                    yield from range_schemas(child)

        ranges = list(range_schemas(response_schema))
        self.assertEqual(len(ranges), 10)
        self.assertTrue(all(item["type"] == "object" for item in ranges))
        self.assertTrue(all(item["required"] == ["min", "max"] for item in ranges))
        self.assertTrue(all(item["additionalProperties"] is False for item in ranges))

        properties = response_schema["properties"]
        for name in ("tags", "genres", "instruments", "keys"):
            with self.subTest(name=name):
                self.assertEqual(properties[name]["maxItems"], 1)

    def test_groq_prompt_sets_a_quantitative_breadth_target(self):
        captured = {}

        def transport(request, timeout):
            captured["body"] = json.loads(request.data.decode())
            return json.dumps(
                {"choices": [{"message": {"content": json.dumps(RESPONSE_CONFIG)}}]}
            ).encode()

        OpenAICompatibleClient(
            "groq",
            "secret",
            model="openai/gpt-oss-120b",
            transport=transport,
        ).parse_filters("request", self.schema)

        prompt = captured["body"]["messages"][0]["content"]
        self.assertIn("Narrow only 2-4 decisive slider axes", prompt)
        self.assertIn('Set every other slider to {"min":1,"max":5}', prompt)
        self.assertIn("Target small useful result set, not zero matches", prompt)
        self.assertIn("Normally choose no more than one selectable value total", prompt)
        self.assertIn("Allowed values:", prompt)

    def test_groq_decodes_named_range_bounds(self):
        groq_response = {
            **RESPONSE_CONFIG,
            "sliders": {
                name: {"min": value[0], "max": value[1]}
                for name, value in RESPONSE_CONFIG["sliders"].items()
            },
            "bpm": {"min": 90, "max": 140},
        }

        def transport(request, timeout):
            return json.dumps(
                {"choices": [{"message": {"content": json.dumps(groq_response)}}]}
            ).encode()

        result = OpenAICompatibleClient(
            "groq",
            "secret",
            model="openai/gpt-oss-120b",
            transport=transport,
        ).parse_filters("request", self.schema)

        self.assertEqual(result["sliders"]["Energy"], [1, 4])
        self.assertEqual(result["bpm"], [90, 140])

    def test_mistral_prompt_uses_compact_filter_budget_rules(self):
        captured = {}

        def transport(request, timeout):
            captured["body"] = json.loads(request.data.decode())
            return json.dumps(
                {"choices": [{"message": {"content": json.dumps(RESPONSE_CONFIG)}}]}
            ).encode()

        OpenAICompatibleClient(
            "mistral",
            "secret",
            model="mistral-small-latest",
            transport=transport,
        ).parse_filters("романтика на пляже", self.schema)

        prompt = captured["body"]["messages"][0]["content"]
        self.assertIn("2-4 decisive axes only", prompt)
        self.assertIn("Other axes: [1,5]", prompt)
        self.assertIn("One selectable value total", prompt)
        self.assertIn("BPM/Length null unless explicitly requested", prompt)
        self.assertNotIn("Interpret meaning holistically", prompt)

    def test_all_openai_compatible_providers_use_their_own_endpoint(self):
        endpoints = {
            "groq": "https://api.groq.com/openai/v1/chat/completions",
            "openrouter": "https://openrouter.ai/api/v1/chat/completions",
            "mistral": "https://api.mistral.ai/v1/chat/completions",
        }
        for provider, endpoint in endpoints.items():
            with self.subTest(provider=provider):
                captured = {}

                def transport(request, timeout):
                    captured["request"] = request
                    return json.dumps(
                        {
                            "choices": [
                                {
                                    "message": {
                                        "content": json.dumps(RESPONSE_CONFIG)
                                    }
                                }
                            ]
                        }
                    ).encode()

                client = OpenAICompatibleClient(
                    provider,
                    "secret",
                    model="chosen-model",
                    transport=transport,
                )
                client.parse_filters("request", self.schema)
                self.assertEqual(captured["request"].full_url, endpoint)

    def test_factory_supports_every_configured_provider(self):
        for provider in ("gemini", "groq", "openrouter", "mistral"):
            with self.subTest(provider=provider):
                client = create_client(provider, "secret", "chosen-model")
                self.assertTrue(callable(client.parse_filters))

    def test_cerebras_is_not_supported(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            create_client("cerebras", "secret", "gpt-oss-120b")

    def test_invalid_response_is_reported_without_echoing_key(self):
        def transport(request, timeout):
            return b'{"choices":[]}'

        client = OpenAICompatibleClient(
            "groq",
            "do-not-leak",
            model="chosen-model",
            transport=transport,
        )
        with self.assertRaises(ProviderRequestError) as raised:
            client.parse_filters("request", self.schema)
        self.assertNotIn("do-not-leak", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
