import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fetch_icons import clean_svg


class CleanSvgTest(unittest.TestCase):
    def test_strips_noise_and_preserves_geometry(self):
        svg = (
            '<svg class="icon" style="width:1em" version="1.1" viewBox="0 0 1024 1024">'
            '<path fill="#383838" d="M1 2z"/>'
            '<path fill="none" stroke="#000" d="M3 4z"/>'
            "</svg>"
        )
        out = clean_svg(svg)
        self.assertNotIn("class=", out)
        self.assertNotIn("style=", out)
        self.assertNotIn("version=", out)
        self.assertNotIn('fill="#383838"', out)
        self.assertIn('fill="none"', out)
        self.assertIn('stroke="#000"', out)
        self.assertIn('viewBox="0 0 1024 1024"', out)


if __name__ == "__main__":
    unittest.main()
