import unittest

from parsers.songless_parser import SonglessScoreParser


class DummyAuthor:
    def __init__(self) -> None:
        self.id = 42
        self.name = "Alice"
        self.display_name = "Alice"


class DummyMessage:
    def __init__(self, content: str) -> None:
        self.content = content
        self.author = DummyAuthor()
        self.guild = None


class SonglessParserTest(unittest.TestCase):
    def test_parses_songless_share(self) -> None:
        parser = SonglessScoreParser()
        message = DummyMessage(
            """I found the All song in 0.1 seconds 🤯 [Songless tealblu/trivial#415]

🟩⬛⬛⬛⬛ [All]
🟥🟥🟥🟥🟥 [Rock]

Play Today's Game: https://less.gg/songless"""
        )

        self.assertTrue(parser.can_parse(message))

        response = parser.parse(message)
        self.assertEqual(response.game, "songless")
        self.assertEqual(response.iteration, "415")
        self.assertAlmostEqual(response.score, 0.1)
        self.assertEqual(response.meta["song"], "All")
        self.assertIn("Songless #415", response.description)

    def test_can_parse_share_without_time_string(self) -> None:
        parser = SonglessScoreParser()
        message = DummyMessage(
            """Songless tealblu/trivial#415

🟩⬛⬛⬛⬛ [All]
🟥🟥🟥🟥🟥 [Rock]"""
        )

        self.assertTrue(parser.can_parse(message))
        response = parser.parse(message)
        self.assertEqual(response.iteration, "415")
        self.assertIsNone(response.score)


if __name__ == "__main__":
    unittest.main()
