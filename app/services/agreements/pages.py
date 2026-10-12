from app.web import render_app_page

AGREEMENTS_BODY = """
      <section class="panel">
        <form id="pks-form">
          <label id="dropzone" class="dropzone" for="file-input">
            <input id="file-input" type="file" name="file" accept=".pdf,.xlsx,.xls,.csv,application/pdf" required>
            <div>
              <strong>Drop the PKS file</strong>
              <span id="file-label">PDF tariff book or Excel catalog</span>
            </div>
          </label>
          <div class="actions">
            <button id="preview-button" class="button" type="submit">Read tariff rows</button>
          </div>
          <p id="status" class="status" role="status"></p>
        </form>
      </section>
      <section id="edit-card" class="panel" hidden>
        <form id="save-form">
          <div class="form-grid">
            <label>Hospital group <input id="group_name" name="group_name" required></label>
            <label>Branch <input id="branch_name" name="branch_name" required></label>
            <label>City <input id="city" name="city"></label>
            <label>Code <input id="code" name="code"></label>
            <label class="wide">Address <input id="address" name="address"></label>
            <label>Effective date <input id="effective_date" name="effective_date" placeholder="YYYY-MM-DD"></label>
            <label>Aliases <input id="aliases" name="aliases" placeholder="pelni jakarta, pelni malang"></label>
          </div>
          <p id="item-summary" class="lede"></p>
          <div class="actions">
            <button class="button" type="submit">Save branch catalog</button>
          </div>
          <div id="preview-table" class="table-wrap tariff-sheet-wrap">
            <table class="tariff-sheet">
              <thead>
                <tr>
                  <th>kode_master</th>
                  <th>kategori_bpjs</th>
                  <th>hospital_name</th>
                  <th>nama</th>
                  <th>group_code</th>
                  <th>price</th>
                  <th>price_base</th>
                  <th>price_final</th>
                  <th>price_basis</th>
                  <th>source_page</th>
                </tr>
              </thead>
              <tbody id="preview-body"></tbody>
            </table>
          </div>
        </form>
      </section>
"""

AGREEMENTS_PAGE = render_app_page(
    title="Upload PKS — EPLKK",
    heading="Upload PKS",
    lede="Read the tariff book, check the extracted rows, then save the catalog.",
    active="pks",
    body=AGREEMENTS_BODY,
    scripts=["/static/nav.js", "/static/agreements.js"],
    shell_class="shell shell-wide",
    body_class="agreements-body",
)

CATALOG_BODY = """
      <section class="panel">
        <label>Branch
          <select id="branch-select">
            <option value="">Select a saved branch</option>
          </select>
        </label>
        <p id="catalog-status" class="status is-empty" role="status">Select a branch to see stored tariff rows.</p>
      </section>
      <div id="catalog-table" class="table-wrap tariff-sheet-wrap" hidden>
        <table class="tariff-sheet">
          <thead>
            <tr>
              <th>kode_master</th>
              <th>kategori_bpjs</th>
              <th>hospital_name</th>
              <th>nama</th>
              <th>group_code</th>
              <th>price</th>
              <th>price_base</th>
              <th>price_final</th>
              <th>price_basis</th>
              <th>source_page</th>
            </tr>
          </thead>
          <tbody id="catalog-body"></tbody>
        </table>
      </div>
"""

CATALOG_PAGE = render_app_page(
    title="PKS data — EPLKK",
    heading="PKS data",
    lede="Tariff rows already saved per hospital branch.",
    active="catalog",
    body=CATALOG_BODY,
    scripts=["/static/nav.js", "/static/catalog.js"],
    shell_class="shell shell-wide",
    body_class="agreements-body",
)

COMPARE_BODY = """
      <section class="panel">
        <form id="compare-form">
          <label>PKS branch
            <select id="branch-select" required>
              <option value="">Select a saved branch</option>
            </select>
          </label>
          <label id="dropzone" class="dropzone" for="file-input">
            <input id="file-input" type="file" name="file" accept=".pdf,.xlsx,.xls,.csv,.docx,.jpg,.jpeg,.png,.webp,.tif,.tiff,.bmp,application/pdf,image/*" required>
            <div>
              <strong>Drop the claim invoice</strong>
              <span id="file-label">PDF, Excel, Word, CSV, or image</span>
            </div>
          </label>
          <div class="actions">
            <button id="compare-button" class="button" type="submit">Extract and compare</button>
          </div>
          <p id="status" class="status" role="status"></p>
        </form>
      </section>
      <div class="facts" id="compare-facts" hidden></div>
      <div id="compare-table" class="table-wrap" hidden>
        <table>
          <thead>
            <tr>
              <th>No</th>
              <th>Item Biaya</th>
              <th>Invoice tarif</th>
              <th>Match</th>
              <th>PKS item</th>
              <th>PKS tarif</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody id="compare-body"></tbody>
        </table>
      </div>
"""

COMPARE_PAGE = render_app_page(
    title="Compare — EPLKK",
    heading="Compare claim to PKS",
    lede="Choose the hospital branch catalog, then drop a claim. Rows stay as billed; the match column only flags differences.",
    active="compare",
    body=COMPARE_BODY,
    scripts=["/static/nav.js", "/static/compare.js"],
)
