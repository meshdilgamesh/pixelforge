"""PixelForge local web UI server.

Everything stays on your machine — the server binds to 127.0.0.1 only and
images never leave your computer. Jobs run one at a time on the GPU.
"""
from __future__ import annotations

import queue
import threading
import time
import uuid
import webbrowser
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .cli import resolve_target
from .engine import Upscaler, auto_tile_size, get_device
from .models import MODELS, find_model_file, models_dir

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "outputs"
OUT_DIR.mkdir(exist_ok=True)
STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="PixelForge", docs_url=None, redoc_url=None)
    state = app.state
    state.jobs = {}
    state.queue: queue.Queue = queue.Queue()
    state.lock = threading.Lock()
    state.upscalers: dict[tuple, Upscaler] = {}
    state.current_model_key = None
    state.downloads: dict[str, dict] = {}

    # check for updates once in the background (silent when offline/unhosted)
    def _startup_update_check():
        from . import update as upd

        state.update_info = upd.check()

    state.update_info = None
    threading.Thread(target=_startup_update_check, daemon=True).start()

    @app.get("/api/update")
    def update_status():
        from . import __version__

        return state.update_info or {"configured": False, "available": False, "local": __version__}

    # ------------------------------------------------------------- models

    @app.get("/api/models")
    def list_models():
        mdir = models_dir(ROOT)
        out = []
        for key, m in MODELS.items():
            out.append({
                "key": key, "name": m.name, "desc": m.desc,
                "scale": m.scale, "size_mb": m.size_mb,
                "available": find_model_file(key, mdir) is not None,
            })
        mdir.mkdir(parents=True, exist_ok=True)
        for p in sorted(mdir.glob("*.pth")):
            if p.name not in {m.file for m in MODELS.values()}:
                out.append({
                    "key": str(p), "name": p.stem, "desc": "Custom model (models/)",
                    "scale": None, "size_mb": p.stat().st_size / 1e6, "available": True,
                })
        return {"models": out, "device": device_info()}

    @app.post("/api/models/{key}/download")
    def start_download(key: str):
        if key not in MODELS:
            raise HTTPException(404, "unknown model")
        with state.lock:
            dl = state.downloads.get(key)
            if dl and dl["status"] == "downloading":
                return {"ok": True, "already": True}

        def work():
            from .models import download_model

            state.downloads[key] = {"status": "downloading", "progress": 0.0, "msg": "starting"}
            try:
                download_model(key, models_dir(ROOT),
                               cb=lambda f, m: state.downloads.update({key: {"status": "downloading", "progress": f, "msg": m}}))
                state.downloads[key] = {"status": "done", "progress": 1.0, "msg": "downloaded"}
            except Exception as e:  # noqa: BLE001
                state.downloads[key] = {"status": "error", "progress": 0.0, "msg": str(e)}

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True}

    @app.get("/api/downloads")
    def downloads():
        with state.lock:
            return {"downloads": state.downloads}

    # ------------------------------------------------------------- jobs

    def worker():
        while True:
            job = state.queue.get()
            try:
                run_job(job)
            except Exception as e:  # noqa: BLE001
                job["status"] = "error"
                job["error"] = str(e)
            finally:
                state.queue.task_done()

    def get_upscaler(model_key: str, tile: int, fp16: bool, device: str) -> Upscaler:
        key = (model_key, tile, fp16, device)
        if key not in state.upscalers:
            mdir = models_dir(ROOT)
            path = find_model_file(model_key, mdir)
            if not path:
                raise HTTPException(400, f"model '{model_key}' is not downloaded")
            state.upscalers[key] = Upscaler(path, device=device, fp16=fp16,
                                            tile=tile or 0)
        return state.upscalers[key]

    def run_job(job: dict):
        from PIL import Image

        job["status"] = "running"
        up = get_upscaler(job["model"], job["tile"], job["fp16"], job["device"])
        job["engine"] = f"{up.tile}px tile | {'fp16 GPU' if up.half else ('GPU' if up.device.type == 'cuda' else 'CPU')}"
        total = len(job["files"])
        for i, item in enumerate(job["files"]):
            if job.get("cancel"):
                job["status"] = "cancelled"
                return
            src: Path = item["src"]
            item["status"] = "running"
            job["msg"] = f"{src.name} ({i + 1}/{total})"

            def cb(frac, msg, i=i, total=total):
                job["progress"] = (i + frac) / total
                job["msg"] = f"{src.name}: {msg}" if total > 1 else msg

            img = Image.open(src)
            img.load()
            target = job.get("target")
            if target is None and job.get("scale"):
                s = job["scale"]
                target = (round(img.width * s), round(img.height * s))
            result = up.upscale(img, target=target, cb=cb)

            stem = src.stem
            tag = f"{target[0]}x{target[1]}" if target else f"x{int(up.scale)}"
            fmt = job["format"]
            has_alpha = result.mode == "RGBA"
            if fmt == "auto":
                fmt = "png" if has_alpha else "jpeg"
            ext = {"png": ".png", "jpeg": ".jpg", "webp": ".webp"}[fmt]
            out = OUT_DIR / f"{stem}_{tag}{ext}"
            n = 1
            while out.exists():
                out = OUT_DIR / f"{stem}_{tag}_{n}{ext}"
                n += 1
            if fmt == "jpeg":
                result.convert("RGB").save(out, quality=job["quality"])
            else:
                result.save(out, quality=job["quality"])

            item["status"] = "done"
            item["output"] = out.name
            item["size"] = list(result.size)
        job["status"] = "done"
        job["progress"] = 1.0
        job["msg"] = "complete"

    threading.Thread(target=worker, daemon=True).start()

    @app.post("/api/upscale")
    async def upscale(
        files: list[UploadFile] = File(...),
        model: str = Form("webphoto"),
        target_text: str = Form(""),      # "4k", "3840x2160" …
        scale: float = Form(0),           # 0 = use model's native scale
        tile: int = Form(0),
        fp16: bool = Form(True),
        device: str = Form("auto"),
        fmt: str = Form("auto"),
        quality: int = Form(95),
    ):
        if not files:
            raise HTTPException(400, "no files")
        tmp_dir = ROOT / "uploads"
        tmp_dir.mkdir(exist_ok=True)
        items = []
        for f in files[:64]:
            suffix = Path(f.filename or "image.png").suffix or ".png"
            dest = tmp_dir / f"{uuid.uuid4().hex[:8]}_{Path(f.filename or 'image.png').stem}{suffix}"
            with open(dest, "wb") as fh:
                while chunk := await f.read(1 << 20):
                    fh.write(chunk)
            items.append({"src": dest, "name": f.filename or dest.name, "status": "queued"})

        target = None
        if target_text:
            target = resolve_target(target_text)
        job = {
            "id": uuid.uuid4().hex[:10],
            "status": "queued",
            "progress": 0.0,
            "msg": "queued",
            "files": items,
            "model": model,
            "target": target,
            "scale": scale,
            "tile": tile,
            "fp16": fp16,
            "device": device,
            "format": fmt,
            "quality": quality,
            "created": time.time(),
            "cancel": False,
        }
        state.jobs[job["id"]] = job
        state.queue.put(job)
        return {"id": job["id"]}

    @app.get("/api/job/{job_id}")
    def job_status(job_id: str):
        job = state.jobs.get(job_id)
        if not job:
            raise HTTPException(404, "no such job")
        return {
            "id": job["id"], "status": job["status"], "progress": job["progress"],
            "msg": job["msg"], "engine": job.get("engine", ""),
            "files": [
                {"name": f["name"], "status": f["status"],
                 "output": f.get("output"), "size": f.get("size")}
                for f in job["files"]
            ],
        }

    @app.post("/api/job/{job_id}/cancel")
    def job_cancel(job_id: str):
        job = state.jobs.get(job_id)
        if job:
            job["cancel"] = True
        return {"ok": True}

    @app.get("/api/output/{name}")
    def output_file(name: str):
        p = (OUT_DIR / name).resolve()
        if not p.is_relative_to(OUT_DIR) or not p.exists():
            raise HTTPException(404, "not found")
        return FileResponse(p)

    # ------------------------------------------------------------- static

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app


