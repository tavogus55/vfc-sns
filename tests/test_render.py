import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.composer.render import create_product_image


class RenderTest(unittest.TestCase):
    def test_product_is_centered_and_keeps_aspect_ratio(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            template_path = directory / "template.png"
            product_path = directory / "product.png"
            output_path = directory / "output.png"

            Image.new("RGBA", (100, 80), "white").save(template_path)
            Image.new("RGBA", (20, 10), "red").save(product_path)

            create_product_image(template_path, product_path, output_path)

            with Image.open(output_path) as result:
                self.assertEqual(result.size, (100, 80))
                self.assertEqual(result.getpixel((40, 35))[:3], (255, 0, 0))
                self.assertEqual(result.getpixel((0, 0))[:3], (255, 255, 255))


if __name__ == "__main__":
    unittest.main()

