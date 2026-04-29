import html
import json
import os
import time
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.responses import HTMLResponse
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

app = FastAPI()

API_URL = "https://data.fingrid.fi/api/datasets"
DATA_API_URL = "https://data.fingrid.fi/api/datasets/{dataset_id}/data"
DATASET_DOCS_URL = "https://developer-data.fingrid.fi/api-details#api=avoindata-api&operation=GetDatasetData"
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
              (
                "<td class=\"actions\">"
                f"<a class=\"action-link\" href=\"{DATASET_DOCS_URL}\" target=\"_blank\" rel=\"noreferrer noopener\">Docs</a>"
                f"<button class=\"action-button\" data-dataset-id=\"{dataset_id}\" data-dataset-name=\"{name}\">Last Hour</button>"
                "</td>"
              ),
                    "</tr>",
                ]
            )
        )
    return "\n".join(rows)


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_last_hour_dataset_data(dataset_id: int, api_key: str) -> dict:
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=1)
    start_str = iso_utc(start_time)
    end_str = iso_utc(end_time)
    params = {
        "startTime": start_str,
        "endTime": end_str,
        "pageSize": 200,
    }
    query = urlencode(params)
    request_url = DATA_API_URL.format(dataset_id=dataset_id)
    full_url = f"{request_url}?{query}"
    headers = {
        "Cache-Control": "no-cache",
        "x-api-key": api_key,
        "Accept": "application/json",
    }
    request = Request(full_url, headers=headers)
    with urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8")
    body = json.loads(payload)
    curl_command = (
        "curl -sS -H 'Cache-Control: no-cache' "
        "-H 'x-api-key: $FINGRID_API_KEY' "
        f"'{full_url}'"
    )
    return {
        "datasetId": dataset_id,
        "startTime": start_str,
        "endTime": end_str,
        "requestUrl": full_url,
        "curl": curl_command,
        "response": body,
    }


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
    .actions {{
      min-width: 200px;
      white-space: nowrap;
    }}
    .action-link {{
      display: inline-block;
      text-decoration: none;
      color: #0b5b55;
      font-weight: 600;
      margin-right: 10px;
      padding: 6px 8px;
      border-radius: 8px;
    }}
    .action-link:hover {{
      background: rgba(11, 91, 85, 0.1);
    }}
    .action-button {{
      border: 0;
      border-radius: 10px;
      background: #0f766e;
      color: white;
      padding: 8px 11px;
      font: inherit;
      cursor: pointer;
    }}
    .action-button:hover {{
      background: #0b5b55;
    }}
    dialog {{
      width: min(980px, calc(100vw - 20px));
      border: 0;
      border-radius: 16px;
      padding: 0;
      box-shadow: 0 24px 70px rgba(15, 18, 20, 0.3);
    }}
    dialog::backdrop {{
      background: rgba(23, 29, 33, 0.46);
      backdrop-filter: blur(2px);
    }}
    .dialog-shell {{
      padding: 18px;
      background: #fffdf9;
    }}
    .dialog-head {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 12px;
    }}
    .dialog-title {{
      margin: 0;
      font-size: 1.1rem;
    }}
    .dialog-close {{
      border: 0;
      background: transparent;
      color: #42535a;
      cursor: pointer;
      font: inherit;
      padding: 6px 8px;
      border-radius: 8px;
    }}
    .dialog-close:hover {{
      background: rgba(66, 83, 90, 0.1);
    }}
    .code-block {{
      margin: 8px 0 14px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #fcfaf5;
      padding: 12px;
      max-height: 360px;
      overflow: auto;
      font-size: 0.85rem;
      line-height: 1.45;
      font-family: Menlo, Monaco, Consolas, monospace;
      white-space: pre;
    }}
    .dialog-section-title {{
      margin: 14px 0 6px;
      color: #3b4c53;
      font-size: 0.83rem;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
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
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="datasetRows">
          {rows}
        </tbody>
      </table>
    </div>
    <p class="footer">Reload the page to fetch the latest dataset catalog from Fingrid.</p>
  </main>
  <dialog id="datasetDialog">
    <section class="dialog-shell">
      <div class="dialog-head">
        <h2 class="dialog-title" id="dialogTitle">Dataset Details</h2>
        <button class="dialog-close" id="dialogClose">Close</button>
      </div>
      <div class="dialog-section-title">cURL Request</div>
      <pre class="code-block" id="curlBlock">Loading...</pre>
      <div class="dialog-section-title">API Response</div>
      <pre class="code-block" id="responseBlock">Loading...</pre>
    </section>
  </dialog>
  <script>
    const searchInput = document.getElementById('searchInput');
    const visibleCount = document.getElementById('visibleCount');
    const rows = Array.from(document.querySelectorAll('#datasetRows tr'));
    const actionButtons = Array.from(document.querySelectorAll('.action-button'));
    const datasetDialog = document.getElementById('datasetDialog');
    const dialogTitle = document.getElementById('dialogTitle');
    const dialogClose = document.getElementById('dialogClose');
    const curlBlock = document.getElementById('curlBlock');
    const responseBlock = document.getElementById('responseBlock');

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

    function prettyJson(value) {{
      try {{
        return JSON.stringify(value, null, 2);
      }} catch (_error) {{
        return String(value);
      }}
    }}

    async function showDatasetDialog(datasetId, datasetName) {{
      dialogTitle.textContent = `Dataset ${{datasetId}}: ${{datasetName}}`;
      curlBlock.textContent = 'Loading cURL request...';
      responseBlock.textContent = 'Loading API response...';
      if (!datasetDialog.open) {{
        datasetDialog.showModal();
      }}

      try {{
        const response = await fetch(`/api/datasets/${{datasetId}}/last-hour`);
        const body = await response.json();
        if (!response.ok) {{
          curlBlock.textContent = body.curl || 'Request generation failed';
          responseBlock.textContent = prettyJson(body);
          return;
        }}
        curlBlock.textContent = body.curl || 'No cURL generated';
        responseBlock.textContent = prettyJson(body.response);
      }} catch (error) {{
        curlBlock.textContent = 'Failed to fetch data';
        responseBlock.textContent = String(error);
      }}
    }}

    for (const button of actionButtons) {{
      button.addEventListener('click', () => {{
        const datasetId = button.getAttribute('data-dataset-id');
        const datasetName = button.getAttribute('data-dataset-name') || 'Unnamed dataset';
        showDatasetDialog(datasetId, datasetName);
      }});
    }}

    dialogClose.addEventListener('click', () => datasetDialog.close());
    datasetDialog.addEventListener('click', (event) => {{
      const bounds = datasetDialog.getBoundingClientRect();
      const clickedOutside = (
        event.clientX < bounds.left ||
        event.clientX > bounds.right ||
        event.clientY < bounds.top ||
        event.clientY > bounds.bottom
      );
      if (clickedOutside) {{
        datasetDialog.close();
      }}
    }});
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


@app.get("/api/datasets/{dataset_id}/last-hour")
async def dataset_last_hour(dataset_id: int):
  try:
    api_key = get_api_key()
    payload = fetch_last_hour_dataset_data(dataset_id, api_key)
    return payload
  except HTTPError as error:
    error_body = ""
    try:
      error_body = error.read().decode("utf-8")
    except Exception:
      error_body = ""
    return JSONResponse(
      status_code=error.code,
      content={
        "error": f"Fingrid API error: {error.reason}",
        "datasetId": dataset_id,
        "responseText": error_body,
        "curl": (
          "curl -sS -H 'Cache-Control: no-cache' "
          "-H 'x-api-key: $FINGRID_API_KEY' "
          f"'https://data.fingrid.fi/api/datasets/{dataset_id}/data?startTime=<ISO>&endTime=<ISO>&pageSize=200'"
        ),
      },
    )
  except URLError as error:
    return JSONResponse(
      status_code=502,
      content={
        "error": f"Unable to reach Fingrid API: {error.reason}",
        "datasetId": dataset_id,
      },
    )
  except Exception as error:
    return JSONResponse(
      status_code=500,
      content={
        "error": str(error),
        "datasetId": dataset_id,
      },
    )
