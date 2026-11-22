import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.match_benchmark import DEFAULT_ENGINE, _summarise


class MatchBenchmarkTests(unittest.TestCase):
    def test_points_use_only_complete_pairs(self):
        pairs = [
            {"games": [{"result": "win"}, {"result": "draw"}]},
            {"games": [{"result": "loss"}, {"result": "unfinished"}]},
        ]
        self.assertEqual(_summarise(pairs), {
            "wins": 1, "draws": 1, "losses": 1, "unfinished": 1,
            "complete_pairs": 1, "points_fraction_in_complete_pairs": 0.75,
        })

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux engine launcher")
    def test_match_runs_both_colours_through_uci(self):
        mate_in_one = "7k/5Q2/6K1/8/8/8/8/8 w - - 0 1"
        with TemporaryDirectory() as temp:
            positions = Path(temp) / "positions.txt"
            positions.write_text(mate_in_one + "\n")
            process = subprocess.run(
                [sys.executable, "-m", "tools.match_benchmark",
                 "--opponent", str(DEFAULT_ENGINE), "--positions", str(positions),
                 "--depth", "1", "--max-plies", "1"],
                cwd=DEFAULT_ENGINE.parents[1], check=True, capture_output=True,
                text=True, timeout=10,
            )
        result = json.loads(process.stdout)
        self.assertEqual(result["results"]["wins"], 1)
        self.assertEqual(result["results"]["losses"], 1)
        self.assertEqual(result["results"]["points_fraction_in_complete_pairs"], 0.5)
        self.assertEqual([engine["moves"] for engine in result["engines"]], [1, 1])
        self.assertEqual([engine["median_reported_depth"] for engine in result["engines"]], [1, 1])
        self.assertEqual([engine["moves_by_reported_depth"] for engine in result["engines"]],
                         [{"1": 1}, {"1": 1}])
        self.assertTrue(all(game["termination"] == "checkmate" for game in result["pairs"][0]["games"]))
