const form = document.getElementById("pks-form");
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const fileLabel = document.getElementById("file-label");
const status = document.getElementById("status");
const previewButton = document.getElementById("preview-button");
const editCard = document.getElementById("edit-card");
const saveForm = document.getElementById("save-form");
const itemSummary = document.getElementById("item-summary");

let draft = null;

function showSelectedFile(file) {
  dropzone.classList.toggle("has-file", Boolean(file));
  fileLabel.textContent = file ? file.name : "PDF tariff book or Excel catalog";
}

function assignFile(file) {
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;
  showSelectedFile(file);
}

fileInput.addEventListener("change", () => showSelectedFile(fileInput.files[0]));
["dragenter", "dragover"].forEach((name) => {
  dropzone.addEventListener(name, (event) => {
    event.preventDefault();
    dropzone.classList.add("is-dragging");
  });
});
["dragleave", "drop"].forEach((name) => {
  dropzone.addEventListener(name, (event) => {
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
    status.textContent = "Choose or drop a PKS file first.";
    return;
  }
  previewButton.disabled = true;
  status.classList.remove("is-error");
  status.textContent = "Extracting catalog…";
  try {
    const response = await fetch("/api/agreements/preview", {
      method: "POST",
      body: new FormData(form),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.detail || "Preview failed");
    }
    draft = body;
    ["group_name", "branch_name", "city", "code", "address", "effective_date"].forEach((key) => {
      document.getElementById(key).value = body[key] || "";
    });
    document.getElementById("aliases").value = (body.aliases || []).join(", ");
    itemSummary.textContent = body.item_count + " tariff rows extracted via " + body.method + ".";
    editCard.hidden = false;
    status.textContent = "Review hospital details, then save.";
  } catch (error) {
    status.classList.add("is-error");
    status.textContent = String(error.message || error);
  } finally {
    previewButton.disabled = false;
  }
});

saveForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!draft) return;
  const aliases = document.getElementById("aliases").value.split(",").map((part) => part.trim()).filter(Boolean);
  const payload = {
    ...draft,
    group_name: document.getElementById("group_name").value,
    branch_name: document.getElementById("branch_name").value,
    city: document.getElementById("city").value,
    code: document.getElementById("code").value,
    address: document.getElementById("address").value,
    effective_date: document.getElementById("effective_date").value,
    aliases,
  };
  status.classList.remove("is-error");
  status.textContent = "Saving…";
  try {
    const response = await fetch("/api/agreements", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Save failed");
    status.textContent = "Saved branch " + body.branch_name + " with " + body.item_count + " items. Open PKS data to browse the rows.";
  } catch (error) {
    status.classList.add("is-error");
    status.textContent = String(error.message || error);
  }
});
