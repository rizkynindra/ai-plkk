const CASE = "/api/tarif-review/emc-alam-sutera";
const ZOOMS = [100, 135, 170];

let catalog = null;
let draft = { rows: {} };
let pdfInfo = { opened: false };
let pdfIndex = { hits: {}, order: {} };
let selectedKode = null;
let detailKode = null;
let currentPage = 1;
let zoomIndex = 0;
let dirty = false;
let viewToken = 0;

const reviewStatus = document.getElementById("review-status");
const reviewError = document.getElementById("review-error");
const reviewErrorText = document.getElementById("review-error-text");
const docFacts = document.getElementById("doc-facts");
const extractBody = document.getElementById("extract-body");
const rowSearch = document.getElementById("row-search");
const kategoriFilter = document.getElementById("kategori-filter");
const statusFilter = document.getElementById("status-filter");
const pageScope = document.getElementById("page-scope");
const filterEmpty = document.getElementById("filter-empty");
const rowCount = document.getElementById("row-count");
const pdfStatus = document.getElementById("pdf-status");
const pdfEmpty = document.getElementById("pdf-empty");
const pdfFrame = document.getElementById("pdf-frame");
const pdfImage = document.getElementById("pdf-image");
const pdfMarks = document.getElementById("pdf-marks");
const pageInput = document.getElementById("page-input");
const pageTotal = document.getElementById("page-total");
const pagePrev = document.getElementById("page-prev");
const pageNext = document.getElementById("page-next");
const zoomOut = document.getElementById("zoom-out");
const zoomIn = document.getElementById("zoom-in");
const verifiedPrice = document.getElementById("verified-price");
const reviewNote = document.getElementById("review-note");
const saveStatus = document.getElementById("save-status");
const downloadReview = document.getElementById("download-review");

function formatIdr(value) {
  return Math.round(Number(value)).toLocaleString("id-ID");
}

function parseMoney(value) {
  const text = String(value).trim().replace(/\s/g, "");
  if (!/^\d{1,3}(\.\d{3})*$|^\d+$/.test(text)) return null;
  return Number(text.replace(/\./g, ""));
}

function currentRow() {
  if (!catalog || !selectedKode) return null;
  return catalog.rows.find((row) => row.kode_master === selectedKode) || null;
}

function savedRow(kode) {
  return draft.rows[kode] || null;
}

function pdfPageFor(row) {
  if (!row || !pdfIndex.hits) return null;
  const hit = pdfIndex.hits[row.kode_master];
  return hit ? hit.pdf_page : null;
}

function rowsOnPage(page) {
  const kodes = (pdfIndex.order && pdfIndex.order[String(page)]) || [];
  const byKode = new Map(catalog.rows.map((row) => [row.kode_master, row]));
  return kodes.map((kode) => byKode.get(kode)).filter(Boolean);
}

function firstLocatedPage() {
  const pages = Object.keys(pdfIndex.order || {}).map(Number).filter((page) => page > 0);
  pages.sort((left, right) => left - right);
  return pages[0] || 1;
}

async function readError(response) {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
  } catch (_error) {
    return "Request failed (" + response.status + ").";
  }
  return "Request failed (" + response.status + ").";
}

