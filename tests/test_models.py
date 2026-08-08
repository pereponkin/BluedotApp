import unittest

from bluedot_agent.models import BlueDotResult, SearchReport, needs_broader_search


def report(results):
    return SearchReport(
        prompt="x",
        preset_name="cozy_narration",
        applied_sliders={},
        results=results,
    )


class NeedsBroaderSearchTest(unittest.TestCase):
    def test_empty_results_ask_for_a_broader_search(self):
        self.assertTrue(needs_broader_search(report([])))

    def test_no_results_placeholder_counts_as_empty(self):
        placeholder = BlueDotResult(
            title="No results. Related tracks",
            subtitle="Lost Shoe",
        )

        self.assertTrue(needs_broader_search(report([placeholder])))

    def test_a_real_track_is_enough(self):
        track = BlueDotResult(title="Green Legal Pad", subtitle="Transistor Radio")

        self.assertFalse(needs_broader_search(report([track])))

    def test_several_tracks_are_never_broadened(self):
        tracks = [BlueDotResult(title="No results. Related tracks"), BlueDotResult(title="Tiella")]

        self.assertFalse(needs_broader_search(report(tracks)))


if __name__ == "__main__":
    unittest.main()
