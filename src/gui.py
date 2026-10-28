"""Desktop GUI for selecting assets, previewing, and creating product images."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Callable, Optional, Tuple

from PIL import Image, ImageTk

from src.composer.render import (
    clamp_position,
    create_product_image,
    fit_product_to_template,
)
from src.post_generator import (
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_URL,
    OllamaError,
    generate_social_post,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = PROJECT_ROOT / "config" / "gui_state.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "assets" / "output" / "final-product.jpg"
DEFAULT_PREVIEW_SIZE = (720, 480)


class ImageComposerApp:
    """Tkinter application for the product-image creation workflow."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Social Post Image Composer")
        self.root.minsize(900, 900)

        self.template_var = tk.StringVar()
        self.product_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(DEFAULT_OUTPUT))
        self.scale_var = tk.DoubleVar(value=1.0)
        self.scale_label_var = tk.StringVar(value="100%")
        self.status_var = tk.StringVar(value="Choose a template and product image.")
        self.ollama_url_var = tk.StringVar(value=DEFAULT_OLLAMA_URL)
        self.ollama_model_var = tk.StringVar(value=DEFAULT_OLLAMA_MODEL)
        self.language_var = tk.StringVar(value="English")
        self.post_status_var = tk.StringVar(value="Paste product information and generate a post.")
        self.generate_button: Optional[ttk.Button] = None
        self.product_info_text: Optional[ScrolledText] = None
        self.post_output_text: Optional[ScrolledText] = None
        self.preview_image: Optional[ImageTk.PhotoImage] = None
        self.template_size: Optional[Tuple[int, int]] = None
        self.product_size: Optional[Tuple[int, int]] = None
        self.product_position: Optional[Tuple[int, int]] = None
        self.preview_display_scale = 1.0
        self.preview_offset = (0, 0)
        self.drag_start: Optional[Tuple[int, int]] = None
        self.drag_origin: Optional[Tuple[int, int]] = None

        self._build_layout()
        self._restore_state()
        self._refresh_preview()

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=0)
        self.root.rowconfigure(2, weight=1)

        controls = ttk.LabelFrame(self.root, text="Images", padding=12)
        controls.grid(row=0, column=0, padx=12, pady=12, sticky="ew")
        controls.columnconfigure(1, weight=1)

        self._add_file_row(
            controls,
            row=0,
            label="Template",
            variable=self.template_var,
            command=self._choose_template,
        )
        self._add_file_row(
            controls,
            row=1,
            label="Product image",
            variable=self.product_var,
            command=self._choose_product,
        )
        self._add_file_row(
            controls,
            row=2,
            label="Output",
            variable=self.output_var,
            command=self._choose_output,
        )

        ttk.Label(controls, text="Product size").grid(row=3, column=0, padx=(0, 8), pady=4, sticky="w")
        self.scale_slider = ttk.Scale(
            controls,
            from_=0.25,
            to=2.0,
            variable=self.scale_var,
            command=self._on_scale_changed,
        )
        self.scale_slider.grid(row=3, column=1, padx=(0, 8), pady=4, sticky="ew")
        self.scale_slider.bind("<ButtonRelease-1>", lambda _event: self._save_state())
        ttk.Label(controls, textvariable=self.scale_label_var, width=6).grid(
            row=3, column=2, pady=4, sticky="e"
        )

        actions = ttk.Frame(controls)
        actions.grid(row=4, column=0, columnspan=3, pady=(10, 0), sticky="w")
        ttk.Button(actions, text="Refresh preview", command=self._refresh_preview).pack(side="left")
        ttk.Button(actions, text="Reset position and size", command=self._reset_transform).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(actions, text="Create image", command=self._create_image).pack(side="left", padx=(8, 0))

        self._build_post_generator()

        preview_frame = ttk.LabelFrame(self.root, text="Preview", padding=12)
        preview_frame.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.preview_canvas = tk.Canvas(
            preview_frame,
            width=720,
            height=480,
            background="#333333",
            highlightthickness=0,
        )
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        self.preview_canvas.bind("<Configure>", self._on_preview_configure)
        self.preview_canvas.bind("<ButtonPress-1>", self._on_preview_press)
        self.preview_canvas.bind("<B1-Motion>", self._on_preview_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self._on_preview_release)

        status_frame = ttk.Frame(self.root)
        status_frame.grid(row=3, column=0, sticky="ew")
        status_frame.columnconfigure(0, weight=1)
        ttk.Label(status_frame, textvariable=self.status_var, padding=(12, 0, 12, 8)).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(status_frame, textvariable=self.post_status_var, padding=(12, 0, 12, 8)).grid(
            row=0, column=1, sticky="e"
        )

    def _build_post_generator(self) -> None:
        """Build the local Ollama product-post assistant panel."""
        post_frame = ttk.LabelFrame(self.root, text="AI post generator (local Ollama)", padding=12)
        post_frame.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="ew")
        post_frame.columnconfigure(0, weight=1)
        post_frame.columnconfigure(1, weight=1)
        post_frame.rowconfigure(2, weight=1)

        settings = ttk.Frame(post_frame)
        settings.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)
        ttk.Label(settings, text="Ollama URL").grid(row=0, column=0, padx=(0, 6), sticky="w")
        ttk.Entry(settings, textvariable=self.ollama_url_var, width=25).grid(
            row=0, column=1, padx=(0, 12), sticky="ew"
        )
        ttk.Label(settings, text="Model").grid(row=0, column=2, padx=(0, 6), sticky="w")
        ttk.Entry(settings, textvariable=self.ollama_model_var, width=18).grid(
            row=0, column=3, padx=(0, 12), sticky="ew"
        )
        ttk.Label(settings, text="Language").grid(row=0, column=4, padx=(0, 6), sticky="w")
        ttk.Combobox(
            settings,
            textvariable=self.language_var,
            values=("English", "Spanish", "Source language"),
            state="readonly",
            width=16,
        ).grid(row=0, column=5, padx=(0, 12), sticky="w")
        self.generate_button = ttk.Button(settings, text="Generate post", command=self._generate_post)
        self.generate_button.grid(row=0, column=6, sticky="e")

        ttk.Label(post_frame, text="Product information").grid(row=1, column=0, sticky="w")
        ttk.Label(post_frame, text="Ready-to-publish post").grid(row=1, column=1, sticky="w", padx=(12, 0))

        self.product_info_text = ScrolledText(post_frame, height=9, wrap="word", undo=True)
        self.product_info_text.grid(row=2, column=0, sticky="nsew")
        self.post_output_text = ScrolledText(post_frame, height=9, wrap="word")
        self.post_output_text.grid(row=2, column=1, padx=(12, 0), sticky="nsew")
        self.post_output_text.configure(state="disabled")

        ttk.Label(
            post_frame,
            text="The model extracts one product name, three factual characteristics, and a contact call to action.",
        ).grid(row=3, column=0, columnspan=2, pady=(6, 0), sticky="w")

    def _add_file_row(
        self,
        parent: ttk.LabelFrame,
        row: int,
        label: str,
        variable: tk.StringVar,
        command: Callable[[], None],
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, padx=(0, 8), pady=4, sticky="w")
        entry = ttk.Entry(parent, textvariable=variable, state="readonly")
        entry.grid(row=row, column=1, padx=(0, 8), pady=4, sticky="ew")
        ttk.Button(parent, text="Browse...", command=command).grid(row=row, column=2, pady=4)

    def _choose_template(self) -> None:
        selected = filedialog.askopenfilename(
            title="Choose template image",
            initialdir=str(self._initial_directory(self.template_var.get(), "assets/templates")),
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")],
        )
        if selected:
            self.template_var.set(selected)
            self._reset_transform(save=False)
            self._save_state()
            self._refresh_preview()

    def _choose_product(self) -> None:
        selected = filedialog.askopenfilename(
            title="Choose product image",
            initialdir=str(self._initial_directory(self.product_var.get(), "assets/images/products")),
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")],
        )
        if selected:
            self.product_var.set(selected)
            self._reset_transform(save=False)
            self._save_state()
            self._refresh_preview()

    def _choose_output(self) -> None:
        selected = filedialog.asksaveasfilename(
            title="Choose output image",
            initialfile=Path(self.output_var.get()).name,
            initialdir=str(self._initial_directory(self.output_var.get(), "assets/output")),
            defaultextension=".jpg",
            filetypes=[("JPEG image", "*.jpg"), ("PNG image", "*.png"), ("All files", "*.*")],
        )
        if selected:
            self.output_var.set(selected)
            self._save_state()

    def _refresh_preview(self) -> None:
        canvas_width, canvas_height = self._preview_canvas_size()
        template_path = Path(self.template_var.get())
        product_path = Path(self.product_var.get())
        if not template_path.is_file() or not product_path.is_file():
            self.preview_canvas.delete("all")
            self.preview_canvas.create_text(
                canvas_width // 2,
                canvas_height // 2,
                text="Choose a template and product image.",
                fill="white",
            )
            self.preview_image = None
            self.template_size = None
            self.product_size = None
            return

        try:
            with Image.open(template_path) as template_file, Image.open(product_path) as product_file:
                template = template_file.convert("RGBA")
                product = product_file.convert("RGBA")

            fitted_product = fit_product_to_template(
                template,
                product,
                scale=float(self.scale_var.get()),
            )
            self.template_size = template.size
            self.product_size = fitted_product.size
            if self.product_position is None:
                self.product_position = (
                    (template.width - fitted_product.width) // 2,
                    (template.height - fitted_product.height) // 2,
                )
            self.product_position = clamp_position(
                template.size,
                fitted_product.size,
                self.product_position,
            )
            template.alpha_composite(fitted_product, dest=self.product_position)

            self.preview_display_scale = min(
                1.0,
                canvas_width / template.width,
                canvas_height / template.height,
            )
            display_size = (
                max(1, round(template.width * self.preview_display_scale)),
                max(1, round(template.height * self.preview_display_scale)),
            )
            preview = template.resize(display_size, Image.Resampling.LANCZOS)
            self.preview_image = ImageTk.PhotoImage(preview)
            self.preview_offset = (
                (canvas_width - display_size[0]) // 2,
                (canvas_height - display_size[1]) // 2,
            )
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(
                self.preview_offset[0],
                self.preview_offset[1],
                image=self.preview_image,
                anchor="nw",
            )
            self.scale_label_var.set(f"{float(self.scale_var.get()) * 100:.0f}%")
            self.status_var.set("Drag the product to move it, or use the size slider.")
        except Exception as error:  # noqa: BLE001 - GUI should show readable errors.
            self.preview_canvas.delete("all")
            self.preview_canvas.create_text(
                canvas_width // 2,
                canvas_height // 2,
                text="Unable to preview these files.",
                fill="white",
            )
            self.preview_image = None
            self.status_var.set(str(error))

    def _preview_canvas_size(self) -> Tuple[int, int]:
        """Return the usable canvas size, including a pre-layout fallback."""
        width = self.preview_canvas.winfo_width()
        height = self.preview_canvas.winfo_height()
        if width <= 1 or height <= 1:
            return DEFAULT_PREVIEW_SIZE
        return width, height

    def _on_preview_configure(self, _event: tk.Event) -> None:
        """Keep the preview centered when its canvas is resized."""
        self._refresh_preview()

    def _on_scale_changed(self, value: str) -> None:
        old_size = self.product_size
        old_position = self.product_position
        new_scale = float(value)
        self.scale_label_var.set(f"{new_scale * 100:.0f}%")

        if old_size and old_position:
            old_center = (
                old_position[0] + old_size[0] / 2,
                old_position[1] + old_size[1] / 2,
            )
            new_size = self._get_product_size(new_scale)
            if new_size:
                self.product_position = (
                    round(old_center[0] - new_size[0] / 2),
                    round(old_center[1] - new_size[1] / 2),
                )
        self._refresh_preview()

    def _get_product_size(self, scale: float) -> Optional[Tuple[int, int]]:
        template_path = Path(self.template_var.get())
        product_path = Path(self.product_var.get())
        if not template_path.is_file() or not product_path.is_file():
            return None
        with Image.open(template_path) as template_file, Image.open(product_path) as product_file:
            template = template_file.convert("RGBA")
            product = product_file.convert("RGBA")
        return fit_product_to_template(template, product, scale=scale).size

    def _reset_transform(self, save: bool = True) -> None:
        self.product_position = None
        self.scale_var.set(1.0)
        self.scale_label_var.set("100%")
        if save:
            self._save_state()
        if hasattr(self, "preview_canvas"):
            self._refresh_preview()

    def _on_preview_press(self, event: tk.Event) -> None:
        if not self.product_position or not self.product_size:
            return
        template_x = (event.x - self.preview_offset[0]) / self.preview_display_scale
        template_y = (event.y - self.preview_offset[1]) / self.preview_display_scale
        product_x, product_y = self.product_position
        product_width, product_height = self.product_size
        if product_x <= template_x <= product_x + product_width and product_y <= template_y <= product_y + product_height:
            self.drag_start = (event.x, event.y)
            self.drag_origin = self.product_position
            self.preview_canvas.configure(cursor="fleur")

    def _on_preview_drag(self, event: tk.Event) -> None:
        if not self.drag_start or not self.drag_origin or not self.template_size or not self.product_size:
            return
        delta_x = (event.x - self.drag_start[0]) / self.preview_display_scale
        delta_y = (event.y - self.drag_start[1]) / self.preview_display_scale
        self.product_position = clamp_position(
            self.template_size,
            self.product_size,
            (self.drag_origin[0] + round(delta_x), self.drag_origin[1] + round(delta_y)),
        )
        self._refresh_preview()

    def _on_preview_release(self, _event: tk.Event) -> None:
        if self.drag_start:
            self._save_state()
        self.drag_start = None
        self.drag_origin = None
        self.preview_canvas.configure(cursor="")

    def _create_image(self) -> None:
        template_path = Path(self.template_var.get())
        product_path = Path(self.product_var.get())
        output_path = Path(self.output_var.get())
        if not template_path.is_file() or not product_path.is_file():
            messagebox.showwarning("Missing image", "Choose both a template and a product image first.")
            return

        try:
            created_path = create_product_image(
                template_path,
                product_path,
                output_path,
                position=self.product_position,
                scale=float(self.scale_var.get()),
            )
            self._save_state()
            self.status_var.set(f"Created: {created_path}")
            self._reveal_in_file_explorer(created_path)
        except Exception as error:  # noqa: BLE001 - GUI should show readable errors.
            messagebox.showerror("Image creation failed", str(error))
            self.status_var.set("Image creation failed.")

    def _generate_post(self) -> None:
        """Generate post copy without blocking the Tkinter event loop."""
        if not self.product_info_text or not self.post_output_text or not self.generate_button:
            return
        source_text = self.product_info_text.get("1.0", "end").strip()
        if not source_text:
            messagebox.showwarning("Missing product information", "Paste the product information first.")
            return

        self.generate_button.configure(state="disabled")
        self.post_status_var.set("Generating with Ollama...")
        thread = threading.Thread(
            target=self._generate_post_in_background,
            args=(source_text, self.ollama_model_var.get(), self.ollama_url_var.get(), self.language_var.get()),
            daemon=True,
        )
        thread.start()
        self._save_state()

    def _generate_post_in_background(
        self, source_text: str, model: str, base_url: str, language: str
    ) -> None:
        try:
            post = generate_social_post(
                source_text,
                model=model,
                base_url=base_url,
                language=language,
            )
        except (OllamaError, ValueError) as error:
            self.root.after(0, self._finish_post_generation, None, str(error))
        except Exception as error:  # noqa: BLE001 - surface unexpected local errors in the GUI.
            self.root.after(0, self._finish_post_generation, None, f"Unexpected error: {error}")
        else:
            self.root.after(0, self._finish_post_generation, post, None)

    def _finish_post_generation(self, post: Optional[str], error: Optional[str]) -> None:
        if self.generate_button:
            self.generate_button.configure(state="normal")
        if error:
            self.post_status_var.set("Generation failed.")
            messagebox.showerror("Ollama post generation failed", error)
            return
        if self.post_output_text and post is not None:
            self.post_output_text.configure(state="normal")
            self.post_output_text.delete("1.0", "end")
            self.post_output_text.insert("1.0", post)
            self.post_output_text.configure(state="disabled")
            self._save_state()
        self.post_status_var.set("Post generated. Review it before publishing.")

    def _restore_state(self) -> None:
        state = {}
        if STATE_PATH.is_file():
            try:
                state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                state = {}

        template = state.get("template", "")
        product = state.get("product", "")
        output = state.get("output", str(DEFAULT_OUTPUT))
        if template and Path(template).is_file():
            self.template_var.set(template)
        if product and Path(product).is_file():
            self.product_var.set(product)
        if output:
            self.output_var.set(output)
        self.ollama_url_var.set(state.get("ollama_url", DEFAULT_OLLAMA_URL))
        self.ollama_model_var.set(state.get("ollama_model", DEFAULT_OLLAMA_MODEL))
        self.language_var.set(state.get("language", "English"))
        if self.product_info_text and isinstance(state.get("product_info"), str):
            self.product_info_text.insert("1.0", state["product_info"])
        if self.post_output_text and isinstance(state.get("post_output"), str):
            self.post_output_text.configure(state="normal")
            self.post_output_text.insert("1.0", state["post_output"])
            self.post_output_text.configure(state="disabled")
        try:
            self.scale_var.set(float(state.get("scale", 1.0)))
        except (TypeError, ValueError):
            self.scale_var.set(1.0)
        saved_position = state.get("position")
        if isinstance(saved_position, list) and len(saved_position) == 2:
            try:
                self.product_position = (int(saved_position[0]), int(saved_position[1]))
            except (TypeError, ValueError):
                self.product_position = None

    def _save_state(self) -> None:
        state = {
            "template": self.template_var.get(),
            "product": self.product_var.get(),
            "output": self.output_var.get(),
            "scale": float(self.scale_var.get()),
            "position": list(self.product_position) if self.product_position else None,
            "ollama_url": self.ollama_url_var.get(),
            "ollama_model": self.ollama_model_var.get(),
            "language": self.language_var.get(),
            "product_info": self.product_info_text.get("1.0", "end").strip() if self.product_info_text else "",
            "post_output": self.post_output_text.get("1.0", "end").strip() if self.post_output_text else "",
        }
        try:
            STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except OSError:
            self.status_var.set("Selection saved for this session only.")

    @staticmethod
    def _initial_directory(selected_path: str, fallback: str) -> Path:
        path = Path(selected_path)
        if path.is_file():
            return path.parent
        return PROJECT_ROOT / fallback

    @staticmethod
    def _reveal_in_file_explorer(path: Path) -> None:
        path = path.resolve()
        if sys.platform == "win32":
            subprocess.Popen(["explorer.exe", f"/select,{path}"])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])


def launch_gui() -> None:
    root = tk.Tk()
    ImageComposerApp(root)
    root.mainloop()
