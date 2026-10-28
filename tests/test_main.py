import tempfile
import unittest
from pathlib import Path

from PIL import Image

from main import main


class MainTest(unittest.TestCase):
    def test_render_command_dispatches_to_composer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            template_path = directory / "template.png"
            product_path = directory / "product.png"
            output_path = directory / "output.png"

            Image.new("RGBA", (120, 100), "white").save(template_path)
            Image.new("RGBA", (20, 20), "blue").save(product_path)

            result = main(
                [
                    "render",
                    "--template",
                    str(template_path),
                    "--product",
                    str(product_path),
                    "--output",
                    str(output_path),
                ]
            )

            self.assertEqual(result, 0)
            self.assertTrue(output_path.exists())


if __name__ == "__main__":
    unittest.main()
