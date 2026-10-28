"""Desktop GUI for selecting assets, previewing, and creating product images."""

from __future__ import annotations

import json
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, List, Optional, Tuple

from PIL import Image, ImageTk

from src.composer.render import compose_product_on_template, create_product_image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = PROJECT_ROOT / "config" / "gui_state.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "assets" / "output" / "final-product.jpg"


class ImageComposerApp:
    """Tkinter application for the product-image creation workflow."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Social Post Image Composer")
        self.root.minsize(760, 620)

        self.template_var = tk.StringVar()
        self.product_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(DEFAULT_OUTPUT))
        self.status_var = tk.StringVar(value="Choose a template and product image.")
        self.preview_image: Optional[ImageTk.PhotoImage] = None

        self._build_layout()
        self._restore_state()
        self._refresh_preview()

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

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

        actions = ttk.Frame(controls)
        actions.grid(row=3, column=0, columnspan=3, pady=(10, 0), sticky="w")
        ttk.Button(actions, text="Refresh preview", command=self._refresh_preview).pack(side="left")
        ttk.Button(actions, text="Create image", command=self._create_image).pack(side="left", padx=(8, 0))

        preview_frame = ttk.LabelFrame(self.root, text="Preview", padding=12)
        preview_frame.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.preview_label = tk.Label(
            preview_frame,
            text="Preview will appear here",
            background="#333333",
            foreground="white",
            anchor="center",
        )
        self.preview_label.grid(row=0, column=0, sticky="nsew")

        ttk.Label(self.root, textvariable=self.status_var, padding=(12, 0, 12, 8)).grid(
            row=2, column=0, sticky="w"
        )

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
        template_path = Path(self.template_var.get())
        product_path = Path(self.product_var.get())
        if not template_path.is_file() or not product_path.is_file():
            self.preview_label.configure(image="", text="Choose a template and product image.")
            self.preview_image = None
            return

        try:
            preview = compose_product_on_template(template_path, product_path)
            preview.thumbnail((720, 480), Image.Resampling.LANCZOS)
            self.preview_image = ImageTk.PhotoImage(preview)
            self.preview_label.configure(image=self.preview_image, text="")
            self.status_var.set("Preview updated. Selections are retained.")
        except Exception as error:  # noqa: BLE001 - GUI should show readable errors.
            self.preview_label.configure(image="", text="Unable to preview these files.")
            self.preview_image = None
            self.status_var.set(str(error))

    def _create_image(self) -> None:
        template_path = Path(self.template_var.get())
        product_path = Path(self.product_var.get())
        output_path = Path(self.output_var.get())
        if not template_path.is_file() or not product_path.is_file():
            messagebox.showwarning("Missing image", "Choose both a template and a product image first.")
            return

        try:
            created_path = create_product_image(template_path, product_path, output_path)
            self._save_state()
            self.status_var.set(f"Created: {created_path}")
            self._reveal_in_file_explorer(created_path)
        except Exception as error:  # noqa: BLE001 - GUI should show readable errors.
            messagebox.showerror("Image creation failed", str(error))
            self.status_var.set("Image creation failed.")

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

    def _save_state(self) -> None:
        state = {
            "template": self.template_var.get(),
            "product": self.product_var.get(),
            "output": self.output_var.get(),
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
