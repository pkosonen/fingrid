import html
import json
import os
import time
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

app = FastAPI()

API_URL = "https://data.fingrid.fi/api/datasets"
API_KEY_ENV = "FINGRID_API_KEY"
CACHE_TTL_SECONDS = 300
PAGE_SIZE = 500

DATASET_CACHE = {
    "datasets": None,
    "fetched_at": 0.0,
}


def get_api_key() -> str:
    api_key = os.environ.get(API_KEY_ENV, "").strip()
    if not api_key:
        raise RuntimeError(
            f"Set {API_KEY_ENV} before starting the viewer."
        )
    return api_key


def fetch_datasets(api_key: str) -> list[dict]:
    headers = {
        "Cache-Control": "no-cache",
        "x-api-key": api_key,
        "Accept": "application/json",
    }
    now = time.time()
    cached = DATASET_CACHE["datasets"]
    fetched_at = DATASET_CACHE["fetched_at"]
    if cached is not None and now - fetched_at < CACHE_TTL_SECONDS:
        return cached

    datasets: list[dict] = []
    page = 1

    while True:
        query = urlencode({"page": page, "pageSize": PAGE_SIZE})
        request = Request(f"{API_URL}?{query}", headers=headers)
        try:
            with urlopen(request, timeout=30) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as error:
            if error.code == 429 and cached is not None:
                return cached
            raise
        body = json.loads(payload)
        data = body.get("data")
        if not isinstance(data, list):
            raise RuntimeError(
                "Unexpected API response: expected a data list in the response body."
            )

        datasets.extend(data)
        pagination = body.get("pagination") or {}
        next_page = pagination.get("nextPage")
        if next_page is None:
            break
        page = next_page

    DATASET_CACHE["datasets"] = datasets
    DATASET_CACHE["fetched_at"] = now
    return datasets


def render_tags(values: list[str]) -> str:
    if not values:
        return '<span class="muted">-</span>'
    tags = []
    for value in values:
        tags.append(f'<span class="tag">{html.escape(str(value))}</span>')
    return "".join(tags)


def render_table_rows(datasets: list[dict]) -> str:
    rows = []
    for dataset in datasets:
        dataset_id = html.escape(str(dataset.get("id", "")))
        name = html.escape(dataset.get("nameEn") or dataset.get("nameFi") or "")
        organization = html.escape(dataset.get("organization") or "")
        dataset_type = html.escape(dataset.get("type") or "")
        unit = html.escape(dataset.get("unitEn") or dataset.get("unitFi") or "")
        period = html.escape(dataset.get("dataPeriodEn") or dataset.get("dataPeriodFi") or "")
        modified = html.escape(dataset.get("modifiedAtUtc") or "")
        description = html.escape(
            dataset.get("descriptionEn") or dataset.get("descriptionFi") or ""
        )
        formats = render_tags(dataset.get("availableFormats") or [])
        groups = render_tags(dataset.get("contentGroupsEn") or dataset.get("contentGroupsFi") or [])
        keywords = " ".join(
            str(value) for value in (dataset.get("keyWordsEn") or dataset.get("keyWordsFi") or [])
        )
        searchable = html.escape(
            " ".join(
                [
                    dataset_id,
                    name,
                    organization,
                    dataset_type,
                    unit,
                    period,
                    description,
                    keywords,
                ]
            ).lower()
        )
        rows.append(
            "".join(
                [
                    f'<tr data-search="{searchable}">',
                    f"<td>{dataset_id}</td>",
                    f"<td><strong>{name}</strong><div class=\"description\">{description}</div></td>",
                    f"<td>{organization}</td>",
                    f"<td>{dataset_type}</td>",
                    f"<td>{unit}</td>",
                    f"<td>{period}</td>",
                    f"<td>{groups}</td>",
                    f"<td>{formats}</td>",
                    f"<td>{modified}</td>",
                    "</tr>",
                ]
            )
        )
    return "\n".join(rows)


