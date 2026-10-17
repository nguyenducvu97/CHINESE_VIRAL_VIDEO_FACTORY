"""Control Center & Operations FastAPI Backend Application for CVVF."""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.core.models import ProcessingStatus, RightsStatus, StandardVideoItem
from src.discovery.adapters.bilibili_adapter import BilibiliDiscoveryAdapter
from src.discovery.dedup import DeduplicationStore
from src.discovery.service import DiscoveryService
from src.dubbing.adapters.mock_tts import MockTTSAdapter
from src.dubbing.service import DubbingService
from src.rendering.ffmpeg_worker import FFmpegRenderWorker
from src.scoring.viral_scorer import ViralScorer
from src.subtitle.adapters.glossary_translator import GlossaryTranslationAdapter
from src.subtitle.adapters.mock_asr import MockASRAdapter
from src.subtitle.cache import SubtitleCache
from src.subtitle.service import SubtitleService

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Chinese Viral Video Factory — Control Center",
    version="1.0.0",
    description="Operational dashboard and orchestrator for CVVF pipeline",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DISCOVERED_PATH = DATA_DIR / "discovered_videos.json"

# In-memory operational audit logs and budget state
AUDIT_LOGS: List[Dict[str, Any]] = []
BUDGET_STATE = {
    "daily_limit_usd": 0.00,  # Strict $0.00 default (local execution only)
    "spent_today_usd": 0.00,
    "circuit_breaker_active": False,
    "paid_apis_enabled": False,
}


def log_operation(action: str, target: str, status: str, details: Optional[str] = None):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "target": target,
        "status": status,
        "details": details or "",
    }
    AUDIT_LOGS.insert(0, entry)
    if len(AUDIT_LOGS) > 100:
        AUDIT_LOGS.pop()


# Pipeline Singletons
dedup_store = DeduplicationStore(storage_path=DISCOVERED_PATH)
discovery_service = DiscoveryService(storage_path=DISCOVERED_PATH)
discovery_service.register_adapter(BilibiliDiscoveryAdapter())
viral_scorer = ViralScorer()
subtitle_service = SubtitleService(
    asr_adapter=MockASRAdapter(),
    translation_adapter=GlossaryTranslationAdapter(),
    cache=SubtitleCache(cache_dir=DATA_DIR / "cache" / "subtitles"),
)
dubbing_service = DubbingService(
    tts_adapter=MockTTSAdapter(),
    cache_dir=DATA_DIR / "cache" / "tts",
)
render_worker = FFmpegRenderWorker()


# Request / Response Schemas
class ApprovalRequest(BaseModel):
    notes: Optional[str] = None


class DiscoveryTriggerRequest(BaseModel):
    platform: str = "bilibili"
    page: int = 1
    page_size: int = 5
    dry_run: bool = False


# API Endpoints
@app.get("/api/health")
def get_health():
    """Health check and runtime status report."""
    return {
        "status": "healthy",
        "service": "cvvf-control-center",
        "version": "1.0.0",
        "port": 3080,
        "isolated_namespace": "cvvf",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_videos_tracked": dedup_store.count(),
    }


@app.get("/api/budget")
def get_budget():
    """Cost tracking and circuit breaker status."""
    return BUDGET_STATE


@app.get("/api/audit-logs")
def get_audit_logs():
    """Operational audit trail."""
    return AUDIT_LOGS


@app.get("/api/videos")
def list_videos(
    platform: Optional[str] = None,
    rights_status: Optional[str] = None,
    processing_status: Optional[str] = None,
):
    """List tracked videos with optional filters."""
    items = dedup_store.get_all()
    results = []
    for it in items:
        if platform and it.source_platform.lower() != platform.lower():
            continue
        if rights_status and it.rights_status.value != rights_status:
            continue
        if processing_status and it.processing_status.value != processing_status:
            continue
        # Check if scored
        scored = viral_scorer.score_video(it)
        d = it.model_dump()
        d["scored"] = scored.model_dump()
        results.append(d)

    return {"total": len(results), "videos": results}


@app.get("/api/videos/{dedup_key:path}")
def get_video_detail(dedup_key: str):
    """Retrieve full metadata, scoring, and lifecycle detail for a video."""
    item = dedup_store.get(dedup_key)
    if not item:
        raise HTTPException(status_code=404, detail="Video not found")

    scored = viral_scorer.score_video(item)
    return {
        "video": item.model_dump(),
        "scored": scored.model_dump(),
    }