function visibleRows() {
  const query = rowSearch.value.trim().toLowerCase();
  const kategori = kategoriFilter.value;
  const mode = statusFilter.value;
  const source = pdfInfo.opened && pageScope.value === "page" ? rowsOnPage(currentPage) : catalog.rows;
  return source.filter((row) => {
    if (kategori && row.kategori_bpjs !== kategori) return false;
    const saved = savedRow(row.kode_master);
    const status = saved ? saved.status : "unchecked";
    if (mode !== "all" && status !== mode) return false;
    if (!query) return true;
    const haystack = [row.kode_master, row.nama, row.kategori_bpjs, row.group_code || ""]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
}

function paintFacts() {
  docFacts.hidden = false;
  document.getElementById("fact-workbook").textContent = catalog.workbook;
  const hospital = document.getElementById("fact-hospital");
  const rows = document.getElementById("fact-rows");
  const match = document.getElementById("fact-pages");
  if (!pdfInfo.opened) {
    hospital.textContent = "Open a PDF";
    rows.textContent = "0";
    match.textContent = catalog.hospitals.join(", ");
  } else {
    hospital.textContent = pdfIndex.document_hospital || "Could not read hospital name";
    rows.textContent = String(catalog.row_count);
    if (pdfIndex.hospital_status === "matched") {
      match.textContent = pdfIndex.matched_hospital + " (" + pdfIndex.identity_method + ")";
    } else if (pdfIndex.hospital_status === "no_reference") {
      match.textContent = "No rows for this hospital in the workbook";
    } else {
      match.textContent = "Hospital could not be matched";
    }
  }
  const period = document.getElementById("fact-period");
  if (catalog.period) {
    period.hidden = false;
    period.querySelector("dd").textContent = catalog.period;
  }
  if (!pdfInfo.opened) {
    pdfEmpty.textContent =
      "Open the PKS PDF. The rows beside it list only the lines found on the page you are viewing.";
  }
}

function paintCategories() {
  const current = kategoriFilter.value;
  const names = [...new Set(catalog.rows.map((row) => row.kategori_bpjs))].sort();
  kategoriFilter.replaceChildren(new Option("All categories", ""));
  names.forEach((name) => kategoriFilter.append(new Option(name, name)));
  kategoriFilter.value = names.includes(current) ? current : "";
}

function paintTable(rows) {
  const fragment = document.createDocumentFragment();
  rows.forEach((row) => {
    const saved = savedRow(row.kode_master);
    const tr = document.createElement("tr");
    tr.dataset.kode = row.kode_master;
    tr.tabIndex = row.kode_master === selectedKode ? 0 : -1;
    tr.setAttribute("aria-selected", row.kode_master === selectedKode ? "true" : "false");
    if (row.kode_master === selectedKode) tr.classList.add("is-selected");
    if (saved && saved.status === "corrected") tr.classList.add("review");
    const check = saved ? (saved.status === "corrected" ? "Corrected" : "Matches") : "";
    const values = [
      row.kode_master,
      row.nama,
      null,
      null,
      check,
      row.kategori_bpjs,
      row.group_code || "",
      row.hospital_name,
    ];
    values.forEach((value, index) => {
      const td = document.createElement("td");
      if (index === 1) td.className = "nama";
      if (index === 2 || index === 3) {
        td.className = "num";
        const amount = index === 2 ? row.price_final : row.reference_price;
        td.append(document.createTextNode(formatIdr(amount)));
        if (index === 2 && saved && saved.status === "corrected") {
          const extra = document.createElement("div");
          extra.className = "verified-price";
          extra.textContent = formatIdr(saved.verified_price);
          td.append(extra);
        }
      } else {
        td.textContent = value;
        if (index === 4 && saved && saved.status === "corrected") td.classList.add("check-corrected");
      }
      tr.append(td);
    });
    fragment.append(tr);
  });
  extractBody.replaceChildren(fragment);
  const onThisPage = pdfInfo.opened && pageScope.value === "page";
  filterEmpty.hidden = rows.length > 0;
  filterEmpty.textContent = onThisPage
    ? "No extracted row was found on PDF page " + currentPage + "."
    : "No rows match this filter. Clear the search or choose All categories.";
  if (onThisPage) rowCount.textContent = rows.length + " on this page";
  else if (rows.length === catalog.row_count) rowCount.textContent = catalog.row_count + " rows";
  else rowCount.textContent = rows.length + " of " + catalog.row_count;
}

function paintDetail() {
  const panel = document.getElementById("row-detail");
  const row = currentRow();
  if (!row) {
    panel.hidden = true;
    detailKode = null;
    return;
  }
  panel.hidden = false;
  if (detailKode !== row.kode_master) {
    detailKode = row.kode_master;
    const saved = savedRow(row.kode_master);
    document.getElementById("detail-nama").textContent = row.nama;
    document.getElementById("detail-meta").textContent = [
      row.kode_master,
      row.kategori_bpjs,
      row.hospital_name,
      row.group_code || "no group_code",
    ].join(" · ");
    document.getElementById("detail-price").textContent = formatIdr(row.price_final);
    document.getElementById("detail-reference-price").textContent = formatIdr(row.reference_price);
    document.getElementById("detail-basis").textContent = row.price_basis;
    verifiedPrice.value = formatIdr(saved ? saved.verified_price : row.price_final);
    reviewNote.value = saved ? saved.note || "" : "";
  }
  const saved = savedRow(row.kode_master);
  const located = pdfPageFor(row);
  const cited = row.source_page || "No cited page";
  document.getElementById("detail-page").textContent = located
    ? cited + ". Found on PDF page " + located + "."
    : cited;
  const check = document.getElementById("detail-check");
  if (!saved) check.textContent = "Unchecked against the printed page.";
  else if (saved.status === "matches") check.textContent = "Matches the printed page.";
  else check.textContent = "Corrected to " + formatIdr(saved.verified_price) + ".";
  document.getElementById("clear-check").disabled = !saved;
  document.getElementById("show-cited").disabled = !located;
}

function paintSummary() {
  let matches = 0;
  let corrected = 0;
  catalog.rows.forEach((row) => {
    const saved = savedRow(row.kode_master);
    if (!saved) return;
    if (saved.status === "matches") matches += 1;
    if (saved.status === "corrected") corrected += 1;
  });
  const open = catalog.rows.length - matches - corrected;
  document.getElementById("decision-summary").textContent =
    matches + " match the printed page. " + corrected + " corrected. " + open + " still unchecked.";
}

function paint(options) {
  if (!catalog) return;
  const follow = !options || options.follow !== false;
  const rows = visibleRows();
  let jumped = false;
  if (!rows.some((row) => row.kode_master === selectedKode)) {
    selectedKode = rows[0] ? rows[0].kode_master : null;
    detailKode = null;
    jumped = Boolean(selectedKode);
  }
  paintTable(rows);
  paintDetail();
  paintSummary();
  if (!follow || !jumped || !pdfInfo.opened) return;
  const target = pdfPageFor(currentRow());
  if (target && target !== currentPage) showPage(target);
}

function selectRow(kode, options) {
  const changed = selectedKode !== kode;
  selectedKode = kode;
  if (changed) detailKode = null;
  const target = pdfPageFor(currentRow());
  if (pdfInfo.opened && target && target !== currentPage) showPage(target);
  else {
    paint({ follow: false });
    if (pdfInfo.opened && target === currentPage) refreshMarks();
  }
  const rowElement = extractBody.querySelector(`[data-kode="${CSS.escape(kode)}"]`);
  if (options && options.focus && rowElement) {
    rowElement.focus();
    rowElement.scrollIntoView({ block: "nearest" });
  }
}

function applyZoom() {
  pdfFrame.style.width = ZOOMS[zoomIndex] + "%";
  zoomOut.disabled = zoomIndex === 0;
  zoomIn.disabled = zoomIndex === ZOOMS.length - 1;
}

function setPager() {
  const opened = Boolean(pdfInfo.opened);
  pagePrev.disabled = !opened || currentPage <= 1;
  pageNext.disabled = !opened || currentPage >= Number(pdfInfo.page_count || 0);
  pageTotal.textContent = opened ? "of " + pdfInfo.page_count : "";
}

async function paintMarks(token, page) {
  pdfMarks.replaceChildren();
  const row = currentRow();
  const cited = row && row.page && row.page !== page ? " Workbook cites printed page " + row.page + "." : "";
  if (!row) {
    if (token !== viewToken) return;
    if (pdfIndex.hospital_status === "no_reference") {
      pdfStatus.textContent =
        "Detected " + pdfIndex.document_hospital + ", but the workbook has no reference rows for this hospital.";
    } else if (pdfIndex.hospital_status === "unknown") {
      pdfStatus.textContent =
        "The hospital name could not be read. OCR or the configured vision model is required for scanned PDFs.";
    } else if (pdfIndex.extraction_method === "vision_unavailable") {
      pdfStatus.textContent =
        "The hospital matched, but this scanned PDF needs the configured vision model to extract tariff rows.";
    } else {
      pdfStatus.textContent = "PDF page " + page + " of " + pdfInfo.page_count + ". No tariff row was extracted on this page.";
    }
    return;
  }
  const response = await fetch(
    CASE + "/pdf/pages/" + page + "/marks?kode=" + encodeURIComponent(row.kode_master)
  );
  if (token !== viewToken) return;
  const body = response.ok ? await response.json() : { kind: "none", rects: [] };
  body.rects.forEach((rect) => {
    const box = document.createElement("span");
    box.className = "pdf-mark";
    box.style.left = rect.x * 100 + "%";
    box.style.top = rect.y * 100 + "%";
    box.style.width = rect.w * 100 + "%";
    box.style.height = rect.h * 100 + "%";
    pdfMarks.append(box);
  });
  if (body.kind === "name") {
    pdfStatus.textContent = "PDF page " + page + " of " + pdfInfo.page_count + ". Boxed the extracted name." + cited;
  } else if (body.kind === "price") {
    pdfStatus.textContent =
      "PDF page " + page + " of " + pdfInfo.page_count + ". Boxed the amount. It may appear on more than one line." + cited;
  } else {
    pdfStatus.textContent =
      "PDF page " + page + " of " + pdfInfo.page_count + ". No box: the printed wording does not match the extracted name." + cited;
  }
  const mark = pdfMarks.querySelector(".pdf-mark");
  const stage = document.getElementById("pdf-stage");
  if (!mark || !stage) return;
  const markTop = mark.getBoundingClientRect().top - stage.getBoundingClientRect().top + stage.scrollTop;
  stage.scrollTop = Math.max(0, markTop - stage.clientHeight / 4);
}

function refreshMarks() {
  if (!pdfInfo.opened || !pdfImage.naturalWidth) return;
  paintMarks(++viewToken, currentPage);
}

function showPage(pageNumber) {
  const page = Number(pageNumber);
  if (!pdfInfo.opened) {
    pdfEmpty.hidden = false;
    pdfFrame.hidden = true;
    pdfStatus.textContent = "Open the PKS PDF. A selected row asks for its printed page.";
    setPager();
    return;
  }
  if (!page || page < 1 || page > pdfInfo.page_count) {
    pageInput.value = String(currentPage);
    const pageWord = pdfInfo.page_count === 1 ? "page" : "pages";
    pdfEmpty.hidden = false;
    pdfFrame.hidden = true;
    pdfEmpty.textContent = "Page " + pageNumber + " is outside this PDF.";
    pdfStatus.textContent =
      "This PDF has " +
      pdfInfo.page_count +
      " " +
      pageWord +
      ". Page " +
      pageNumber +
      " is not in the file. Type the PDF page that shows the tariff table.";
    return;
  }
  currentPage = page;
  pageInput.value = String(page);
  setPager();
  applyZoom();
  const staying = currentRow() && pdfPageFor(currentRow()) === page;
  if (!staying) {
    const kode = ((pdfIndex.order && pdfIndex.order[String(page)]) || [])[0];
    if (kode) {
      selectedKode = kode;
      detailKode = null;
    }
  }
  paint({ follow: false });
  const token = ++viewToken;
  const nextSrc = CASE + "/pdf/pages/" + page + "?v=" + pdfInfo.revision;
  pdfStatus.textContent = "Rendering page " + page + "…";
  if (pdfImage.dataset.pageSrc === nextSrc && pdfImage.complete && pdfImage.naturalWidth) {
    pdfEmpty.hidden = true;
    pdfFrame.hidden = false;
    paintMarks(token, page);
    return;
  }
  pdfImage.onload = () => {
    if (token !== viewToken) return;
    pdfEmpty.hidden = true;
    pdfFrame.hidden = false;
    paintMarks(token, page);
  };
  pdfImage.onerror = () => {
    if (token !== viewToken) return;
    pdfStatus.textContent = "Page " + page + " could not be rendered.";
  };
  pdfImage.alt = "PKS page " + page;
  pdfImage.dataset.pageSrc = nextSrc;
  pdfImage.src = nextSrc;
}

function remember(kode, status, verified, note) {
  if (!status) delete draft.rows[kode];
  else draft.rows[kode] = { verified_price: verified, status: status, note: note.trim() };
  dirty = true;
  detailKode = null;
  paint();
}

function captureOpenNote() {
  const row = currentRow();
  if (!row || !draft.rows[row.kode_master]) return;
  draft.rows[row.kode_master].note = reviewNote.value.trim();
}

async function saveDraft() {
  captureOpenNote();
  saveStatus.classList.remove("is-error");
  saveStatus.textContent = "Saving review draft…";
  const response = await fetch(CASE + "/draft", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(draft),
  });
  if (!response.ok) throw new Error(await readError(response));
  draft = await response.json();
  dirty = false;
  saveStatus.textContent = "Draft saved.";
  paint();
}

async function loadIndex() {
  if (!pdfInfo.opened) {
    pdfIndex = { hits: {}, order: {} };
    return;
  }
  pdfStatus.textContent = "Matching extracted rows to the PDF…";
  const response = await fetch(CASE + "/pdf/index");
  if (!response.ok) throw new Error(await readError(response));
  pdfIndex = await response.json();
  catalog.rows = pdfIndex.rows || [];
  catalog.row_count = catalog.rows.length;
  selectedKode = null;
  detailKode = null;
  paintFacts();
  paintCategories();
}

async function uploadPdf(file) {
  pdfStatus.classList.remove("is-error");
  pdfStatus.textContent = "Opening " + file.name + "…";
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(CASE + "/pdf", { method: "POST", body: body });
  if (!response.ok) throw new Error(await readError(response));
  pdfInfo = await response.json();
  pdfImage.dataset.pageSrc = "";
  await loadIndex();
  const located = Object.keys(pdfIndex.order || {}).length;
  if (!located) pageScope.value = "all";
  showPage(firstLocatedPage());
}

async function loadReview() {
  reviewStatus.textContent = "Reading TARIF_KESEPAKATAN_EMC_ALAM_SUTERA.xlsx…";
  reviewError.hidden = true;
  try {
    const [catalogResponse, draftResponse, pdfResponse] = await Promise.all([
      fetch(CASE),
      fetch(CASE + "/draft"),
      fetch(CASE + "/pdf"),
    ]);
    if (!catalogResponse.ok) throw new Error(await readError(catalogResponse));
    if (!draftResponse.ok) throw new Error(await readError(draftResponse));
    if (!pdfResponse.ok) throw new Error(await readError(pdfResponse));
    catalog = await catalogResponse.json();
    catalog.rows = [];
    catalog.row_count = 0;
    draft = await draftResponse.json();
    pdfInfo = await pdfResponse.json();
    reviewStatus.textContent = "";
    paintFacts();
    paintCategories();
    applyZoom();
    setPager();
    if (pdfInfo.opened) {
      await loadIndex();
      showPage(firstLocatedPage());
    } else if (catalog.rows[0]) selectRow(catalog.rows[0].kode_master);
    else paint();
  } catch (error) {
    reviewStatus.textContent = "";
    reviewError.hidden = false;
    reviewErrorText.textContent = error.message || "The workbook could not be read.";
  }
}

extractBody.addEventListener("click", (event) => {
  const row = event.target.closest("tr");
  if (!row || !row.dataset.kode) return;
  selectRow(row.dataset.kode);
});

extractBody.addEventListener("keydown", (event) => {
  if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
  event.preventDefault();
  const rows = visibleRows();
  const index = rows.findIndex((row) => row.kode_master === selectedKode);
  const next = event.key === "ArrowDown" ? index + 1 : index - 1;
  if (next < 0 || next >= rows.length) return;
  selectRow(rows[next].kode_master, { focus: true });
});

rowSearch.addEventListener("input", () => paint({ follow: false }));
kategoriFilter.addEventListener("change", () => paint({ follow: false }));
statusFilter.addEventListener("change", () => paint({ follow: false }));
pageScope.addEventListener("change", () => {
  paint({ follow: false });
  if (pdfInfo.opened) refreshMarks();
});

document.getElementById("pdf-input").addEventListener("change", async (event) => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  try {
    await uploadPdf(file);
  } catch (error) {
    pdfStatus.classList.add("is-error");
    pdfStatus.textContent = error.message;
  }
});