def render_page(datasets: list[dict]) -> str:
    rows = render_table_rows(datasets)
    total = len(datasets)
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fingrid Dataset Viewer</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f1e8;
      --panel: rgba(255, 252, 247, 0.92);
      --panel-strong: #fffaf1;
      --ink: #1f2a2f;
      --muted: #66757c;
      --line: rgba(31, 42, 47, 0.12);
      --accent: #0f766e;
      --accent-soft: rgba(15, 118, 110, 0.12);
      --tag: #f0e5c8;
      --shadow: 0 22px 50px rgba(51, 59, 64, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(15, 118, 110, 0.12), transparent 26%),
        radial-gradient(circle at top right, rgba(192, 132, 53, 0.12), transparent 24%),
        linear-gradient(180deg, #fbf7ef 0%, var(--bg) 100%);
    }}
    .shell {{
      width: min(1400px, calc(100vw - 32px));
      margin: 32px auto;
      padding: 28px;
      border: 1px solid rgba(255, 255, 255, 0.7);
      border-radius: 28px;
      background: var(--panel);
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
    }}
    h1 {{
      margin: 0;
      font-size: clamp(2rem, 3vw, 3.2rem);
      line-height: 0.98;
      letter-spacing: -0.03em;
    }}
    .lead {{
      max-width: 70ch;
      margin: 12px 0 0;
      color: var(--muted);
      font-size: 1.02rem;
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      align-items: center;
      justify-content: space-between;
      margin: 24px 0 18px;
      padding: 18px;
      border-radius: 18px;
      background: var(--panel-strong);
      border: 1px solid var(--line);
    }}
    .stat {{
      display: inline-flex;
      flex-direction: column;
      gap: 4px;
      min-width: 140px;
    }}
    .stat-label {{
      color: var(--muted);
      font-size: 0.75rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .stat-value {{
      font-size: 1.7rem;
    }}
    .search {{
      flex: 1 1 280px;
      min-width: 240px;
      max-width: 420px;
    }}
    input {{
      width: 100%;
      padding: 14px 16px;
      border-radius: 999px;
      border: 1px solid var(--line);
      font: inherit;
      background: white;
    }}
    input:focus {{
      outline: 2px solid var(--accent-soft);
      border-color: var(--accent);
    }}
    .table-wrap {{
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 22px;
      background: rgba(255, 255, 255, 0.75);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 1080px;
    }}
    thead th {{
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f8f2e5;
      text-align: left;
      font-size: 0.8rem;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #46555c;
    }}
    th, td {{
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    tbody tr:hover {{
      background: rgba(15, 118, 110, 0.05);
    }}
    .description {{
      margin-top: 6px;
      color: var(--muted);
      max-width: 44ch;
      font-size: 0.94rem;
      line-height: 1.4;
    }}
    .tag {{
      display: inline-block;
      margin: 0 8px 8px 0;
      padding: 5px 10px;
      border-radius: 999px;
      background: var(--tag);
      font-size: 0.86rem;
      white-space: nowrap;
    }}
    .muted {{ color: var(--muted); }}
    .hidden {{ display: none; }}
    .footer {{
      margin-top: 14px;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    @media (max-width: 720px) {{
      .shell {{
        width: min(100vw - 16px, 100%);
        margin: 8px auto;
        padding: 18px;
        border-radius: 20px;
      }}
      .toolbar {{
        padding: 14px;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <h1>Fingrid Dataset Viewer</h1>
    <p class="lead">Browse all datasets exposed by the Fingrid Data service. Filter by id, name, organization, type, unit, period, description, or keywords.</p>
    <section class="toolbar">
      <div class="stat">
        <span class="stat-label">Datasets</span>
        <span class="stat-value" id="visibleCount">{total}</span>
      </div>
      <div class="search">
        <input id="searchInput" type="search" placeholder="Filter datasets by name, id, type, keyword..." autofocus>
      </div>
    </section>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Organization</th>
            <th>Type</th>
            <th>Unit</th>
            <th>Period</th>
            <th>Groups</th>
            <th>Formats</th>
            <th>Modified</th>
          </tr>
        </thead>
        <tbody id="datasetRows">
          {rows}
        </tbody>
      </table>
    </div>
    <p class="footer">Reload the page to fetch the latest dataset catalog from Fingrid.</p>
  </main>
  <script>
    const searchInput = document.getElementById('searchInput');
    const visibleCount = document.getElementById('visibleCount');
    const rows = Array.from(document.querySelectorAll('#datasetRows tr'));

    function applyFilter() {{
      const query = searchInput.value.trim().toLowerCase();
      let count = 0;
      for (const row of rows) {{
        const isMatch = !query || row.dataset.search.includes(query);
        row.classList.toggle('hidden', !isMatch);
        if (isMatch) {{
          count += 1;
        }}
      }}
      visibleCount.textContent = String(count);
    }}

    searchInput.addEventListener('input', applyFilter);
  </script>
</body>
</html>
"""
    return page


@app.get("/", response_class=HTMLResponse)
async def index():
    """Render the Fingrid dataset viewer."""
    try:
        api_key = get_api_key()
    except RuntimeError as error:
        return f"<h1>Configuration Error</h1><p>{error}</p>"

    try:
        datasets = fetch_datasets(api_key)
        page = render_page(datasets)
        return page
    except HTTPError as error:
        return f"<h1>Fingrid API Error</h1><p>Status {error.code}: {error.reason}</p>"
    except URLError as error:
        return f"<h1>Connection Error</h1><p>Unable to reach Fingrid API: {error.reason}</p>"
    except Exception as error:
        return f"<h1>Viewer Error</h1><p>{error}</p>"


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
