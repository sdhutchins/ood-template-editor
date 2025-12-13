"""
Template Bash Script Editor - Flask Application

A simple web-based editor for bash script templates. Users can select templates,
fill in variables, preview rendered scripts, and save them to configured directories.

Structure follows Flask best practices:
- Routes organized by functionality (pages, API endpoints)
- Context processors for template variables
- Error handlers for common HTTP errors
- Settings management via JSON file
"""
from flask import Flask, render_template, jsonify, request, abort
import os
import re
import json
import logging
from datetime import date

from jinja2 import Environment, BaseLoader, StrictUndefined, TemplateError

# Flask app initialization
# Use instance folder for user-specific configuration (Flask best practice)
# Instance folder stores user-specific data that shouldn't be in version control
app = Flask(__name__, instance_relative_config=True)

# ============================================================================
# Configuration and Paths
# ============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "script_templates")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# Instance folder for user-specific settings (Flask best practice)
# Defaults to 'instance' folder in app directory if not set via INSTANCE_PATH
INSTANCE_DIR = app.instance_path
if INSTANCE_DIR is None:
    # Fallback: create instance folder in app directory
    INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
    try:
        os.makedirs(INSTANCE_DIR, exist_ok=True)
    except OSError:
        pass

SETTINGS_FILE = os.path.join(INSTANCE_DIR, "settings.json")

# ============================================================================
# Logging Setup
# ============================================================================

# Basic, light logging setup – logs go to stdout/stderr which Passenger captures.
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

logger = logging.getLogger(__name__)

# File logging to logs/app-YYYY-MM-DD.log (a new file for each day the app starts)
try:
    if not os.path.isdir(LOG_DIR):
        os.makedirs(LOG_DIR)
    log_file_path = os.path.join(LOG_DIR, "app-%s.log" % date.today().isoformat())
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(file_handler)
except Exception:
    # If file logging fails for any reason, continue with stdout/stderr logging only.
    logger.warning("File logging could not be initialized; continuing without app-YYYY-MM-DD.log")

# ============================================================================
# Settings Management
# ============================================================================


