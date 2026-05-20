// Settings page JavaScript

// Get API URLs from data attributes on the form
function getApiUrls() {
  const form = document.getElementById("settingsForm");
  return {
    settingsUrl: form.dataset.settingsUrl,
    saveSettingsUrl: form.dataset.saveSettingsUrl,
    indexUrl: form.dataset.indexUrl,
  };
}

async function fetchJson(url, options) {
  const response = await fetch(url, options || {});
  if (!response.ok) {
    let msg = "Request failed";
    try {
      const data = await response.json();
      if (data && data.description) {
        msg = data.description;
      } else if (data && data.error) {
        msg = data.error;
      }
    } catch (e) {
      // ignore parse error, fall back to default message
    }
    throw new Error(msg);
  }
  return response.json();
}

async function loadSettings() {
  const urls = getApiUrls();
  try {
    const data = await fetchJson(urls.settingsUrl);
    document.getElementById("additional_root").value = data.additional_root || "";
    document.getElementById("additional_root_label").value = data.additional_root_label || "";
    document.getElementById("additional_template_dirs").value =
      (data.additional_template_dirs || []).join("\n");
    const navbarColor = data.navbar_color || "#e3f2fd";
    document.getElementById("navbar_color").value = navbarColor;
    document.getElementById("navbar_color_preview").style.backgroundColor = navbarColor;
  } catch (err) {
    showError("Failed to load settings: " + err.message);
  }
}

function showError(message) {
  const errorEl = document.getElementById("settingsError");
  errorEl.textContent = message;
  errorEl.style.display = "block";
  document.getElementById("settingsSuccess").style.display = "none";
}

function showSuccess(message) {
  const successEl = document.getElementById("settingsSuccess");
  successEl.textContent = message;
  successEl.style.display = "block";
  document.getElementById("settingsError").style.display = "none";
}

function validatePath(path) {
  const validationEl = document.getElementById("pathValidation");
  if (!path || path.trim() === "") {
    validationEl.style.display = "none";
    return true;
  }
  
  // Basic validation - check if it looks like an absolute path
  if (!path.startsWith("/")) {
    validationEl.innerHTML = '<small class="text-warning">⚠ Path should be absolute (start with /)</small>';
    validationEl.style.display = "block";
    return false;
  }
  
  validationEl.innerHTML = '<small class="text-muted">✓ Path format looks valid</small>';
  validationEl.style.display = "block";
  return true;
}

function validateTemplateDirs(pathsText) {
  const validationEl = document.getElementById("templateDirsValidation");
  const paths = pathsText
    .split(/\r?\n/)
    .map((path) => path.trim())
    .filter((path) => path.length > 0);

  if (paths.length === 0) {
    validationEl.style.display = "none";
    return true;
  }

  const invalidPaths = paths.filter((path) => !path.startsWith("/"));
  if (invalidPaths.length > 0) {
    validationEl.innerHTML =
      '<small class="text-warning">Each template directory must be an absolute path.</small>';
    validationEl.style.display = "block";
    return false;
  }

  validationEl.innerHTML =
    `<small class="text-muted">${paths.length} template director${paths.length === 1 ? "y" : "ies"} ready to validate on save.</small>`;
  validationEl.style.display = "block";
  return true;
}

document.addEventListener("DOMContentLoaded", () => {
  loadSettings();

  const pathInput = document.getElementById("additional_root");
  pathInput.addEventListener("input", () => {
    validatePath(pathInput.value);
  });

  const templateDirsInput = document.getElementById("additional_template_dirs");
  templateDirsInput.addEventListener("input", () => {
    validateTemplateDirs(templateDirsInput.value);
  });

  const navbarColorInput = document.getElementById("navbar_color");
  navbarColorInput.addEventListener("change", function() {
    const color = this.value;
    document.getElementById("navbar_color_preview").style.backgroundColor = color;
  });

  document.getElementById("settingsForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    
    const additionalRoot = pathInput.value.trim();
    const additionalRootLabel = document.getElementById("additional_root_label").value.trim();
    const additionalTemplateDirs = templateDirsInput.value
      .split(/\r?\n/)
      .map((path) => path.trim())
      .filter((path) => path.length > 0);
    const navbarColor = navbarColorInput.value.trim();
    
    if (!validatePath(additionalRoot)) {
      return;
    }
    if (!validateTemplateDirs(templateDirsInput.value)) {
      return;
    }

    const urls = getApiUrls();
    try {
      const data = await fetchJson(urls.saveSettingsUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          additional_root: additionalRoot,
          additional_root_label: additionalRootLabel,
          additional_template_dirs: additionalTemplateDirs,
          navbar_color: navbarColor,
        }),
      });
      showSuccess("Settings saved successfully!");
      // Redirect to editor after a short delay
      setTimeout(() => {
        window.location.href = urls.indexUrl;
      }, 1000);
    } catch (err) {
      showError("Failed to save settings: " + err.message);
    }
  });
});
