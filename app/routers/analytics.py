"""
مسارات التحليلات — Feature 5
تتبع المشاهدات وتحليل البيانات لكل فيديو
"""
import hashlib
import json
from typing import Optional, List
from datetime import datetime, timedelta
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

import httpx

from app.database import get_db, Video, ViewEvent, User
from app.auth import get_current_user, require_auth
from app.limiter import limiter

router = APIRouter()


# ── Schemas ───────────────────────────────────────────
class ViewEventCreate(BaseModel):
    seconds_watched: int = 0


class RetentionPoint(BaseModel):
    second:  int
    viewers: int


class CountryCount(BaseModel):
    country: str
    count:   int


class AnalyticsResponse(BaseModel):
    total_views:        int
    unique_viewers:     int
    avg_watch_duration: float
    retention_graph:    List[RetentionPoint]
    countries:          List[CountryCount]


# ══════════════════════════════════════════════════════
#  مساعد: جلب الدولة من IP
# ══════════════════════════════════════════════════════
async def _get_country_from_ip(ip: str) -> Optional[str]:
    """يستخدم ip-api.com المجاني (لا يحتاج API key)"""
    if ip in ("127.0.0.1", "::1", "localhost"):
        return "local"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            res = await client.get(f"http://ip-api.com/json/{ip}?fields=countryCode")
            if res.status_code == 200:
                data = res.json()
                return data.get("countryCode")
    except Exception:
        pass
    return None


def _hash_ip(ip: str) -> str:
    """يشفر IP للخصوصية (SHA-256)"""
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def _get_client_ip(request: Request) -> str:
    """استخرج IP الحقيقي (خلف Proxy/CDN)"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host or "unknown"


# ══════════════════════════════════════════════════════
#  POST /api/videos/{video_id}/view-event
# ══════════════════════════════════════════════════════
@router.post("/{video_id}/view-event", status_code=201)
@limiter.limit("120/hour")
async def record_view_event(
    request:   Request,
    video_id:  str,
    data:      ViewEventCreate,
    db:        Session = Depends(get_db),
):
    """
    يُسجَّل كل 30 ثانية من المشاهدة.
    لا يتطلب تسجيل دخول.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(404, "الفيديو غير موجود")

    ip = _get_client_ip(request)
    ip_hash = _hash_ip(ip)
    country = await _get_country_from_ip(ip)

    event = ViewEvent(
        video_id=video_id,
        viewer_ip_hash=ip_hash,
        country=country,
        watch_duration_seconds=max(0, data.seconds_watched),
    )
    db.add(event)
    db.commit()

    return {"recorded": True}


# ══════════════════════════════════════════════════════
#  GET /api/videos/{video_id}/analytics
# ══════════════════════════════════════════════════════
@router.get("/{video_id}/analytics", response_model=AnalyticsResponse)
def get_analytics(
    video_id:     str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_auth),
):
    """تحليلات مفصلة للفيديو — للمالك فقط"""
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.owner_id == current_user.id,
    ).first()
    if not video:
        raise HTTPException(404, "الفيديو غير موجود أو ليس لديك صلاحية")

    events = db.query(ViewEvent).filter(ViewEvent.video_id == video_id).all()

    if not events:
        return AnalyticsResponse(
            total_views=0,
            unique_viewers=0,
            avg_watch_duration=0.0,
            retention_graph=[],
            countries=[],
        )

    # ── إجماليات ─────────────────────────────────────
    total_views = len(events)
    unique_viewers = len(set(e.viewer_ip_hash for e in events if e.viewer_ip_hash))

    durations = [e.watch_duration_seconds for e in events if e.watch_duration_seconds > 0]
    avg_duration = round(sum(durations) / len(durations), 1) if durations else 0.0

    # ── مخطط الاحتفاظ (retention graph) ────────────────
    # كل نقطة = كم مشاهداً وصل لهذه اللحظة
    retention: dict[int, int] = defaultdict(int)
    for e in events:
        if e.watch_duration_seconds > 0:
            # كل 30 ثانية حتى مدة المشاهدة
            for sec in range(0, e.watch_duration_seconds + 1, 30):
                retention[sec] += 1

    retention_graph = [
        RetentionPoint(second=sec, viewers=count)
        for sec, count in sorted(retention.items())
    ]

    # ── توزيع الدول ──────────────────────────────────
    country_counts: dict[str, int] = defaultdict(int)
    for e in events:
        if e.country:
            country_counts[e.country] += 1

    countries = [
        CountryCount(country=c, count=n)
        for c, n in sorted(country_counts.items(), key=lambda x: -x[1])
    ]

    return AnalyticsResponse(
        total_views=total_views,
        unique_viewers=unique_viewers,
        avg_watch_duration=avg_duration,
        retention_graph=retention_graph,
        countries=countries,
    )