def load_settings():
    """
    Load user settings from instance folder (Flask best practice).
    
    Returns dict with default values if file doesn't exist or can't be read.
    Uses JSON format (Python standard library, no extra dependencies).
    """
    defaults = {
        "additional_root": "",
        "navbar_color": "#e3f2fd",
    }
    if os.path.isfile(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
                # Merge with defaults to ensure all keys exist
                defaults.update(settings)
        except (OSError, ValueError) as e:
            logger.warning("Failed to load settings file: %s", e)
    return defaults


def save_settings(settings):
    """
    Save user settings to instance folder (Flask best practice).
    
    Returns True on success, False on failure.
    """
    try:
        # Ensure instance directory exists
        os.makedirs(INSTANCE_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except OSError as e:
        logger.exception("Failed to save settings file: %s", e)
        return False


def get_roots():
    """Get list of allowed root directories from settings and environment."""
    HOME_DIR = os.path.expanduser("~")
    roots = [{"id": "home", "label": "Home directory", "path": os.path.realpath(HOME_DIR)}]
    
    # Check environment variable first (for backward compatibility)
    env_root = os.environ.get("TEMPLATE_EDITOR_ROOT")
    if env_root and os.path.isdir(env_root):
        roots.append({
            "id": "env_root",
            "label": "Environment root",
            "path": os.path.realpath(env_root),
        })
    
    # Check settings file
    settings = load_settings()
    additional_root = settings.get("additional_root", "").strip()
    if additional_root and os.path.isdir(additional_root):
        roots.append({
            "id": "settings_root",
            "label": "Settings root",
            "path": os.path.realpath(additional_root),
        })
    
    return roots

# ============================================================================
# Application Initialization
# ============================================================================

# Whitelisted light navbar colors (value, label)
ALLOWED_NAV_COLORS = [
    ("#e8f5e9", "Mint"),
    ("#e3f2fd", "Light Blue"),
    ("#ffeef3", "Rose Tint"),
    ("#f1f3f5", "Light Gray"),
    ("#ede7f6", "Lavender"),
]

# Initialize roots and allowed paths
ROOTS = get_roots()
ALLOWED_ROOT_PATHS = [root["path"] for root in ROOTS]

# Jinja2 environment for template rendering (separate from Flask's template engine)
jinja_env = Environment(loader=BaseLoader(), undefined=StrictUndefined)

logger.info(
    "Starting Template Bash Script Editor app; TEMPLATE_DIR=%s, ROOTS=%s",
    TEMPLATE_DIR,
    ALLOWED_ROOT_PATHS,
)

# ============================================================================
# Utility Functions
# ============================================================================


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

    This is intentionally conservative and only supports simple identifiers as the
    first token inside the braces. It ignores filters and other syntax that may
    follow the variable name, e.g. {{ user | default('friend') }}.
    """
    # Match {{ variable_name ... }} and capture the first identifier only.
    pattern = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)[^}]*}}")
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


@app.context_processor
def inject_template_vars():
    """Inject variables available to all templates."""
    settings = load_settings()
    navbar_color = settings.get("navbar_color", "#e3f2fd")
    # Validate navbar color is in allowed list
    allowed_values = [color[0] for color in ALLOWED_NAV_COLORS]
    if navbar_color not in allowed_values:
        navbar_color = allowed_values[0]
    return {
        "navbar_color": navbar_color,
        "allowed_nav_colors": ALLOWED_NAV_COLORS,
    }


@app.route("/")
def index():
    """Serve the main template editor page."""
    logger.info("Serving index page from %s", TEMPLATE_DIR)
    return render_template("index.html")


@app.route("/settings")
def settings_page():
    """Serve the settings page."""
    logger.info("Serving settings page")
    return render_template("settings.html")

# ============================================================================
# Routes - API Endpoints
# ============================================================================


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
        # Explicit UTF-8 encoding (Python 3 best practice)
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        logger.exception("Failed to read template file %s", template_path)
        abort(500, description="Failed to read template")

    variables = extract_jinja_variables(content)
    return jsonify({"name": name, "content": content, "variables": variables})


@app.route("/api/roots", methods=["GET"])
def api_get_roots():
    """Return the roots that can be used in the save dialog."""
    # Refresh roots from settings in case they changed
    global ROOTS, ALLOWED_ROOT_PATHS
    ROOTS = get_roots()
    ALLOWED_ROOT_PATHS = [root["path"] for root in ROOTS]
    logger.info("Returning configured roots")
    return jsonify({"roots": ROOTS})


@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    """Return current settings."""
    settings = load_settings()
    return jsonify(settings)


@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    """Save settings."""
    data = request.get_json(silent=True) or {}
    additional_root = data.get("additional_root", "").strip()
    navbar_color = data.get("navbar_color", "#e3f2fd").strip()
    
    # Validate the path if provided
    if additional_root:
        if not os.path.isdir(additional_root):
            abort(400, description="Path is not a valid directory")
        # Normalize the path
        additional_root = os.path.realpath(additional_root)
    
    # Validate navbar color is in allowed list
    allowed_values = [color[0] for color in ALLOWED_NAV_COLORS]
    if navbar_color not in allowed_values:
        # Default to first allowed color if invalid
        logger.warning("Invalid navbar_color '%s', defaulting to '%s'", navbar_color, allowed_values[0])
        navbar_color = allowed_values[0]
    
    settings = {
        "additional_root": additional_root,
        "navbar_color": navbar_color,
    }
    if save_settings(settings):
        # Refresh roots
        global ROOTS, ALLOWED_ROOT_PATHS
        ROOTS = get_roots()
        ALLOWED_ROOT_PATHS = [root["path"] for root in ROOTS]
        logger.info("Settings saved; additional_root=%s, navbar_color=%s", additional_root, navbar_color)
        return jsonify({"status": "ok", "settings": settings})
    else:
        abort(500, description="Failed to save settings")


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
        # Explicit UTF-8 encoding (Python 3 best practice)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError:
        logger.exception("Failed to save file %s", file_path)
        abort(500, description="Failed to save file")

    return jsonify({"status": "ok", "path": file_path})

# ============================================================================
# Error Handlers
# ============================================================================


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    logger.warning("404 error: %s", error)
    # Return JSON for API endpoints, redirect to index for page endpoints
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    # For non-API routes, redirect to index
    from flask import redirect, url_for
    return redirect(url_for("index")), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.exception("500 error: %s", error)
    # Return JSON for API endpoints, simple message for page endpoints
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal server error"}), 500
    # For non-API routes, return a simple error message
    return "<h1>Internal Server Error</h1><p>An error occurred. Please check the logs.</p>", 500


# ============================================================================
# Application Entry Point
# ============================================================================

if __name__ == "__main__":
    app.run(debug=True)
