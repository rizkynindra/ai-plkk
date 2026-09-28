const form = document.getElementById("convert-form");
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const fileLabel = document.getElementById("file-label");
const status = document.getElementById("status");
const button = document.getElementById("submit-button");

function formatElapsed(seconds) {
  if (seconds < 60) return seconds.toFixed(1) + " s";
  const minutes = Math.floor(seconds / 60);
  const rest = seconds - minutes * 60;
  return minutes + " min " + rest.toFixed(1) + " s";
}

function showSelectedFile(file) {
  if (!file) {
    dropzone.classList.remove("has-file");
    fileLabel.textContent = "PDF, Excel, Word, CSV, or image";
    return;
  }
  dropzone.classList.add("has-file");
  fileLabel.textContent = file.name;
}

function assignFile(file) {
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;
  showSelectedFile(file);
}

fileInput.addEventListener("change", () => {
  showSelectedFile(fileInput.files[0]);
});

["dragenter", "dragover"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.add("is-dragging");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.remove("is-dragging");
  });
});

dropzone.addEventListener("drop", (event) => {
  const file = event.dataTransfer?.files?.[0];
  if (file) assignFile(file);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!fileInput.files[0]) {
    status.classList.add("is-error");
    status.textContent = "Choose or drop a file first.";
    return;
  }
  const started = performance.now();
  button.disabled = true;
  status.classList.remove("is-error");
  const tick = () => {
    const seconds = (performance.now() - started) / 1000;
    status.textContent = "Processing… " + formatElapsed(seconds);
  };
  tick();
  const timer = setInterval(tick, 200);
  try {
    const response = await fetch("/preview", { method: "POST", body: new FormData(form) });
    const body = await response.text();
    clearInterval(timer);
    if (!response.ok) {
      let detail = body;
      try {
        detail = JSON.parse(body).detail || body;
      } catch (error) {}
      status.classList.add("is-error");
      status.textContent =
        "Failed after " + formatElapsed((performance.now() - started) / 1000) + ": " + detail;
      button.disabled = false;
      return;
    }
    document.open();
    document.write(body);
    document.close();
  } catch (error) {
    clearInterval(timer);
    status.classList.add("is-error");
    status.textContent =
      "Failed after " + formatElapsed((performance.now() - started) / 1000) + ": " + error;
    button.disabled = false;
  }
});
