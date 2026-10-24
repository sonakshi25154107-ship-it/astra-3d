# ASTRA 3D — Near-Earth Object Intelligence

An interactive Streamlit dashboard that loads real close-approach data from NASA's **Near Earth Object Web Service (NeoWs)**, lets you filter and compare objects, and shows them in a rotatable **schematic** 3D scene.

> **Scientific honesty.** NeoWs does not provide 3D positions for each asteroid. The 3D view is a *schematic layout*, labelled **"SCHEMATIC 3D EXPLORER — NOT TO SCALE; POSITIONS ARE ILLUSTRATIVE"**. It is not an orbit simulator. All real measurements appear in tooltips, charts and tables.

## Screenshots

![Dashboard](docs/screenshot-dashboard.png)

![3D explorer (schematic)](docs/screenshot-3d.png)

![Analytics](docs/screenshot-analytics.png)

## Features

- Live data from the NeoWs Feed endpoint (max 7 days per request, validated before sending)
- Header status: live vs. sample data, API key type, retrieval timestamp
- KPI strip: unique asteroids, hazardous count, largest estimated diameter, closest approach
- Rotatable, zoomable, hoverable Plotly 3D scene (marker size = estimated diameter)
- Filters: approach date, hazardous flag, diameter range, name/ID search, reset
- Charts: diameter distribution, closest approaches, relative velocity
- Sortable table with units, plus CSV download of the filtered data
- Selected-object panel with a link to NASA's JPL record when provided
- Friendly handling of timeouts, bad keys, HTTP 429, malformed JSON, empty results
- Optional sample mode, always labelled **DEMO/SAMPLE DATA — NOT LIVE NASA DATA**

## Architecture

```
astra-3d/
  app.py              Streamlit UI, CSS, session state, filters, sections
  nasa_api.py         NeoWs client: key handling, validation, errors, sample payload
  data_processing.py  Defensive parsing, filters, KPIs, illustrative coordinates, formatting
  visualizations.py   Plotly 3D scene and analytics charts
  requirements.txt
  .env.example        Template for your API key (copy to .env)
  .gitignore
  .streamlit/config.toml   Dark theme base colors
  README.md
```

Data flow: `nasa_api.fetch_feed` → cached in `app.cached_fetch` → `data_processing.parse_feed` (one row per close approach) → `apply_filters` → KPIs, charts, table, details.

## Skills demonstrated

REST API integration, defensive parsing, pandas data cleaning and unit conversion, Plotly 3D and statistical charts, Streamlit state and caching, error handling, secret management, UI design with CSS, scientific communication of limitations.

## NASA data and API key

1. Go to <https://api.nasa.gov/> and fill in the **Generate API Key** form (name and email). The key is emailed to you.
2. Copy `.env.example` to `.env` and set `NASA_API_KEY=your_key_here`.
3. Never commit `.env`. It is already in `.gitignore`.

Without a key the app uses `DEMO_KEY`, which works but is limited to roughly **30 requests per hour and 50 per day per IP address**. A personal key allows about 1,000 requests per hour (check api.nasa.gov for current limits).

## Setup on Windows with VS Code

Install Python 3.11 or 3.12 from python.org (tick "Add python.exe to PATH") and VS Code with the Python extension.

1. Open VS Code, choose **File → Open Folder**, and select the `astra-3d` folder.
2. Open a terminal: **Terminal → New Terminal** (PowerShell).
3. Create and activate a virtual environment:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

   If PowerShell blocks the script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again. In Command Prompt use `.venv\Scripts\activate.bat`. You should see `(.venv)` at the start of the prompt.
4. Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

5. Create your `.env` file:

```powershell
copy .env.example .env
```

6. Run the app:

```powershell
streamlit run app.py
```

The browser opens at <http://localhost:8501>. Stop the server with `Ctrl+C`.

## Test checklist

- [ ] App starts and the header shows **LIVE NASA DATA** after loading
- [ ] Drag/scroll/hover works in the 3D scene; the schematic banner is visible
- [ ] Changing a filter changes the KPIs, charts, table and selected-object list together
- [ ] Hazardous filter returns only rows marked "Yes"
- [ ] CSV download contains only the filtered rows
- [ ] Choosing more than 7 days shows a warning and disables Fetch
- [ ] Turning on the sample checkbox and fetching shows the amber sample label everywhere
- [ ] `.env` does not appear in `git status`

## Troubleshooting

| Problem | Fix |
|---|---|
| `streamlit` is not recognized | Activate the venv first (`.venv\Scripts\Activate.ps1`), then reinstall requirements |
| PowerShell says scripts are disabled | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| "rate limit reached (HTTP 429)" | Wait, or put your own key in `.env` and restart |
| "NASA rejected the API key" | Check for typos or spaces in `.env`; the file must be named `.env`, not `.env.txt` |
| "Could not reach api.nasa.gov" | Check internet, VPN or firewall settings |
| Edited `.env` but nothing changed | Stop and restart `streamlit run app.py` |
| Wrong Python in VS Code | `Ctrl+Shift+P` → **Python: Select Interpreter** → choose `.venv` |

## Data methodology and limitations

- **Diameter**: from NASA's `estimated_diameter.meters`. The app uses the mean of NASA's minimum and maximum estimates. These are estimates inferred mostly from brightness, not measurements.
- **Relative velocity**: speed relative to Earth at close approach, *not* orbital speed around the Sun.
- **Miss distance**: distance at closest approach, *not* size. Shown in km, lunar distances (384,400 km) and AU (149,597,870.7 km). Only exact unit conversions are applied.
- **Hazardous**: NASA's "potentially hazardous" classification (based on orbit and size). It is not an impact prediction.
- **Rows and dates**: one row per close approach; duplicates removed; dates are filtered on the actual approach date.
- **Missing values** stay missing and display as "Not provided".
- **3D scene**: direction comes from a hash of the NASA ID, distance from Earth is a log-compressed function of miss distance, and Sun/Earth are placed arbitrarily. Nothing is to scale and nothing represents an orbit.
- This is a student prototype and has **not** been scientifically validated.

## Publish on GitHub

```powershell
git init
git add .
git status
```

Confirm `.env` is **not** listed, then:

```powershell
git commit -m "Initial commit: ASTRA 3D"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/astra-3d.git
git push -u origin main
```

Create the empty `astra-3d` repository on github.com first (no README, no .gitignore). If a key was ever committed, revoke it at api.nasa.gov and generate a new one.

## LinkedIn description (edit after testing)

> **ASTRA 3D — NASA Near-Earth Object Explorer.** I built an interactive Python dashboard that pulls close-approach data from NASA's NeoWs API, cleans and analyzes it with pandas, and presents it through Plotly charts and a rotatable 3D scene. It supports filtering, CSV export and object-level details, handles API limits and missing data, and clearly labels the 3D view as schematic because NASA's feed doesn't provide positions. Built with Python, Streamlit, Plotly and pandas as part of my path toward space data science. Code: [GitHub link]