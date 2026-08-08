import unittest
from io import StringIO
from unittest.mock import patch

from bluedot_agent.diagnostics import NetworkEvent
from bluedot_agent.models import BlueDotResult, SearchReport
from bluedot_agent.reporting import (
    print_network_events,
    print_playlist_report,
    print_search_report,
    print_session_report,
)


def printed(render, *args):
    with patch("sys.stdout", new_callable=StringIO) as output:
        render(*args)
    return output.getvalue()


class ReportPrintingTest(unittest.TestCase):
    def test_search_report_prints_selectable_filters(self):
        report = SearchReport(
            prompt="digital",
            preset_name="rule_based",
            applied_sliders={"Energy": (3, 5)},
            results=[],
            selectable_filters={"Tags": ["Confident"], "Genres": ["Electro"]},
        )

        text = printed(print_search_report, report)

        self.assertIn("Tags: Confident", text)
        self.assertIn("Genres: Electro", text)
        self.assertIn("Energy: 3-5", text)

    def test_every_report_shows_the_same_filters(self):
        report = SearchReport(
            prompt="digital",
            preset_name="rule_based",
            applied_sliders={"Energy": (3, 5)},
            results=[BlueDotResult(title="Tiella")],
            selectable_filters={"Tags": ["Confident"]},
            missing_sliders={"Mood": (1, 2)},
        )

        for render in (print_search_report, print_session_report, print_playlist_report):
            with self.subTest(render=render.__name__):
                text = printed(render, report)
                self.assertIn("Energy: 3-5", text)
                self.assertIn("Tags: Confident", text)
                self.assertIn("Mood: 1-2", text)

    def test_session_report_limits_candidates_to_ten(self):
        report = SearchReport(
            prompt="digital",
            preset_name="rule_based",
            applied_sliders={},
            results=[BlueDotResult(title=f"Track {index}") for index in range(12)],
        )

        text = printed(print_session_report, report)

        self.assertIn("Track 9", text)
        self.assertNotIn("Track 10", text)


class NetworkEventPrintingTest(unittest.TestCase):
    def event(self, post_data=None):
        return NetworkEvent(
            direction="request",
            method="POST",
            resource_type="fetch",
            url="https://api.sessions.blue/graphql",
            status=200,
            post_data=post_data,
        )

    def test_notification_polling_is_left_out(self):
        text = printed(
            print_network_events,
            [self.event(post_data='{"query":"getNotifications"}')],
        )

        self.assertIn("не зафиксированы", text)

    def test_real_traffic_is_printed(self):
        text = printed(print_network_events, [self.event(post_data='{"query":"filter"}')])

        self.assertIn("Network events:", text)
        self.assertIn("api.sessions.blue", text)


if __name__ == "__main__":
    unittest.main()
