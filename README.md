# Template Bash Script Editor (Open OnDemand)

This is a simple Flask-based web app for editing and filling in bash script templates within Open OnDemand.
It lets you pick a template, fill in variables, preview the rendered script, and save it into your home (or another configured) directory.

This app is built on standard Python 3 and Flask and was inspired by
[OSC's OOD Flask example app](https://github.com/OSC/ood-example-flask-app).

## Installation

Create the app directory, clone the repository, and run setup:

```bash
# Create the sandbox apps directory (Open OnDemand scans this location for apps)
mkdir -p /data/user/$USER/ondemand/dev

# Navigate to the sandbox directory
cd /data/user/$USER/ondemand/dev

# Clone the repository (replace <repository-url> with your actual repo URL)
git clone <repository-url> ood-template-editor

# Enter the app directory
cd ood-template-editor

# Run setup to create venv and install dependencies
./setup.sh
```

### Explanation of `setup.sh`

Run `setup.sh` to create a virtual environment and install dependencies. The script also creates `bin/python`, which Passenger uses instead of system Python. This ensures Passenger uses your venv's Python with Flask installed.

## Local Development

This app targets Python 3.11. For local development, run the app in Docker:

```bash
docker compose up --build
```

Open the app at <http://localhost:5001>.

The Docker workflow mounts the repository at `/app` so code changes are visible
inside the container. It also mounts your home directory at `/workspace`, which
is exposed through `TEMPLATE_EDITOR_ROOT` for local file browsing and saves.

## Learn More

- [Open OnDemand Documentation](https://osc.github.io/ood-documentation/latest/)
- [Tutorials for Passenger Apps](https://osc.github.io/ood-documentation/latest/tutorials/tutorials-passenger-apps/)
- [App Development Guide](https://osc.github.io/ood-documentation/latest/how-tos/app-development/)
- [Interactive Apps](https://osc.github.io/ood-documentation/latest/how-tos/app-development/interactive/)
 - [Flask Documentation](https://flask.palletsprojects.com/)
 - [Python Standard Library Reference](https://docs.python.org/3/library/)