def device_info() -> dict:
    dev = get_device("auto")
    info = {"type": dev.type, "tile": auto_tile_size(dev)}
    if dev.type == "cuda":
        import torch

        p = torch.cuda.get_device_properties(0)
        info.update(name=p.name, vram_gb=round(p.total_memory / 1e9, 1))
    return info


def serve(open_browser: bool = True, port: int = 8477):
    import urllib.request
    import uvicorn

    # if a PixelForge is already listening on this port, just open it —
    # never show a scary "address already in use" error for a double-launch
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/models", timeout=2) as r:
            if r.status == 200:
                url = f"http://127.0.0.1:{port}"
                print(f"\n  PixelForge is already running: {url}\n  Opening your browser to it.\n")
                if open_browser:
                    webbrowser.open(url)
                return
    except Exception:
        pass  # port free or foreign app — continue below

    # if some other app owns the port, quietly move to the next one
    for attempt in range(5):
        try:
            app = create_app()
            url = f"http://127.0.0.1:{port}"
            print(f"\n  PixelForge is running: {url}\n  (Ctrl+C to stop — nothing leaves your PC)\n")
            if open_browser:
                threading.Timer(1.2, lambda: webbrowser.open(url)).start()
            uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
            return
        except OSError:
            port += 1  # port taken by a different app, try the next door
    raise RuntimeError("Could not find a free port (8477–8481).")
