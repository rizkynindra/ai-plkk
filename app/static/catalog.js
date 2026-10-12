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

const select = document.getElementById("branch-select");
const status = document.getElementById("catalog-status");
const wrap = document.getElementById("catalog-table");
const body = document.getElementById("catalog-body");

async function loadBranches() {
  const response = await fetch("/api/hospitals");
  const rows = await response.json();
  if (!rows.length) {
    status.textContent = "No PKS saved yet. Use Upload PKS to add a tariff book.";
    return;
  }
  rows.forEach((row) => {
    const option = document.createElement("option");
    option.value = row.branch_id;
    option.textContent = row.branch_name + (row.city ? " · " + row.city : "") + " · " + row.item_count + " items";
    select.appendChild(option);
  });
}

select.addEventListener("change", async () => {
  const branchId = select.value;
  body.replaceChildren();
  wrap.hidden = true;
  if (!branchId) {
    status.textContent = "Select a branch to see stored tariff rows.";
    return;
  }
  status.textContent = "Loading tariff rows…";
  const response = await fetch("/api/hospitals/" + branchId);
  if (!response.ok) {
    status.classList.add("is-error");
    status.textContent = "Could not load this branch.";
    return;
  }
  status.classList.remove("is-error");
  const data = await response.json();
  if (!data.items.length) {
    status.textContent = "This branch has no stored tariff rows. Upload PKS again.";
    return;
  }
  status.textContent = data.item_count + " rows for " + data.branch_name + ".";
  data.items.forEach((item) => {
    const tr = document.createElement("tr");
    TARIFF_HEADERS.forEach((key) => {
      const td = document.createElement("td");
      td.textContent = cellText(item, key);
      if (MONEY_COLUMNS.has(key)) td.className = "num";
      if (key === "nama") td.className = "nama";
      if (key === "price_basis") td.className = "basis";
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
  wrap.hidden = false;
});

loadBranches();
