function formatElapsed(seconds) {
  if (seconds < 60) return seconds.toFixed(1) + " s";
  const minutes = Math.floor(seconds / 60);
  const rest = seconds - minutes * 60;
  return minutes + " min " + rest.toFixed(1) + " s";
}

function formatIdr(value) {
  if (value === null || value === undefined || value === "") return "";
  return Math.round(Number(value)).toLocaleString("id-ID");
}

function matchLabel(status) {
  if (status === "matched") return "Matched";
  if (status === "price_mismatch") return "Price differs";
  if (status === "ambiguous") return "Ambiguous";
  return "Unmatched";
}

async function fillBranchSelect(select) {
  const response = await fetch("/api/hospitals");
  const rows = await response.json();
  rows.forEach((row) => {
    const option = document.createElement("option");
    option.value = row.branch_id;
    option.textContent = row.branch_name + (row.city ? " · " + row.city : "");
    select.appendChild(option);
  });
  return rows.length;
}

function bindDropzone(dropzone, fileInput, fileLabel, emptyText) {
  function showSelectedFile(file) {
    dropzone.classList.toggle("has-file", Boolean(file));
    fileLabel.textContent = file ? file.name : emptyText;
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
    if (!file) return;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    fileInput.files = transfer.files;
    showSelectedFile(file);
  });
}

function renderCompareRows(tbody, lines) {
  tbody.replaceChildren();
  lines.forEach((line) => {
    const tr = document.createElement("tr");
    const status = line.match_status || "unmatched";
    if (status === "price_mismatch" || status === "unmatched" || status === "ambiguous") {
      tr.className = "review";
    }
    const cells = [
      line.sequence_no,
      line.item_name,
      formatIdr(line.tariff),
      matchLabel(status),
      line.matched_item_name || "",
      formatIdr(line.agreement_tariff),
      line.review_reason || "",
    ];
    cells.forEach((value, index) => {
      const td = document.createElement("td");
      td.textContent = value;
      if (index === 0 || index === 2 || index === 5) td.className = "num";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

const previewRoot = document.getElementById("preview-compare");
const compareForm = document.getElementById("compare-form");

if (previewRoot) {
  const select = document.getElementById("compare-branch");
  const button = document.getElementById("compare-button");
  const status = document.getElementById("compare-status");
  const facts = document.getElementById("compare-facts");
  fillBranchSelect(select).then((count) => {
    if (!count) status.textContent = "Save a PKS catalog first (Upload PKS).";
  });
  button.addEventListener("click", async () => {
    if (!select.value) {
      status.classList.add("is-error");
      status.textContent = "Select a PKS branch.";
      return;
    }
    status.classList.remove("is-error");
    status.textContent = "Comparing…";
    button.disabled = true;
    try {
      const response = await fetch("/api/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          branch_id: Number(select.value),
          conversion_id: previewRoot.dataset.conversionId,
        }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Compare failed");
      renderCompareRows(document.getElementById("compare-body"), body.lines);
      facts.hidden = false;
      facts.innerHTML =
        "<div><span>Matched</span><strong>" +
        body.counts.matched +
        "</strong></div><div><span>Price differs</span><strong>" +
        body.counts.price_mismatch +
        "</strong></div><div><span>Unmatched</span><strong>" +
        body.counts.unmatched +
        "</strong></div>";
      document.getElementById("compare-table").hidden = false;
      status.textContent = "Comparison finished.";
    } catch (error) {
      status.classList.add("is-error");
      status.textContent = String(error.message || error);
    } finally {
      button.disabled = false;
    }
  });
}

if (compareForm) {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const fileLabel = document.getElementById("file-label");
  const select = document.getElementById("branch-select");
  const button = document.getElementById("compare-button");
  const status = document.getElementById("status");
  const facts = document.getElementById("compare-facts");
  const table = document.getElementById("compare-table");
  bindDropzone(dropzone, fileInput, fileLabel, "PDF, Excel, Word, CSV, or image");
  fillBranchSelect(select).then((count) => {
    if (!count) status.textContent = "Save a PKS catalog first (Upload PKS).";
  });
  compareForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!select.value) {
      status.classList.add("is-error");
      status.textContent = "Select a PKS branch.";
      return;
    }
    if (!fileInput.files[0]) {
      status.classList.add("is-error");
      status.textContent = "Drop a claim file first.";
      return;
    }
    const started = performance.now();
    button.disabled = true;
    status.classList.remove("is-error");
    const tick = () => {
      status.textContent = "Extracting… " + formatElapsed((performance.now() - started) / 1000);
    };
    tick();
    const timer = setInterval(tick, 200);
    try {
      const convertResponse = await fetch("/api/convert", {
        method: "POST",
        body: new FormData(compareForm),
      });
      const convertBody = await convertResponse.json();
      if (!convertResponse.ok) throw new Error(convertBody.detail || "Extract failed");
      const compareResponse = await fetch("/api/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          branch_id: Number(select.value),
          lines: convertBody.lines,
        }),
      });
      const compareBody = await compareResponse.json();
      if (!compareResponse.ok) throw new Error(compareBody.detail || "Compare failed");
      clearInterval(timer);
      renderCompareRows(document.getElementById("compare-body"), compareBody.lines);
      facts.hidden = false;
      facts.innerHTML =
        "<div><span>Matched</span><strong>" +
        compareBody.counts.matched +
        "</strong></div><div><span>Price differs</span><strong>" +
        compareBody.counts.price_mismatch +
        "</strong></div><div><span>Unmatched</span><strong>" +
        compareBody.counts.unmatched +
        "</strong></div>";
      table.hidden = false;
      status.textContent =
        "Finished in " +
        formatElapsed((performance.now() - started) / 1000) +
        ". Extracted " +
        convertBody.written_count +
        " billed rows.";
    } catch (error) {
      clearInterval(timer);
      status.classList.add("is-error");
      status.textContent = String(error.message || error);
    } finally {
      button.disabled = false;
    }
  });
}
