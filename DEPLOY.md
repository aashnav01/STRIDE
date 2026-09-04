# Deploying Stride to Render

Two services: a Python backend and a static frontend. They need each other's
**public** URLs, which are not known until both exist — so deployment is a
two-pass process.

## Why you cannot wire them automatically

Render's `fromService` returns the service's *internal* hostname. The
frontend is a static site: its JavaScript runs in the user's browser, which
sits outside Render's private network and cannot resolve that name. Using it
produces:

```
Failed to load resource: net::ERR_NAME_NOT_RESOLVED
```

Render also appends a random suffix when a service name is already taken
(`stride-backend` → `stride-backend-ab12`), so the public URL cannot be
predicted from the blueprint either. Both variables are therefore
`sync: false` and set by hand, once.

## Steps

**1 — Sync the blueprint**

Render Dashboard → **New → Blueprint** → connect `aashnav01/STRIDE`, branch
`main`. If a blueprint is already connected, open it and **Sync** instead.

The backend service is named **stride-api**, not stride-backend. Render
cannot convert an existing service from the native Python runtime to Docker,
but it does create a service for a name it has not seen — so the rename is
what produces a Docker build without hand-building the service. Delete the
old `stride-backend` once `stride-api` is live.

It will prompt for the two `sync: false` variables. Leave them blank for now
and apply.

The backend builds as a **Docker image**, not on Render's native Python
runtime. MediaPipe links against OpenGL ES (`libGLESv2`, `libEGL`) even for
headless CPU work, and depends on the non-headless `opencv-contrib-python`
regardless of what is pinned; the native runtime has neither library and no
way to install them. The Dockerfile installs them explicitly.

The first build takes 5–10 minutes — mediapipe, opencv and interpret are
large.

**2 — Wait for the backend, then copy its URL**

Once `stride-backend` is live, confirm the model actually loaded:

```
https://<your-backend>.onrender.com/health
→ {"status":"healthy","model_loaded":true}
```

If `model_loaded` is `false`, the model failed to load — check the build log
before going further. Nothing else will work.

**3 — Point the frontend at it**

`stride-frontend` → Environment → set:

```
VITE_API_URL = https://<your-backend>.onrender.com
```

Use the **full public URL** — scheme, service name and `.onrender.com`.
A bare service name such as `stride-backend-ifu4` has no domain and will
never resolve from a browser. Then **Manual Deploy → Deploy latest commit**.

> This variable is read by Vite at **build** time and baked into the bundle.
> Restarting is not enough — it must rebuild, or the old value stays compiled in.

**4 — Let the backend accept the frontend**

`stride-backend` → Environment → set:

```
ALLOWED_ORIGINS = https://<your-frontend>.onrender.com
```

This one is read at runtime, so a restart is sufficient. Multiple origins can
be comma-separated. `localhost:5173` and `localhost:4173` are always allowed,
so local development keeps working.

**5 — Verify**

Open the frontend and start a screening. If a request fails, check in order:

| Symptom | Cause |
|---|---|
| `ERR_NAME_NOT_RESOLVED`, host has no dot | `VITE_API_URL` is a bare service name; it needs the full `.onrender.com` URL |
| `ERR_NAME_NOT_RESOLVED`, host looks right | Points at a service that no longer exists, or the bundle was not rebuilt |
| CORS error in console | `ALLOWED_ORIGINS` does not exactly match the frontend origin |
| 500, `model_loaded: false` | Model failed to load; see the build log |
| 500, `libGLESv2.so.2: cannot open shared object file` | Backend is on the native Python runtime. MediaPipe needs system GL libraries — the service must use the Docker runtime (`runtime: docker` in `render.yaml`) |
| First request hangs ~50 s | Free instance waking from sleep — this is normal |

## Diagnosing a slow request

Every analysis returns a `timings` block and logs it server-side. Open the
browser console:

```
[timing] round trip 78.3s | server: upload 1.2s, pose 61.4s (245 ms/frame),
         score 0.3s, total 62.9s
[timing] 15.4s outside the server — upload + cold start
```

Read it as:

| Observation | Meaning |
|---|---|
| `pose_s` dominates | Normal. MediaPipe runs on every frame |
| `ms_per_frame` above ~200 | Slow shared CPU, or frames are not being downscaled |
| Large gap between round trip and `total_s` | Cold start or a slow upload, not the model |
| `score_s` above a second | Unexpected — inference should be milliseconds |
| No response at all after 4 min | The client aborts and says so |

`GET /health` reports `uptime_s` and `peak_rss_mb`. If `uptime_s` resets
between requests the process restarted — on a 512 MB instance that almost
always means it was OOM-killed mid-request, which from the browser is
indistinguishable from a timeout.

## Before a demo

- **Open `/health` a minute beforehand.** Free instances sleep after 15
  minutes idle and take roughly 50 s to wake. Combined with 30–60 s of
  analysis, a cold first upload can take 90 s.
- **Screening records do not persist on the free plan.** Render's filesystem
  is ephemeral, so every deploy, restart and sleep/wake wipes the database
  and the dashboard resets. Each phone keeps its own copy in IndexedDB, so
  nothing is lost on the device. For durable server-side storage, set the
  backend to `plan: starter` and uncomment the `disk` block in
  `render.yaml`, then set `SCREENINGS_DB=/var/data/screenings.db`.
- **Test with a full-length video**, not a 4-second clip. Idle memory is
  ~170 MB against a 512 MB limit, leaving ~340 MB for pose extraction. That
  should be ample, but long or high-resolution footage is the one path that
  has not been measured.
