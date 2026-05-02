# How To Start Up Program

## Normal Startup

Use this when you just want to open the program on this computer.

1. Open PowerShell in this project folder.
2. Type:

```powershell
.\start-local.ps1
```

3. The app opens at `http://localhost:8002`.
4. Keep the PowerShell window open.
5. Press `Enter` in that window to stop the app.

If the app was already open and looks broken, restart it with:

```powershell
.\start-local.ps1 -Restart
```

## If You Are Editing Code

Use this for live frontend/backend development.

```powershell
.\start-dev.ps1
```

The app opens at `http://localhost:5181`. Press `Enter` in that PowerShell window to stop both servers.

## Phone Or Tablet Testing

Use this when a phone/tablet needs to open the app over HTTPS.

```powershell
.\start-phone.ps1
```

The script starts Docker Desktop if needed, starts the app, and prints the `https://...` address to open on the phone/tablet.

To stop the Docker app later:

```powershell
docker compose down
```

## If PowerShell Blocks The Script

Run this version instead:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-local.ps1
```
