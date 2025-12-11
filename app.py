from flask import Flask, render_template, jsonify, request, abort
import os
import re
import logging

from jinja2 import Environment, BaseLoader, StrictUndefined, TemplateError

app = Flask(__name__)

# Basic, light logging setup – logs go to stdout/stderr which Passenger captures.
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "script_templates")

# Roots that are available in the "Save to..." dialog:
# - The user's home directory
# - Optionally, another root directory specified via TEMPLATE_EDITOR_ROOT
HOME_DIR = os.path.expanduser("~")
CONFIG_ROOT = os.environ.get("TEMPLATE_EDITOR_ROOT")

ROOTS = [
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

logger.info(
    "Starting Template Bash Script Editor app; TEMPLATE_DIR=%s, HOME_DIR=%s, ROOTS=%s",
    TEMPLATE_DIR,
    HOME_DIR,
    ALLOWED_ROOT_PATHS,
)


def is_subpath(path, parent):
    """Return True if path is inside parent (or equal), compatible with older Python."""
    path_real = os.path.realpath(path)
    parent_real = os.path.realpath(parent)

    # Exact match is always allowed
    if path_real == parent_real:
        return True

    # Ensure we only match on directory boundaries
    parent_with_sep = parent_real.rstrip(os.sep) + os.sep
    return path_real.startswith(parent_with_sep)


def is_allowed_path(path):
    """Return True if the path is under any allowed root."""
    return any(is_subpath(path, root) for root in ALLOWED_ROOT_PATHS)


def extract_jinja_variables(template_text):
    """
    Extract simple Jinja-style variables like {{ variable_name }} from the template.

    This is intentionally conservative and only supports simple identifiers.
    """
    pattern = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")
    vars_found = sorted(set(pattern.findall(template_text)))
    return vars_found


def safe_filename(name):
    """Very basic filename validation."""
    if not name or name.strip() == "":
        return False
    # Disallow path separators and traversal
    if "/" in name or "\\" in name or ".." in name:
        return False
    return True


@app.route("/")
def index():
    logger.info("Serving index page from %s", TEMPLATE_DIR)
    return render_template("index.html")


@app.route("/api/templates", methods=["GET"])
def list_templates():
    """Return list of available bash script templates."""
    logger.info("Listing templates in %s", TEMPLATE_DIR)
    templates = []
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
def get_template(name):
    """Return the content of a specific template and the variables in it."""
    if "/" in name or "\\" in name or ".." in name:
        logger.warning("Rejected template name %r (invalid)", name)
        abort(400, description="Invalid template name")

    template_path = os.path.join(TEMPLATE_DIR, name)
    logger.info("Loading template %s", template_path)
    if not os.path.isfile(template_path):
        abort(404, description="Template not found")

    try:
        # Use default system encoding for compatibility with older Python
        with open(template_path, "r") as f:
            content = f.read()
    except OSError:
        logger.exception("Failed to read template file %s", template_path)
        abort(500, description="Failed to read template")

    variables = extract_jinja_variables(content)
    return jsonify({"name": name, "content": content, "variables": variables})


@app.route("/api/roots", methods=["GET"])
def get_roots():
    """Return the roots that can be used in the save dialog."""
    logger.info("Returning configured roots")
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
            logger.error("No roots configured; cannot list directory")
            abort(500, description="No roots configured")
        path = ROOTS[0]["path"]

    path_real = os.path.realpath(path)
    logger.info("Listing directory %s", path_real)
    if not is_allowed_path(path_real):
        logger.warning("Rejected directory %s (not under allowed roots)", path_real)
        abort(400, description="Path is not under an allowed root")

    if not os.path.isdir(path_real):
        logger.warning("Path %s is not a directory", path_real)
        abort(400, description="Path is not a directory")

    # Determine which root this directory belongs to so we can compute a parent
    root_for_path = None
    for root in ROOTS:
        if is_subpath(path_real, root["path"]):
            root_for_path = root
            break

    if root_for_path is None:
        logger.warning("No root found for path %s", path_real)
        abort(400, description="Path is not under a known root")

    entries = []
    try:
        for name in os.listdir(path_real):
            if name.startswith("."):
                continue
            entry_path = os.path.join(path_real, name)
            entry_type = "dir" if os.path.isdir(entry_path) else "file"
            entries.append(
                {
                    "name": name,
                    "path": entry_path,
                    "type": entry_type,
                }
            )
    except OSError:
        logger.exception("Failed to list directory %s", path_real)
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
        logger.warning("Invalid variables payload (not a dict): %r", variables)
        abort(400, description="variables must be an object")

    try:
        tmpl = jinja_env.from_string(template_text)
        rendered = tmpl.render(**variables)
        logger.info("Rendered template preview successfully (len=%d)", len(rendered))
    except TemplateError as exc:
        logger.exception("Template rendering error")
        abort(400, description="Template rendering error: %s" % exc)

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
        logger.warning("Save request missing directory or filename: %r", data)
        abort(400, description="directory and filename are required")

    directory_real = os.path.realpath(directory)
    if not is_allowed_path(directory_real):
        logger.warning("Rejected save directory %s (not under allowed roots)", directory_real)
        abort(400, description="Directory is not under an allowed root")

    if not safe_filename(filename):
        logger.warning("Rejected filename %r (invalid or unsafe)", filename)
        abort(400, description="Invalid filename")

    try:
        if not os.path.isdir(directory_real):
            os.makedirs(directory_real)
    except OSError:
        logger.exception("Failed to create directory %s", directory_real)
        abort(500, description="Failed to create directory")

    file_path = os.path.join(directory_real, filename)
    logger.info("Saving script to %s", file_path)

    try:
        # Use default system encoding for compatibility with older Python
        with open(file_path, "w") as f:
            f.write(content)
    except OSError:
        logger.exception("Failed to save file %s", file_path)
        abort(500, description="Failed to save file")

    return jsonify({"status": "ok", "path": file_path})


if __name__ == "__main__":
    app.run(debug=True)
