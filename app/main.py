from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from app.auth import COOKIE_MAX_AGE, COOKIE_NAME, AuthMiddleware, make_session_cookie, verify_session_cookie
from app.config import settings
from app.services.bird_classifier import classifier
from app.services.bird_detector import detector
from app.services.stream_capture import StreamCaptureError, stream_capture
from app.services.temporal_smoother import smoother


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title=settings.app_name)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class AnalyzeFrameRequest(BaseModel):
    client_id: str
    frame: str


class AnalyzeStreamRequest(BaseModel):
    client_id: str
    stream_url: str


@app.on_event("startup")
def startup_event() -> None:
    try:
        classifier.warmup()
        detector.warmup()
    except Exception:
        # The UI can still load; the first analyze request will surface the issue.
        pass


@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request) -> HTMLResponse:
    token = request.cookies.get(COOKIE_NAME)
    if token and verify_session_cookie(token):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None})


@app.post("/login")
async def login_post(request: Request, password: str = Form(...)):
    if password == settings.app_password:
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key=COOKIE_NAME,
            value=make_session_cookie(),
            httponly=True,
            samesite="lax",
            max_age=COOKIE_MAX_AGE,
        )
        return response
    return templates.TemplateResponse(
        request,
        "login.html",
        {"request": request, "error": "Wrong password — try again."},
        status_code=200,
    )


@app.get("/logout")
async def logout() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "frame_interval_ms": settings.frame_min_interval_ms,
            "default_stream_url": settings.default_stream_url,
        },
    )


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "app": settings.app_name}


@app.post("/api/analyze")
async def analyze_frame(payload: AnalyzeFrameRequest) -> dict:
    try:
        image = classifier.decode_data_url(payload.frame)
        return analyze_image(payload.client_id, image)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/analyze-stream")
async def analyze_stream(payload: AnalyzeStreamRequest) -> dict:
    try:
        frame = stream_capture.capture(payload.stream_url)
        result = analyze_image(payload.client_id, frame.image, preview_frame=frame.preview_data_url)
        result["source_mode"] = "stream"
        return result
    except StreamCaptureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def analyze_image(client_id: str, image, preview_frame: str | None = None) -> dict:
    context = detector.inspect(image)
    person_detected = (
        context.person_score is not None
        and context.person_score >= settings.detection_confidence_threshold
    )

    if not context.birds:
        smoother.clear(client_id)
        return {
            "detections": [],
            "best_match": None,
            "predictions": [],
            "confident": False,
            "smoothed_match": None,
            "detection": None,
            "crop_source": "none",
            "guidance": compose_guidance(
                confident=False,
                detected=False,
                frames_tracked=0,
                person_detected=person_detected,
                bird_count=0,
            ),
            "person_detected": person_detected,
            "preview_frame": preview_frame,
            "source_mode": "camera",
        }

    # Classify every detected bird independently
    detections = []
    for i, bird in enumerate(context.birds):
        cropped = detector.crop_detected_bird(image, bird)
        result = classifier.predict_image(cropped)
        smoothed = smoother.update(
            client_id=f"{client_id}:{i}",
            label=result["best_match"]["label"],
            score=result["best_match"]["score"],
            detected=True,
        )
        detections.append({
            "best_match": result["best_match"],
            "predictions": result["predictions"],
            "confident": result["confident"],
            "smoothed_match": smoothed,
            "detection": {
                "score": round(bird.score, 4),
                "confidence_percent": round(bird.score * 100, 1),
                "bbox": bird.normalized_bbox,
            },
        })

    # Clear smoothers for bird slots that no longer exist
    for i in range(len(context.birds), len(context.birds) + 4):
        smoother.clear(f"{client_id}:{i}")

    primary = detections[0]
    bird_count = len(detections)

    return {
        "detections": detections,
        # Top-level fields mirror primary detection for backward compat
        "best_match": primary["best_match"],
        "predictions": primary["predictions"],
        "confident": primary["confident"],
        "smoothed_match": primary["smoothed_match"],
        "detection": primary["detection"],
        "crop_source": "detected_bird",
        "guidance": compose_guidance(
            confident=primary["confident"],
            detected=True,
            frames_tracked=primary["smoothed_match"]["frames_tracked"],
            person_detected=person_detected,
            bird_count=bird_count,
        ),
        "person_detected": person_detected,
        "preview_frame": preview_frame,
        "source_mode": "camera",
    }


def compose_guidance(
    confident: bool,
    detected: bool,
    frames_tracked: int,
    person_detected: bool,
    bird_count: int = 1,
) -> str:
    if not detected:
        if person_detected:
            return "A person was detected, but no bird was found, so species ID was skipped."
        return "No confident bird box yet. Move closer, reduce clutter, or improve lighting."
    if bird_count > 1:
        return f"{bird_count} birds in frame — each is being identified independently."
    if confident:
        return (
            f"Tracked across {frames_tracked} frame"
            f"{'s' if frames_tracked != 1 else ''}. Keep it centered for steadier ID."
        )
    return "Bird found, but the species read is still soft. Hold steady a bit longer."
