from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional

from .core.config import settings
from .services.downloader import JobManager

app = FastAPI(title="TikTok Profile Downloader")

# Static and templates
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))

job_manager = JobManager()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "default_output": str(settings.DEFAULT_OUTPUT_ROOT)
    })


@app.post("/api/jobs")
async def create_job(
    background_tasks: BackgroundTasks,
    profile_url: str = Form(...),
    output_root: Optional[str] = Form(None),
    # Accept as string to avoid 422 when empty, convert manually
    max_videos: Optional[str] = Form(None),
    proxy: Optional[str] = Form(None),
):
    # Normalize and convert max_videos if provided
    mv: Optional[int] = None
    if max_videos is not None:
        s = str(max_videos).strip()
        if s:
            try:
                mv = int(s)
            except ValueError:
                mv = None

    job = job_manager.create_job(
        profile_url=profile_url.strip(),
        output_root=output_root or str(settings.DEFAULT_OUTPUT_ROOT),
        max_videos=mv,
        proxy=proxy,
    )
    background_tasks.add_task(job_manager.run_job, job.id)
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"detail": "Job not found"})
    return job.to_dict()


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    ok = job_manager.cancel_job(job_id)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "Job not found"})
    return {"status": "cancelled"}


@app.get("/features", response_class=HTMLResponse)
async def features(request: Request):
    return templates.TemplateResponse("features.html", {"request": request})


# Pricing page removed - using ad-based monetization model


@app.get("/support", response_class=HTMLResponse)
async def support(request: Request):
    return templates.TemplateResponse("support.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/youtube", response_class=HTMLResponse)
async def youtube(request: Request):
    return templates.TemplateResponse("youtube.html", {"request": request})


@app.get("/instagram", response_class=HTMLResponse)
async def instagram(request: Request):
    return templates.TemplateResponse("instagram.html", {"request": request})


@app.get("/audio", response_class=HTMLResponse)
async def audio(request: Request):
    return templates.TemplateResponse("audio.html", {"request": request})


@app.post("/api/instagram/jobs")
async def create_instagram_job(
    background_tasks: BackgroundTasks,
    profile_url: str = Form(...),
    output_root: Optional[str] = Form(None),
    max_videos: Optional[str] = Form(None),
    content_type: Optional[str] = Form("all"),
    quality: Optional[str] = Form("best"),
):
    try:
        # Validate Instagram URL
        url = profile_url.strip()
        if not url or not ("instagram.com" in url):
            return JSONResponse(
                status_code=400, 
                content={"error": "Por favor ingresa una URL válida de Instagram"}
            )
        
        # Normalize and convert max_videos if provided
        mv: Optional[int] = None
        if max_videos is not None:
            s = str(max_videos).strip()
            if s:
                try:
                    mv = int(s)
                except ValueError:
                    mv = None

        job = job_manager.create_job(
            profile_url=url,
            output_root=output_root or str(settings.DEFAULT_OUTPUT_ROOT),
            max_videos=mv,
            proxy=None,
        )
        background_tasks.add_task(job_manager.run_job, job.id)
        return {"job_id": job.id, "message": "Descarga iniciada. Si falla, puede ser por restricciones de la plataforma."}
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Error interno del servidor: {str(e)}"}
        )


@app.post("/api/youtube/jobs")
async def create_youtube_job(
    background_tasks: BackgroundTasks,
    profile_url: str = Form(...),
    output_root: Optional[str] = Form(None),
    max_videos: Optional[str] = Form(None),
    quality: Optional[str] = Form("best"),
    format: Optional[str] = Form("mp4"),
):
    try:
        # Validate YouTube URL
        url = profile_url.strip()
        if not url or not ("youtube.com" in url or "youtu.be" in url):
            return JSONResponse(
                status_code=400, 
                content={"error": "Por favor ingresa una URL válida de YouTube"}
            )
        
        # Normalize and convert max_videos if provided
        mv: Optional[int] = None
        if max_videos is not None:
            s = str(max_videos).strip()
            if s:
                try:
                    mv = int(s)
                except ValueError:
                    mv = None

        job = job_manager.create_job(
            profile_url=url,
            output_root=output_root or str(settings.DEFAULT_OUTPUT_ROOT),
            max_videos=mv,
            proxy=None,
        )
        background_tasks.add_task(job_manager.run_job, job.id)
        return {"job_id": job.id, "message": "Descarga iniciada. Videos individuales tienen mejor tasa de éxito."}
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Error interno del servidor: {str(e)}"}
        )


@app.post("/api/audio/jobs")
async def create_audio_job(
    background_tasks: BackgroundTasks,
    profile_url: str = Form(...),
    output_root: Optional[str] = Form(None),
    content_type: Optional[str] = Form("audio"),
    audio_quality: Optional[str] = Form("192"),
):
    try:
        url = profile_url.strip()
        if not url:
            return JSONResponse(
                status_code=400, 
                content={"error": "Por favor ingresa una URL válida"}
            )
        
        job = job_manager.create_job(
            profile_url=url,
            output_root=output_root or str(settings.DEFAULT_OUTPUT_ROOT),
            max_videos=1,
            proxy=None,
        )
        background_tasks.add_task(job_manager.run_job, job.id)
        return {"job_id": job.id, "message": "Extracción iniciada. Algunos contenidos pueden no estar disponibles."}
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Error interno del servidor: {str(e)}"}
        )


# Instagram job status and cancel endpoints
@app.get("/api/instagram/jobs/{job_id}")
async def get_instagram_job(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"detail": "Job not found"})
    return job.to_dict()


@app.post("/api/instagram/jobs/{job_id}/cancel")
async def cancel_instagram_job(job_id: str):
    ok = job_manager.cancel_job(job_id)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "Job not found"})
    return {"status": "cancelled"}


# YouTube job status and cancel endpoints
@app.get("/api/youtube/jobs/{job_id}")
async def get_youtube_job(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"detail": "Job not found"})
    return job.to_dict()


@app.post("/api/youtube/jobs/{job_id}/cancel")
async def cancel_youtube_job(job_id: str):
    ok = job_manager.cancel_job(job_id)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "Job not found"})
    return {"status": "cancelled"}


# Audio job status and cancel endpoints
@app.get("/api/audio/jobs/{job_id}")
async def get_audio_job(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"detail": "Job not found"})
    return job.to_dict()


@app.post("/api/audio/jobs/{job_id}/cancel")
async def cancel_audio_job(job_id: str):
    ok = job_manager.cancel_job(job_id)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "Job not found"})
    return {"message": "Job cancelled"}


@app.post("/api/analytics/ad-impression")
async def track_ad_impression(request: Request):
    """Track ad impression for analytics"""
    try:
        data = await request.json()
        # In a real implementation, you would store this in a database
        # For now, we'll just log it
        print(f"Ad impression tracked: {data}")
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)