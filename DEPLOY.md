# Deploying PartsHub free on Render

PartsHub runs as a normal Python web service. The one twist: several vendors block
datacenter IPs, so you **ingest the catalog on your own machine**, then ship the
pre-built `partshub.db` with the app. Render just serves it.

---

## 1. Build the catalog database locally

Your home network can reach every vendor (Render's datacenter can't), so run
ingestion locally first:

```powershell
cd Parts-Hub                   # the folder you cloned
.venv\Scripts\activate
python -m scripts.ingest       # full catalog  (or: python -m scripts.seed_demo for a quick demo)
```

This creates/updates `partshub.db` in the project folder.

## 2. Commit the app + database

`partshub.db` is normally git-ignored, so force-add it **once** for deployment
(after that it's tracked and normal commits pick up changes):

```powershell
git add -A
git add -f partshub.db
git commit -m "Add Render deploy config + bundled catalog DB"
git push
```

Your repo now contains the code, `render.yaml`, and the database.

## 3. Create the Render service

1. Go to **https://render.com** and sign in with GitHub (free — no card needed for the free plan).
2. **New +  →  Blueprint**.
3. Pick your **`Herons-0/Parts-Hub`** repo → Render reads `render.yaml` → **Apply**.
4. Wait ~2–4 minutes for the build. You'll get a URL like
   **`https://partshub.onrender.com`**.

<details>
<summary>Prefer to set it up manually instead of the blueprint?</summary>

**New +  →  Web Service** → connect `Parts-Hub`, then:
- **Language:** Python 3
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Instance type:** Free
- **Create Web Service**
</details>

## 4. Good to know (free tier)

- **Sleeps when idle:** free services spin down after ~15 min of no traffic; the next
  visit wakes it and takes ~1 minute. Normal for free hosting.
- **Serves the bundled DB.** To refresh prices later, re-ingest locally and push — Render
  auto-redeploys on every push:

  ```powershell
  python -m scripts.ingest
  git commit -am "Refresh catalog"
  git push
  ```

- **Projects/carts created on the live free site reset on restart** (the free tier has
  an ephemeral disk). That's fine for a demo/portfolio. For durable user data you'd add
  a Render paid disk or an external database (e.g. Postgres) later.

That's it — connect the repo, and PartsHub is live for free.
