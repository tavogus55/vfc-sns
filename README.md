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
├── publisher/          # Social-platform publishing integrations
└── gui.py              # Desktop image-composer interface
tests/                  # Automated tests
main.py                 # Central command-line entry point
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
python main.py render
```

The result is written to `assets/output/final-product.jpg`. To select files
explicitly or leave space around the product image:

```bash
python main.py render \
  --template assets/templates/template.jpg \
  --product assets/images/products/product.jpg \
  --output assets/output/product-post.jpg \
  --margin 40
```

`main.py` is the central process dispatcher. Future commands such as
`publish` can be added as subcommands while keeping their implementation in
the appropriate package under `src/`.

## Desktop GUI

Launch the image-composer interface with:

```bash
python main.py gui
```

The GUI lets you choose a template and product image, preview the centered
result, drag the product within the preview, resize it with the product-size
slider, and create the final image using those exact position and size
settings. The selected paths and transform settings are retained in the
interface and saved locally for the next launch. After creation, the output
file is selected in the system file explorer.

The same GUI includes a local Ollama post generator. Paste a full product
description into the Product information box, choose the Ollama model (the
default is `qwen3:1.7b`), and click Generate post. The assistant returns a
product name, exactly three factual characteristics, and a contact call to
action in a ready-to-publish format. Ollama must be running locally at
`http://localhost:11434` (or change the URL in the panel). The URL and model
can also be configured with the `OLLAMA_URL` and `OLLAMA_MODEL` environment
variables.