pagePrev.addEventListener("click", () => showPage(currentPage - 1));
pageNext.addEventListener("click", () => showPage(currentPage + 1));
pageInput.addEventListener("change", () => showPage(pageInput.value));
pageInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  showPage(pageInput.value);
});
zoomOut.addEventListener("click", () => {
  zoomIndex = Math.max(0, zoomIndex - 1);
  applyZoom();
});
zoomIn.addEventListener("click", () => {
  zoomIndex = Math.min(ZOOMS.length - 1, zoomIndex + 1);
  applyZoom();
});

document.getElementById("show-cited").addEventListener("click", () => {
  const row = currentRow();
  const target = pdfPageFor(row);
  if (!row || !target) return;
  if (!pdfInfo.opened) {
    pdfStatus.textContent = "Open the PKS PDF to show this row.";
    return;
  }
  showPage(target);
});

document.getElementById("mark-match").addEventListener("click", () => {
  const row = currentRow();
  if (!row) return;
  saveStatus.classList.remove("is-error");
  saveStatus.textContent = "";
  verifiedPrice.value = formatIdr(row.price_final);
  remember(row.kode_master, "matches", row.price_final, reviewNote.value);
});

document.getElementById("mark-corrected").addEventListener("click", () => {
  const row = currentRow();
  if (!row) return;
  const amount = parseMoney(verifiedPrice.value);
  if (amount === null) {
    saveStatus.classList.add("is-error");
    saveStatus.textContent = "Type the printed amount using digits, for example 750.000.";
    return;
  }
  if (amount === row.price_final) {
    saveStatus.classList.add("is-error");
    saveStatus.textContent = "That amount is the extracted price. Use Printed price matches.";
    return;
  }
  saveStatus.classList.remove("is-error");
  saveStatus.textContent = "";
  remember(row.kode_master, "corrected", amount, reviewNote.value);
});

document.getElementById("clear-check").addEventListener("click", () => {
  const row = currentRow();
  if (!row) return;
  delete draft.rows[row.kode_master];
  dirty = true;
  verifiedPrice.value = formatIdr(row.price_final);
  reviewNote.value = "";
  detailKode = null;
  paint();
});

document.getElementById("save-draft").addEventListener("click", async () => {
  try {
    await saveDraft();
  } catch (error) {
    saveStatus.classList.add("is-error");
    saveStatus.textContent = error.message;
  }
});

downloadReview.addEventListener("click", async (event) => {
  if (!dirty) return;
  event.preventDefault();
  try {
    await saveDraft();
    window.location.assign(downloadReview.href);
  } catch (error) {
    saveStatus.classList.add("is-error");
    saveStatus.textContent = error.message;
  }
});

document.getElementById("retry-load").addEventListener("click", loadReview);

window.addEventListener("beforeunload", (event) => {
  if (!dirty) return;
  event.preventDefault();
  event.returnValue = "";
});

applyZoom();
setPager();
loadReview();
