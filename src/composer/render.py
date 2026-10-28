"""Create a social-media image by centering a product image on a template."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def find_single_image(directory: Path) -> Path:
    """Return the only image in a directory, or raise a useful error."""
    images = sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )

    if not images:
        raise FileNotFoundError(f"No supported image files found in {directory}")
    if len(images) > 1:
        names = ", ".join(path.name for path in images)
        raise ValueError(
            f"More than one image found in {directory}: {names}. "
            "Pass --template and --product explicitly."
        )
    return images[0]


def create_product_image(
    template_path: Path,
    product_path: Path,
    output_path: Path,
    margin: int = 0,
) -> Path:
    """Place a product image in the center of a template.

    The product keeps its aspect ratio and is reduced when it does not fit
    inside the template's available area. Smaller product images are not
    enlarged by default.
    """
    if margin < 0:
        raise ValueError("margin must be zero or greater")

    with Image.open(template_path) as template_file, Image.open(product_path) as product_file:
        template = template_file.convert("RGBA")
        product = product_file.convert("RGBA")

        available_width = template.width - (margin * 2)
        available_height = template.height - (margin * 2)
        if available_width <= 0 or available_height <= 0:
            raise ValueError("margin is too large for the template dimensions")

        scale = min(
            1.0,
            available_width / product.width,
            available_height / product.height,
        )
        if scale < 1.0:
            resized_size = (
                max(1, round(product.width * scale)),
                max(1, round(product.height * scale)),
            )
            product = product.resize(resized_size, Image.Resampling.LANCZOS)

        position = (
            (template.width - product.width) // 2,
            (template.height - product.height) // 2,
        )
        template.alpha_composite(product, dest=position)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_format = "JPEG" if output_path.suffix.lower() in {".jpg", ".jpeg"} else "PNG"
        if output_format == "JPEG":
            template.convert("RGB").save(output_path, format=output_format, quality=95)
        else:
            template.save(output_path, format=output_format)

    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Center a product image on a social-media template."
    )
    parser.add_argument(
        "--template",
        type=Path,
        help="Template image. If omitted, the only image in assets/templates is used.",
    )
    parser.add_argument(
        "--product",
        type=Path,
        help="Product image. If omitted, the only image in assets/images/products is used.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "assets" / "output" / "final-product.jpg",
        help="Output path (default: assets/output/final-product.jpg).",
    )
    parser.add_argument(
        "--margin",
        type=int,
        default=0,
        help="Minimum margin around the product in pixels (default: 0).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    template_path = args.template or find_single_image(PROJECT_ROOT / "assets" / "templates")
    product_path = args.product or find_single_image(PROJECT_ROOT / "assets" / "images" / "products")

    output_path = create_product_image(
        template_path=template_path,
        product_path=product_path,
        output_path=args.output,
        margin=args.margin,
    )
    print(f"Created {output_path}")


if __name__ == "__main__":
    main()

