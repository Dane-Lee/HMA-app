# HMA MVP Hosted Web App

Mobile-first ATI Human Movement Assessment MVP for on-site use. The app captures short movement videos in the browser, processes them transiently for scoring, saves only structured results, and provides a provider-facing history/results view.

## Stack

- Frontend: `Vite + React + Tailwind`
- Backend: `FastAPI`
- Database: `SQLite`
- Optional pose extraction: `MediaPipe + OpenCV`

## Repo Layout

```text
/api
/config
/data
/web
/HMA-Manual
  /api_manual
  /config_manual
  /data/manual
  /web_manual
Dockerfile
docker-compose.yml
```

## HMA-Manual Sister App

HMA-Manual is isolated under [`HMA-Manual/`](HMA-Manual/). Open that folder in
VS Code when you want to work strictly on the manual-scoring sister app without
touching the original HMA folders. It uses separate backend/frontend folders and
separate data under `HMA-Manual/data/manual`.

The manual app does not call the original movement-recognition pipeline. Review
videos are temporary files for provider review only. See
[`HMA-Manual/README.md`](HMA-Manual/README.md) for startup and deployment notes.

## Local Developer Workflow

For the shortest startup instructions, see [`How To Start Up Program.md`](<How To Start Up Program.md>).

Use this workflow for day-to-day coding on the same machine. The frontend runs on `http://localhost:5181`, the backend runs on `http://localhost:8002`, and Vite proxies `/api` to the backend.

The backend auto-loads the repo-root `.env` file when you run `uvicorn` locally. Use `.env.example` as the template; `DATA_DIR=./data` is the shared default for both local development and Docker.

1. Install backend dependencies:

```powershell
python -m pip install -r api/requirements.txt
python -m pip install -r api/requirements-vision.txt
```

2. Install frontend dependencies:

```powershell
cd web
npm install
```

3. Run the backend in one shell:

```powershell
uvicorn api.app.main:app --reload --port 8002
```

4. Run the frontend in a second shell:

```powershell
cd web
npm run dev
```

5. Open `http://localhost:5181`.

If the backend is unavailable, the frontend stops at an explicit connection screen instead of continuing into failing API requests.

## Built App Smoke Test

Build the frontend and let FastAPI serve the single-page app directly:

```powershell
cd web
npm run build
cd ..
uvicorn api.app.main:app --port 8002
```

With `web/dist` present, FastAPI serves the built single-page app at `http://localhost:8002`.

## Phone / Device Verification

Use this workflow when you want the deployed-like HTTPS experience on the local network, including phone camera access and secure cookies.

1. Start Docker Desktop.
2. Run:

```powershell
.\setup.ps1
```

3. Open one of the printed `https://<LAN-IP>` URLs on the phone or tablet.
4. Accept the self-signed certificate warning in the browser.

The Docker workflow is for device verification, not the default coding loop.

## Tests

Backend:

```powershell
pytest api/tests -q
```

Frontend:

```powershell
cd web
npm test
```

## Scoring Notes

- `cervical_rotation` and `trunk_rotation` have explicit rule modules tuned by `config/scoring_thresholds.yaml`.
- All five movements are wired into the assessment flow and scoring registry.
- Bilateral final score uses the lower of the two side scores.
- The backend never persists raw upload files. Temporary captures are deleted after analysis.
- When MediaPipe/OpenCV are unavailable, the fallback extractor uses deterministic metadata/file-based heuristics so the full workflow remains testable.
