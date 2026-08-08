import unittest

from bluedot_agent.bluedot import BlueDotAdapter


class BlueDotParserTest(unittest.TestCase):
    def test_parse_result_accepts_dynamic_slider_set(self):
        adapter = BlueDotAdapter()

        result = adapter._parse_result(
            {
                "lines": [
                    "Belle Anette",
                    "Scalcairn",
                    "Mood",
                    "Density",
                    "Energy",
                    "Gravity",
                    "Ensemble",
                    "Melody",
                    "Tension",
                    "Rhythm",
                    "Album",
                    "Scalcairn",
                    "Published",
                    "11/27/2020",
                    "Key",
                    "Db",
                    "BPM",
                    "120",
                    "Stem Files",
                    "4",
                    "Publisher",
                    "Blue Dot Studios",
                ],
                "sliders": {
                    "Mood": None,
                    "Density": None,
                    "Energy": None,
                    "Gravity": None,
                    "Ensemble": None,
                    "Melody": None,
                    "Tension": None,
                    "Rhythm": None,
                },
                "chips": ["Folk", "Classical Guitar", "Dulcimer", "Harp", "Strings"],
                "url": None,
            }
        )

        self.assertEqual(result.title, "Belle Anette")
        self.assertEqual(result.subtitle, "Scalcairn")
        self.assertEqual(result.album, "Scalcairn")
        self.assertEqual(result.key, "Db")
        self.assertEqual(result.bpm, "120")
        self.assertEqual(result.stem_files, "4")
        self.assertEqual(result.publisher, "Blue Dot Studios")
        self.assertEqual(
            set(result.sliders),
            {
                "mood",
                "density",
                "energy",
                "gravity",
                "ensemble",
                "melody",
                "tension",
                "rhythm",
            },
        )
        self.assertEqual(result.tags, ["Folk"])
        self.assertEqual(result.instruments, ["Classical Guitar", "Dulcimer", "Harp", "Strings"])

    def test_parse_result_allows_partial_slider_set(self):
        adapter = BlueDotAdapter()

        result = adapter._parse_result(
            {
                "lines": [
                    "Heavenstill",
                    "Scalcairn",
                    "Mood",
                    "Density",
                    "Energy",
                    "Gravity",
                    "Ensemble",
                    "Album",
                    "Scalcairn",
                    "Key",
                    "C",
                    "BPM",
                    "1",
                ],
                "sliders": {
                    "Mood": None,
                    "Density": None,
                    "Energy": None,
                    "Gravity": None,
                    "Ensemble": None,
                },
                "chips": ["Folk", "Adventure", "Harp", "Recorder", "Strings"],
                "url": None,
            }
        )

        self.assertEqual(result.title, "Heavenstill")
        self.assertEqual(set(result.sliders), {"mood", "density", "energy", "gravity", "ensemble"})
        self.assertEqual(result.tags, ["Folk", "Adventure"])
        self.assertEqual(result.instruments, ["Harp", "Recorder", "Strings"])

    def test_api_slider_range_uses_observed_bluedot_scale(self):
        self.assertEqual(BlueDotAdapter._api_slider_range((1, 5)), (0, 9))
        self.assertEqual(BlueDotAdapter._api_slider_range((2, 4)), (2, 7))
        self.assertEqual(BlueDotAdapter._api_slider_range((3, 3)), (5, 5))

    def test_api_filters_include_advanced_sliders_and_duration(self):
        adapter = BlueDotAdapter()
        filters = adapter._api_filters(
            intent=type(
                "Intent",
                (),
                {
                    "length": None,
                    "tags": [],
                    "genres": ["Classical"],
                    "instruments": ["Bassoon"],
                    "keys": [],
                },
            )(),
            requested_sliders={"Mood": (3, 5), "Density": (1, 2), "Tension": (1, 2)},
        )

        self.assertIn({"min": 5, "max": 9, "filterType": "range", "filterName": "Mood"}, filters)
        self.assertIn({"min": 0, "max": 2, "filterType": "range", "filterName": "Density"}, filters)
        self.assertIn({"min": 0, "max": 2, "filterType": "range", "filterName": "Tension"}, filters)
        self.assertIn({"min": 0, "max": 330, "filterType": "range", "filterName": "Duration"}, filters)
        self.assertIn({"filterType": "selectable", "filterName": "instruments", "filterValue": "Bassoon"}, filters)
        self.assertIn(
            {"filterType": "selectable", "filterName": "genres", "filterValue": "Classical"},
            filters,
        )

    def test_api_suggest_parser_accepts_bucket_object(self):
        data = {
            "data": {
                "suggest": {
                    "buckets": [
                        {
                            "key": {"parentTrackId": "parent-1"},
                            "top_tracks": {
                                "hits": {"hits": [{"_source": {"id": "track-1", "title": "Tiella"}}]}
                            },
                        }
                    ]
                }
            }
        }

        results = BlueDotAdapter()._parse_api_suggest_results(data, limit=10)

        self.assertEqual([result.title for result in results], ["Tiella"])

    def test_api_suggest_parser_accepts_flat_hit_list(self):
        data = {
            "data": {
                "suggest": [
                    {"_id": "track-1", "_source": {"id": "track-1", "title": "Tiella"}},
                    {"id": "track-2", "title": "Hensteeth"},
                ]
            }
        }

        results = BlueDotAdapter()._parse_api_suggest_results(data, limit=10)

        self.assertEqual([result.title for result in results], ["Tiella", "Hensteeth"])

    def test_playlist_filter_names_map_length_to_duration(self):
        intent = type(
            "Intent",
            (),
            {"tags": [], "genres": [], "instruments": [], "keys": []},
        )()

        self.assertEqual(
            BlueDotAdapter._playlist_filter_names(
                intent,
                {"Mood": (3, 5), "BPM": (80, 120), "Length": (30, 180)},
            ),
            ["Mood", "BPM", "Duration"],
        )


if __name__ == "__main__":
    unittest.main()
