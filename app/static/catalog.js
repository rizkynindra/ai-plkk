function formatIdr(value) {
  if (value === null || value === undefined || value === "") return "";
  return Math.round(Number(value)).toLocaleString("id-ID");
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
    const cells = [
      item.item_code || "",
      item.item_name || "",
      item.kelompok || "",
      formatIdr(item.tariff),
      item.tariff_note || "",
    ];
    cells.forEach((value, index) => {
      const td = document.createElement("td");
      td.textContent = value;
      if (index === 3) td.className = "num";
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
  wrap.hidden = false;
});

loadBranches();