@app.post("/api/discovery/trigger")
def trigger_discovery(req: DiscoveryTriggerRequest):
    """Trigger video discovery run."""
    log_operation("DISCOVERY_RUN", req.platform, "STARTED")
    try:
        res = discovery_service.discover_trending(
            platform_name=req.platform,
            page=req.page,
            page_size=req.page_size,
            dry_run=req.dry_run,
        )
        log_operation(
            "DISCOVERY_RUN",
            req.platform,
            "COMPLETED",
            f"Fetched: {res.total_fetched}, New: {res.new_unique_added}, Dupes: {res.duplicates_filtered}",
        )
        return {
            "total_fetched": res.total_fetched,
            "new_unique_added": res.new_unique_added,
            "duplicates_filtered": res.duplicates_filtered,
            "errors": res.errors,
        }
    except Exception as e:
        log_operation("DISCOVERY_RUN", req.platform, "FAILED", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/videos/{dedup_key:path}/approve")
def approve_video_rights(dedup_key: str, req: Optional[ApprovalRequest] = None):
    """Human-in-the-loop gate: explicitly approve rights and authorize processing."""
    item = dedup_store.get(dedup_key)
    if not item:
        raise HTTPException(status_code=404, detail="Video not found")

    item.rights_status = RightsStatus.APPROVED_BY_USER
    item.processing_status = ProcessingStatus.APPROVED_FOR_PUBLISH
    dedup_store.add(item)  # Re-persist
    log_operation("RIGHTS_APPROVAL", dedup_key, "APPROVED", req.notes if req else "User manual approval")
    return {"status": "success", "message": "Video rights successfully approved"}


@app.post("/api/videos/{dedup_key:path}/reject")
def reject_video(dedup_key: str, req: Optional[ApprovalRequest] = None):
    """Human-in-the-loop gate: reject video from publishing."""
    item = dedup_store.get(dedup_key)
    if not item:
        raise HTTPException(status_code=404, detail="Video not found")

    item.rights_status = RightsStatus.REJECTED
    item.processing_status = ProcessingStatus.FILTERED_OUT
    dedup_store.add(item)
    log_operation("RIGHTS_APPROVAL", dedup_key, "REJECTED", req.notes if req else "User manual rejection")
    return {"status": "success", "message": "Video rejected"}


@app.post("/api/videos/{dedup_key:path}/process-all")
def process_full_pipeline(dedup_key: str):
    """Execute end-to-end processing (ASR, Vietsub, Dubbing, Render)."""
    item = dedup_store.get(dedup_key)
    if not item:
        raise HTTPException(status_code=404, detail="Video not found")

    if item.rights_status != RightsStatus.APPROVED_BY_USER:
        raise HTTPException(
            status_code=400,
            detail="Human review required: Video rights must be APPROVED_BY_USER before full processing",
        )

    log_operation("PIPELINE_RUN", dedup_key, "STARTED")

    # Step 1: Ensure audio fixture
    audio_path = Path("fixtures/audio/sample_chinese_audio.wav")
    if not audio_path.exists():
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(
            b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        )

    # Step 2: Subtitle
    sub_doc, sub_report, srt_content = subtitle_service.process_audio(
        audio_path=audio_path,
        item_id=item.id,
        dedup_key=item.dedup_key,
    )

    # Step 3: Dubbing
    dub_res = dubbing_service.dub_video(
        subtitle_doc=sub_doc,
        original_audio_path=audio_path,
        output_dir=DATA_DIR / "output" / "dubbing",
    )

    # Step 4: Video sample
    sample_video = Path("fixtures/sample_videos/demo_video.mp4")
    if not sample_video.exists():
        from scripts.run_render import ensure_sample_video
        ensure_sample_video(sample_video)

    srt_file = DATA_DIR / "output" / f"sub_{item.id}.srt"
    srt_file.write_text(srt_content, encoding="utf-8")

    # Step 5: Render Vietsub & Dubbed
    render_out = DATA_DIR / "output" / "rendered"
    render_res = render_worker.render_dubbed_vietsub(
        source_video_path=sample_video,
        dubbed_audio_path=Path(dub_res.mixed_audio_path),
        srt_path=srt_file,
        output_dir=render_out,
        item_id=item.id,
        dedup_key=item.dedup_key,
    )

    item.processing_status = ProcessingStatus.RENDERED
    dedup_store.add(item)

    log_operation("PIPELINE_RUN", dedup_key, "COMPLETED", f"Rendered: {render_res.output_video_path}")

    return {
        "status": "success",
        "item_id": item.id,
        "processing_status": item.processing_status.value,
        "subtitles_count": len(sub_doc.segments),
        "dubbed_audio": dub_res.mixed_audio_path,
        "rendered_video": render_res.output_video_path,
        "qc_passed": render_res.qc_inspection.is_valid,
    }


# Mount Static Dashboard UI
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def serve_dashboard():
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "CVVF Control Center API is running. UI not found."}
