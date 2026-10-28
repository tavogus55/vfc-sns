# Social Post Automation

Project scaffold for creating and publishing social media posts from product images and reusable templates.

## Workflow

1. Add source product images to `assets/images/products/`.
2. Keep brand assets such as logos and fonts in `assets/images/brand/`.
3. Store reusable post templates in `assets/templates/`.
4. Compose a final image containing the product image and title.
5. Review generated images in `assets/drafts/`.
6. Publish approved images from `assets/output/` through the configured social platforms.

## Project layout

```text
assets/
├── drafts/             # Local previews awaiting approval (ignored)
├── images/
│   ├── brand/          # Logos, fonts, and other brand assets
│   └── products/       # Source product images
├── output/             # Final generated images (ignored)
└── templates/          # Reusable image templates
config/                 # Non-secret application settings
data/                   # Post metadata, queues, and schedules
logs/                   # Local runtime logs (ignored)
scripts/                # Command-line entry points
src/
├── composer/           # Product-image and title composition
└── publisher/          # Social-platform publishing integrations
tests/                  # Automated tests
```

Secrets belong in a local `.env` file and must never be committed.

## Create a product image

Install the dependency:

```bash
python -m pip install -r requirements.txt
```

When `assets/templates/` and `assets/images/products/` each contain one image,
run:

```bash
python -m src.composer.render
```

The result is written to `assets/output/final-product.jpg`. To select files
explicitly or leave space around the product image:

```bash
python -m src.composer.render \
  --template assets/templates/template.jpg \
  --product assets/images/products/product.jpg \
  --output assets/output/product-post.jpg \
  --margin 40
```
