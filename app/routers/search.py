"""
البحث العميق في الصوت — Deep Audio Search
ابحث في كل تسجيلاتك بكلمة واحدة
"""
import json
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db, Video, Transcript, TranscriptStatus, User
from app.auth import require_auth

router = APIRouter()


# ── Schemas ───────────────────────────────────────────
class SearchMatch(BaseModel):
    start:      float
    end:        float
    text:       str
    context:    str        # الجملة كاملة مع الكلمة مُظلَّلة
    speaker:    Optional[str] = None

class SearchResult(BaseModel):
    video_id:    str
    video_title: str
    created_at:  str
    duration:    Optional[float]
    matches:     List[SearchMatch]
    match_count: int

class SearchResponse(BaseModel):
    query:        str
    total_matches:int
    videos_found: int
    results:      List[SearchResult]


# ══════════════════════════════════════════════════════
#  GET /api/search?q=كلمة
# ══════════════════════════════════════════════════════
@router.get("", response_model=SearchResponse)
def deep_search(
    q:            str     = Query(..., min_length=1, description="كلمة البحث"),
    limit:        int     = Query(50, le=200),
    current_user: User    = Depends(require_auth),
    db:           Session = Depends(get_db),
):
    """
    يبحث في كل التسجيلات ويعيد الجمل التي تحتوي الكلمة مع توقيتها
    """
    # جلب كل فيديوهات المستخدم مع تفريغها
    videos = (
        db.query(Video)
        .filter(Video.owner_id == current_user.id)
        .order_by(Video.created_at.desc())
        .all()
    )

    results      = []
    total_matches = 0
    query_lower  = q.strip().lower()

    for video in videos:
        if not video.transcript:
            continue
        if video.transcript.status != TranscriptStatus.DONE:
            continue
        if not video.transcript.segments_json:
            continue

        # فرز الجمل التي تحتوي الكلمة
        try:
            segments = json.loads(video.transcript.segments_json)
        except json.JSONDecodeError:
            continue

        matches = []
        for seg in segments:
            text = seg.get("text", "")
            if query_lower in text.lower():
                # أنشئ نصاً مُظلَّلاً بعلامات HTML
                highlighted = _highlight(text, q)
                matches.append(SearchMatch(
                    start   = seg.get("start", 0),
                    end     = seg.get("end",   0),
                    text    = text,
                    context = highlighted,
                    speaker = seg.get("speaker"),
                ))

        if matches:
            total_matches += len(matches)
            results.append(SearchResult(
                video_id    = video.id,
                video_title = video.title,
                created_at  = video.created_at.strftime("%Y/%m/%d"),
                duration    = video.duration,
                matches     = matches,
                match_count = len(matches),
            ))

    # رتّب بالأكثر نتائج أولاً
    results.sort(key=lambda r: r.match_count, reverse=True)

    return SearchResponse(
        query         = q,
        total_matches = total_matches,
        videos_found  = len(results),
        results       = results[:limit],
    )


# ══════════════════════════════════════════════════════
#  GET /api/search/suggest?q=كلم  — اقتراحات بحث
# ══════════════════════════════════════════════════════
@router.get("/suggest")
def search_suggestions(
    q:            str     = Query(..., min_length=1),
    current_user: User    = Depends(require_auth),
    db:           Session = Depends(get_db),
):
    """يقترح كلمات شائعة في تسجيلاتك"""
    videos = (
        db.query(Video)
        .filter(Video.owner_id == current_user.id)
        .limit(20)
        .all()
    )

    words = set()
    for video in videos:
        if not video.transcript or not video.transcript.full_text:
            continue
        # استخرج كلمات تبدأ بنفس الحروف
        for word in video.transcript.full_text.split():
            word = word.strip(".,،؟!؛")
            if word.startswith(q) and len(word) > len(q):
                words.add(word)

    return {"suggestions": sorted(list(words))[:10]}


# ══════════════════════════════════════════════════════
#  Helper
# ══════════════════════════════════════════════════════
def _highlight(text: str, query: str) -> str:
    """يُظلّل الكلمة في النص بعلامة <mark>"""
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return pattern.sub(lambda m: f"<mark>{m.group()}</mark>", text)
