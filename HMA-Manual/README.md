# HMA-Manual

HMA-Manual is a sister program to the original HMA app. It uses separate app folders and separate data storage:

- Backend: `api_manual`
- Frontend: `web_manual`
- Config: `config_manual`
- Data: `data/manual`

Open this `HMA-Manual` folder in VS Code when you want to work only on the sister app.

The manual app intentionally does not call the original scoring service. Review videos are temporary files for provider review only.

## Local Development

1. Copy `.env.manual.example` to `.env.manual` and change the bootstrap password.
2. Start the app:

```powershell
.\start-manual-dev.ps1
```

The manual frontend runs at `http://localhost:5182` and the manual backend runs at `http://localhost:8003`.

## Public Deployment Notes

Run HMA and HMA-Manual behind a reverse proxy. The public proxy should terminate HTTPS and route separate hostnames to private app ports, for example:

- `hma.example.com` -> original HMA
- `hma-manual.example.com` -> HMA-Manual

For public deployment, enable provider MFA, use named provider accounts, and complete the compliance review for employee movement videos and retention.
