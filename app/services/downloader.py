from __future__ import annotations

import threading
import uuid
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Optional, List

from loguru import logger
import yt_dlp

from ..core.config import settings


@dataclass
class Job:
    id: str
    profile_url: str
    output_root: Path
    max_videos: Optional[int] = None
    proxy: Optional[str] = None

    # runtime fields
    status: str = "queued"  # queued|running|completed|cancelled|failed
    progress: float = 0.0
    total: Optional[int] = None
    downloaded: int = 0
    failed: int = 0
    message: str = ""
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())
    _cancel_event: threading.Event = field(default_factory=threading.Event, repr=False, compare=False)

    def to_dict(self) -> Dict:
        # Evitar deepcopy de dataclasses.asdict que intenta copiar _thread.lock
        return {
            "id": self.id,
            "profile_url": self.profile_url,
            "output_root": str(self.output_root),
            "max_videos": self.max_videos,
            "proxy": self.proxy,
            "status": self.status,
            "progress": self.progress,
            "total": self.total,
            "downloaded": self.downloaded,
            "failed": self.failed,
            "message": self.message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class JobManager:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_job(self, profile_url: str, output_root: str, max_videos: Optional[int], proxy: Optional[str]) -> Job:
        job_id = str(uuid.uuid4())
        output_root_path = Path(output_root)
        output_root_path.mkdir(parents=True, exist_ok=True)
        job = Job(
            id=job_id,
            profile_url=profile_url,
            output_root=output_root_path,
            max_videos=max_videos,
            proxy=proxy,
        )
        with self._lock:
            self._jobs[job_id] = job
        logger.info(f"Created job {job_id} for {profile_url}")
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        job = self.get_job(job_id)
        if not job:
            return False
        job._cancel_event.set()
        job.status = "cancelled"
        job.updated_at = time.time()
        logger.info(f"Cancelled job {job_id}")
        return True

    def run_job(self, job_id: str):
        job = self.get_job(job_id)
        if not job or job.status == "cancelled":
            return
        job.status = "running"
        job.updated_at = time.time()

        # Output template: create folder per profile under output_root
        out_dir = job.output_root
        out_dir.mkdir(parents=True, exist_ok=True)
        outtmpl = str(out_dir / "%(uploader)s/%(upload_date>%Y-%m-%d)s_%(id)s.%(ext)s")

        # Progress hooks
        def progress_hook(d):
            if job._cancel_event.is_set():
                raise yt_dlp.utils.DownloadError("Job cancelled by user")
            if d.get('status') == 'downloading':
                # d may contain 'total_bytes_estimate' or 'total_bytes'
                job.message = d.get('filename', '')
                job.updated_at = time.time()
            elif d.get('status') == 'finished':
                job.downloaded += 1
                job.message = f"Downloaded {d.get('filename', '')}"
                job.updated_at = time.time()

        # TikTok user URL can be like https://www.tiktok.com/@username
        # yt-dlp will enumerate all videos available (subject to rate limits/privileges)
        url = job.profile_url

        # Configuración específica para Instagram
        if "instagram.com" in url.lower():
            ydl_opts = {
                "outtmpl": outtmpl,
                "noplaylist": True,  # Solo el post específico
                "progress_hooks": [progress_hook],
                "format": "best[height<=720]",  # Formato más compatible
                "merge_output_format": "mp4",
                "retries": 3,
                "fragment_retries": 5,
                "ignoreerrors": True,
                "quiet": True,
                "no_warnings": True,
                # Headers específicos para Instagram
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-us,en;q=0.5",
                    "Accept-Encoding": "gzip,deflate",
                    "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.7",
                    "Keep-Alive": "300",
                    "Connection": "keep-alive",
                },
                # Configuraciones adicionales para Instagram
                "extractor_args": {
                    "instagram": {
                        "api_version": "v1"
                    }
                }
            }
        elif "youtube.com" in url.lower() or "youtu.be" in url.lower():
            # Configuración específica para YouTube con múltiples fallbacks
            ydl_opts = {
                "outtmpl": outtmpl,
                "noplaylist": True,
                "progress_hooks": [progress_hook],
                "format": "best[height<=720]/best",
                "merge_output_format": "mp4",
                "retries": 5,
                "fragment_retries": 10,
                "ignoreerrors": True,
                "quiet": True,
                "no_warnings": True,
                # Rate limiting
                "sleep_interval": 3,
                "max_sleep_interval": 10,
                "sleep_interval_requests": 2,
                # Headers actualizados para 2024
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                },
                # Configuraciones avanzadas con múltiples fallbacks
                "extractor_args": {
                    "youtube": {
                        # Orden de clientes: Android primero (más estable)
                        "player_client": ["android", "android_embedded", "ios", "ios_embedded", "web", "mweb", "tv_embedded"],
                        "player_skip": ["webpage", "configs"],
                        "skip": ["hls"],
                        "comment_sort": ["top"],
                        "max_comments": [0],
                        # Configuraciones adicionales para bypass
                        "include_live_dash": False,
                        "include_hls_manifest": False,
                    }
                },
                # Configuraciones adicionales
                "writesubtitles": False,
                "writeautomaticsub": False,
                "writedescription": False,
                "writeinfojson": False,
                "writethumbnail": False,
                "extract_flat": False,
                # Configuración de cookies y sesión
                "cookiefile": None,
                "no_check_certificate": True,
            }
        else:
            # Configuración para otras plataformas (TikTok, etc.)
            ydl_opts = {
                "outtmpl": outtmpl,
                "noplaylist": False,
                "progress_hooks": [progress_hook],
                "format": "bv*+ba/b",  # best video+audio or best
                "merge_output_format": "mp4",
                "concurrent_fragment_downloads": settings.YTDLP_CONCURRENCY,
                "retries": 5,
                "fragment_retries": 10,
                "ignoreerrors": True,
                "quiet": True,
                "no_warnings": True,
            }
        if job.proxy:
            ydl_opts["proxy"] = job.proxy

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Pre-extract to count entries (optional; may be heavy). We'll stream instead.
                # If max_videos provided, we limit by slicing the entries.
                info = None
                try:
                    info = ydl.extract_info(url, download=False)
                except Exception as extract_error:
                    logger.warning(f"First extraction failed: {extract_error}. Trying fallback methods...")
                    info = None
                    
                    # Múltiples fallbacks para YouTube
                    if "youtube.com" in url.lower() or "youtu.be" in url.lower():
                        fallback_configs = [
                            # Fallback 1: Solo Android client
                            {
                                "outtmpl": outtmpl,
                                "noplaylist": True,
                                "progress_hooks": [progress_hook],
                                "format": "best[height<=480]/best",
                                "ignoreerrors": True,
                                "quiet": True,
                                "no_warnings": True,
                                "extractor_args": {
                                    "youtube": {
                                        "player_client": ["android"],
                                        "player_skip": ["webpage"],
                                    }
                                }
                            },
                            # Fallback 2: iOS client únicamente
                            {
                                "outtmpl": outtmpl,
                                "noplaylist": True,
                                "progress_hooks": [progress_hook],
                                "format": "worst/best",
                                "ignoreerrors": True,
                                "quiet": True,
                                "no_warnings": True,
                                "extractor_args": {
                                    "youtube": {
                                        "player_client": ["ios"],
                                    }
                                }
                            },
                            # Fallback 3: Configuración mínima
                            {
                                "outtmpl": outtmpl,
                                "noplaylist": True,
                                "progress_hooks": [progress_hook],
                                "format": "best",
                                "ignoreerrors": True,
                                "quiet": True,
                                "no_warnings": True,
                            }
                        ]
                        
                        for i, fallback_opts in enumerate(fallback_configs, 1):
                            try:
                                if job.proxy:
                                    fallback_opts["proxy"] = job.proxy
                                
                                logger.info(f"Trying YouTube fallback {i}/3...")
                                job.message = f"Reintentando con método alternativo {i}/3..."
                                job.updated_at = time.time()
                                
                                with yt_dlp.YoutubeDL(fallback_opts) as fallback_ydl:
                                    info = fallback_ydl.extract_info(url, download=False)
                                    if info:
                                        logger.info(f"YouTube fallback {i} successful!")
                                        break
                            except Exception as fallback_error:
                                logger.warning(f"YouTube fallback {i} failed: {fallback_error}")
                                continue
                    else:
                        # Fallback simple para otras plataformas
                        try:
                            simple_opts = {
                                "outtmpl": outtmpl,
                                "noplaylist": True,
                                "progress_hooks": [progress_hook],
                                "format": "best",
                                "ignoreerrors": True,
                                "quiet": True,
                                "no_warnings": True,
                            }
                            if job.proxy:
                                simple_opts["proxy"] = job.proxy
                            
                            with yt_dlp.YoutubeDL(simple_opts) as simple_ydl:
                                info = simple_ydl.extract_info(url, download=False)
                        except Exception as simple_error:
                            logger.error(f"Simple fallback also failed: {simple_error}")
                            info = None
                
                if info is None:
                    # Mensaje específico para errores de extracción de YouTube
                    if "youtube.com" in url.lower() or "youtu.be" in url.lower():
                        job.status = "failed"
                        job.message = "⚠️ YouTube ha actualizado su sistema. Intenta actualizar yt-dlp con: pip install -U yt-dlp"
                        job.updated_at = time.time()
                        logger.error(f"Job {job.id} failed: YouTube extraction failed, may need yt-dlp update")
                    else:
                        job.status = "failed"
                        job.message = "No se pudo acceder al contenido. Posibles causas: video privado, restringido por región, eliminado, o URL incorrecta."
                        job.updated_at = time.time()
                        logger.error(f"Job {job.id} failed: No info extracted from {url}")
                    return

                entries: List[Dict] = []
                if "entries" in info and isinstance(info["entries"], list):
                    # Some extractors return a flat list
                    entries = [e for e in info["entries"] if e]
                else:
                    # Single video
                    entries = [info]

                if job.max_videos:
                    entries = entries[: job.max_videos]

                job.total = len(entries)
                job.progress = 0.0
                job.updated_at = time.time()

                for idx, entry in enumerate(entries, start=1):
                    if job._cancel_event.is_set():
                        raise yt_dlp.utils.DownloadError("Cancelled")
                    vid_url = entry.get("webpage_url") or entry.get("url")
                    if not vid_url:
                        job.failed += 1
                        continue
                    
                    # Retry logic with exponential backoff for rate limits
                    max_retries = 3
                    retry_delay = 5  # Start with 5 seconds
                    
                    for attempt in range(max_retries):
                        try:
                            if attempt > 0:
                                # Exponential backoff: 5s, 15s, 45s
                                wait_time = retry_delay * (3 ** attempt)
                                logger.info(f"Rate limit retry {attempt + 1}/{max_retries}, waiting {wait_time}s...")
                                job.message = f"Rate limit detectado, reintentando en {wait_time}s... ({attempt + 1}/{max_retries})"
                                job.updated_at = time.time()
                                time.sleep(wait_time)
                            
                            ydl.download([vid_url])
                            break  # Success, exit retry loop
                            
                        except yt_dlp.utils.DownloadError as e:
                            error_msg = str(e).lower()
                            if "rate" in error_msg or "limit" in error_msg or "try again later" in error_msg:
                                if attempt < max_retries - 1:
                                    logger.warning(f"Rate limit detected for {vid_url}, attempt {attempt + 1}/{max_retries}")
                                    continue  # Retry
                                else:
                                    logger.error(f"Max retries exceeded for rate limit: {vid_url}")
                                    job.failed += 1
                                    job.message = f"Video bloqueado por rate limit después de {max_retries} intentos"
                            else:
                                logger.exception(f"Download failed for {vid_url}: {e}")
                                job.failed += 1
                                break  # Don't retry for non-rate-limit errors
                        except Exception as e:
                            logger.exception(f"Download failed for {vid_url}: {e}")
                            job.failed += 1
                            break  # Don't retry for unexpected errors
                    
                    # Additional delay between videos to prevent rate limiting
                    if "youtube.com" in url.lower() or "youtu.be" in url.lower():
                        time.sleep(2)  # 2 second delay between YouTube videos
                    
                    job.progress = idx / job.total if job.total else 0.0
                    job.updated_at = time.time()

            if job.status != "cancelled":
                job.status = "completed"
                job.message = f"Done. Downloaded={job.downloaded}, Failed={job.failed}"
                job.updated_at = time.time()
        except Exception as e:
            if job.status != "cancelled":
                job.status = "failed"
                job.message = str(e)
                job.updated_at = time.time()
                logger.exception(f"Job {job.id} failed: {e}")