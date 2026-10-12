const form = document.getElementById("pks-form");
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const fileLabel = document.getElementById("file-label");
const status = document.getElementById("status");
const previewButton = document.getElementById("preview-button");
const editCard = document.getElementById("edit-card");
const saveForm = document.getElementById("save-form");
const itemSummary = document.getElementById("item-summary");
const previewRowCount = document.getElementById("preview-row-count");
const previewElapsed = document.getElementById("preview-elapsed");
const previewBody = document.getElementById("preview-body");
const branchInput = document.getElementById("branch_name");

const TARIFF_HEADERS = [
  "kode_master",
  "kategori_bpjs",
  "hospital_name",
  "nama",
  "group_code",
  "price",
  "price_base",
  "price_final",
  "price_basis",
  "source_page",
];
const MONEY_COLUMNS = new Set(["price", "price_base", "price_final"]);

let draft = null;

function formatElapsed(seconds) {
  if (seconds < 60) return seconds.toFixed(1) + " s";
  const minutes = Math.floor(seconds / 60);
  const rest = seconds - minutes * 60;
  return minutes + " min " + rest.toFixed(1) + " s";
}

function formatIdr(value) {
  if (value === null || value === undefined || value === "") return "";
  const number = Number(value);
  if (Number.isNaN(number)) return "";
  return Math.round(number).toLocaleString("id-ID");
}

function cellText(row, key) {
  if (MONEY_COLUMNS.has(key)) return formatIdr(row[key]);
  if (row[key] === null || row[key] === undefined) return "";
  return String(row[key]);
}

function paintPreview() {
  previewBody.replaceChildren();
  (draft.items || []).forEach((row) => {
    const tr = document.createElement("tr");
    TARIFF_HEADERS.forEach((key) => {
      const td = document.createElement("td");
      td.textContent = cellText(row, key);
      if (MONEY_COLUMNS.has(key)) td.className = "num";
      if (key === "nama") td.className = "nama";
      if (key === "price_basis") td.className = "basis";
      if (key === "hospital_name") td.dataset.hospital = "1";
      tr.appendChild(td);
    });
    previewBody.appendChild(tr);
  });
}

function syncHospitalName() {
  if (!draft) return;
  const name = branchInput.value;
  draft.branch_name = name;
  (draft.items || []).forEach((row) => {
    row.hospital_name = name;
  });
  previewBody.querySelectorAll("[data-hospital]").forEach((cell) => {
    cell.textContent = name;
  });
}

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
  const started = performance.now();
  previewButton.disabled = true;
  status.classList.remove("is-error");
  const tick = () => {
    status.textContent = "Extracting catalog… " + formatElapsed((performance.now() - started) / 1000);
  };
  tick();
  const timer = setInterval(tick, 200);
  try {
    const response = await fetch("/api/agreements/preview", {
      method: "POST",
      body: new FormData(form),
    });
    const body = await response.json();
    clearInterval(timer);
    if (!response.ok) {
      throw new Error(body.detail || "Preview failed");
    }
    draft = body;
    const elapsed = formatElapsed(
      typeof body.elapsed_seconds === "number" ? body.elapsed_seconds : (performance.now() - started) / 1000,
    );
    ["group_name", "branch_name", "city", "code", "address", "effective_date"].forEach((key) => {
      document.getElementById(key).value = body[key] || "";
    });
    document.getElementById("aliases").value = (body.aliases || []).join(", ");
    previewRowCount.textContent = String(body.item_count);
    previewElapsed.textContent = elapsed;
    itemSummary.textContent = body.item_count + " rows extracted in " + elapsed + ". Check the sheet, then save.";
    paintPreview();
    editCard.hidden = false;
    editCard.scrollIntoView({ block: "nearest" });
    status.textContent = "Finished in " + elapsed + ". Extracted rows are below. Save writes this sheet to the catalog.";
  } catch (error) {
    clearInterval(timer);
    status.classList.add("is-error");
    status.textContent =
      "Failed after " + formatElapsed((performance.now() - started) / 1000) + ": " + String(error.message || error);
  } finally {
    clearInterval(timer);
    previewButton.disabled = false;
  }
});

branchInput.addEventListener("input", syncHospitalName);

saveForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!draft) return;
  syncHospitalName();
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
    status.textContent = "Saved " + body.branch_name + " with " + body.item_count + " rows. Open PKS data to see the same sheet.";
  } catch (error) {
    status.classList.add("is-error");
    status.textContent = String(error.message || error);
  }
});
