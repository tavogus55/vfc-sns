"""Central command-line entry point for the social post automation project."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from src.composer.render import create_product_image, find_single_image


PROJECT_ROOT = Path(__file__).resolve().parent


def render_command(args: argparse.Namespace) -> int:
    """Run the product-image renderer."""
    template_path = args.template or find_single_image(
        PROJECT_ROOT / "assets" / "templates"
    )
    product_path = args.product or find_single_image(
        PROJECT_ROOT / "assets" / "images" / "products"
    )

    output_path = create_product_image(
        template_path=template_path,
        product_path=product_path,
        output_path=args.output,
        margin=args.margin,
    )
    print(f"Created {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the central CLI parser.

    Future processes, such as API publishing, should be added as subcommands
    here and implemented in their own package under ``src/``.
    """
    parser = argparse.ArgumentParser(
        description="Automate social-media post creation and publishing."
    )
    subparsers = parser.add_subparsers(dest="command")

    render_parser = subparsers.add_parser(
        "render",
        help="Center a product image on a social-media template.",
    )
    render_parser.add_argument(
        "--template",
        type=Path,
        help="Template image. Defaults to the only image in assets/templates.",
    )
    render_parser.add_argument(
        "--product",
        type=Path,
        help="Product image. Defaults to the only image in assets/images/products.",
    )
    render_parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "assets" / "output" / "final-product.jpg",
        help="Output path (default: assets/output/final-product.jpg).",
    )
    render_parser.add_argument(
        "--margin",
        type=int,
        default=0,
        help="Minimum margin around the product in pixels (default: 0).",
    )
    render_parser.set_defaults(handler=render_command)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Parse arguments and dispatch the selected process.

    Running ``python main.py`` without a command preserves the convenient
    behavior of rendering the default template and product image.
    """
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        arguments = ["render"]

    parser = build_parser()
    args = parser.parse_args(arguments)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 0
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
