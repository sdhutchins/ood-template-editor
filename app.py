from flask import Flask, render_template, jsonify, request, abort
import os
import re
from typing import List, Dict

from jinja2 import Environment, BaseLoader, StrictUndefined, TemplateError

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "script_templates")

# Roots that are available in the "Save to..." dialog:
# - The user's home directory
# - Optionally, another root directory specified via TEMPLATE_EDITOR_ROOT
HOME_DIR = os.path.expanduser("~")
CONFIG_ROOT = os.environ.get("TEMPLATE_EDITOR_ROOT")

ROOTS: List[Dict[str, str]] = [
    {"id": "home", "label": "Home directory", "path": os.path.realpath(HOME_DIR)},
]

if CONFIG_ROOT:
    ROOTS.append(
        {
            "id": "configured",
            "label": "Configured root",
            "path": os.path.realpath(CONFIG_ROOT),
        }
    )

ALLOWED_ROOT_PATHS = [root["path"] for root in ROOTS]

jinja_env = Environment(loader=BaseLoader(), undefined=StrictUndefined)


def is_subpath(path: str, parent: str) -> bool:
    """Return True if path is inside parent (or equal)."""
    path_real = os.path.realpath(path)
    parent_real = os.path.realpath(parent)
    try:
        common = os.path.commonpath([path_real, parent_real])
    except ValueError:
        return False
    return common == parent_real


def is_allowed_path(path: str) -> bool:
    """Return True if the path is under any allowed root."""
    return any(is_subpath(path, root) for root in ALLOWED_ROOT_PATHS)


def extract_jinja_variables(template_text: str) -> List[str]:
    """
    Extract simple Jinja-style variables like {{ variable_name }} from the template.

    This is intentionally conservative and only supports simple identifiers.
    """
    pattern = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")
    vars_found = sorted(set(pattern.findall(template_text)))
    return vars_found


def safe_filename(name: str) -> bool:
    """Very basic filename validation."""
    if not name or name.strip() == "":
        return False
    # Disallow path separators and traversal
    if "/" in name or "\\" in name or ".." in name:
        return False
    return True


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/templates", methods=["GET"])
def list_templates():
    """Return list of available bash script templates."""
    templates: List[Dict[str, str]] = []
    if os.path.isdir(TEMPLATE_DIR):
        for entry in sorted(os.listdir(TEMPLATE_DIR)):
            if entry.startswith("."):
                continue
            if not (
                entry.endswith(".sh")
                or entry.endswith(".bash")
                or entry.endswith(".sh.j2")
            ):
                continue
            templates.append({"id": entry, "label": entry})
    return jsonify({"templates": templates})


@app.route("/api/template/<name>", methods=["GET"])
def get_template(name: str):
    """Return the content of a specific template and the variables in it."""
    if "/" in name or "\\" in name or ".." in name:
        abort(400, description="Invalid template name")

    template_path = os.path.join(TEMPLATE_DIR, name)
    if not os.path.isfile(template_path):
        abort(404, description="Template not found")

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        abort(500, description="Failed to read template")

    variables = extract_jinja_variables(content)
    return jsonify({"name": name, "content": content, "variables": variables})


@app.route("/api/roots", methods=["GET"])
def get_roots():
    """Return the roots that can be used in the save dialog."""
    return jsonify({"roots": ROOTS})


@app.route("/api/list_dir", methods=["GET"])
def api_list_dir():
    """
    List a directory for the pseudo file dialog.

    Query params:
      - path: absolute path to list; if omitted, defaults to the first root.
    """
    path = request.args.get("path")
    if not path:
        # default to first root path
        if not ROOTS:
            abort(500, description="No roots configured")
        path = ROOTS[0]["path"]

    path_real = os.path.realpath(path)
    if not is_allowed_path(path_real):
        abort(400, description="Path is not under an allowed root")

    if not os.path.isdir(path_real):
        abort(400, description="Path is not a directory")

    # Determine which root this directory belongs to so we can compute a parent
    root_for_path = None
    for root in ROOTS:
        if is_subpath(path_real, root["path"]):
            root_for_path = root
            break

    if root_for_path is None:
        abort(400, description="Path is not under a known root")

    entries = []
    try:
        with os.scandir(path_real) as it:
            for entry in it:
                if entry.name.startswith("."):
                    continue
                entry_type = "dir" if entry.is_dir() else "file"
                entries.append(
                    {
                        "name": entry.name,
                        "path": entry.path,
                        "type": entry_type,
                    }
                )
    except OSError:
        abort(500, description="Failed to list directory")

    # Sort: directories first, then files, alphabetically
    entries.sort(key=lambda e: (e["type"] != "dir", e["name"].lower()))

    # Compute parent, but don't go above the root
    parent = None
    if os.path.realpath(path_real) != root_for_path["path"]:
        potential_parent = os.path.dirname(path_real)
        if is_subpath(potential_parent, root_for_path["path"]):
            parent = potential_parent

    return jsonify(
        {
            "path": path_real,
            "entries": entries,
            "parent": parent,
            "root": root_for_path,
        }
    )


@app.route("/api/render", methods=["POST"])
def api_render():
    """
    Render a template string with the provided variables using Jinja2.

    Body (JSON):
      - template: string
      - variables: object (mapping from name to value)
    """
    data = request.get_json(silent=True) or {}
    template_text = data.get("template", "")
    variables = data.get("variables") or {}

    if not isinstance(variables, dict):
        abort(400, description="variables must be an object")

    try:
        tmpl = jinja_env.from_string(template_text)
        rendered = tmpl.render(**variables)
    except TemplateError as exc:
        abort(400, description=f"Template rendering error: {exc}")

    return jsonify({"rendered": rendered})


@app.route("/api/save", methods=["POST"])
def api_save():
    """
    Save the rendered script to a file under an allowed root.

    Body (JSON):
      - directory: absolute directory path (must be under an allowed root)
      - filename: file name only (no path separators)
      - content: text to save
    """
    data = request.get_json(silent=True) or {}
    directory = data.get("directory")
    filename = data.get("filename")
    content = data.get("content", "")

    if not directory or not filename:
        abort(400, description="directory and filename are required")

    directory_real = os.path.realpath(directory)
    if not is_allowed_path(directory_real):
        abort(400, description="Directory is not under an allowed root")

    if not safe_filename(filename):
        abort(400, description="Invalid filename")

    try:
        os.makedirs(directory_real, exist_ok=True)
    except OSError:
        abort(500, description="Failed to create directory")

    file_path = os.path.join(directory_real, filename)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError:
        abort(500, description="Failed to save file")

    return jsonify({"status": "ok", "path": file_path})


if __name__ == "__main__":
    app.run(debug=True)
