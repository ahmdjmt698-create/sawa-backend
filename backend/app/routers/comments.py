"""
مسارات التعليقات بالطوابع الزمنية — Feature 3
"""
import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime

from app.database import get_db, Comment, Video, User
from app.auth import get_current_user
from app.limiter import limiter

router = APIRouter()


class CommentCreate(BaseModel):
    timestamp_seconds: float = Field(..., ge=0, description="الوقت بالثواني")
    text: str = Field(..., min_length=1, max_length=1000)
    author_name: str = Field("زائر", min_length=1, max_length=50)


class CommentResponse(BaseModel):
    id:                str
    video_id:          str
    timestamp_seconds: float
    text:              str
    author_name:       str
    created_at:        datetime

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════
#  GET /api/videos/{video_id}/comments
# ══════════════════════════════════════════════════════
@router.get("/videos/{video_id}/comments", response_model=List[CommentResponse])
def list_comments(
    video_id: str,
    db:       Session = Depends(get_db),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(404, "الفيديو غير موجود")

    comments = (
        db.query(Comment)
        .filter(Comment.video_id == video_id)
        .order_by(Comment.timestamp_seconds.asc())
        .all()
    )
    return comments


# ══════════════════════════════════════════════════════
#  POST /api/videos/{video_id}/comments
# ══════════════════════════════════════════════════════
@router.post("/videos/{video_id}/comments", response_model=CommentResponse, status_code=201)
@limiter.limit("30/hour")
def add_comment(
    request:  Request,
    video_id: str,
    data:     CommentCreate,
    db:       Session       = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(404, "الفيديو غير موجود")

    author = data.author_name
    user_id = None
    if current_user:
        author = current_user.name
        user_id = current_user.id

    comment = Comment(
        video_id=video_id,
        user_id=user_id,
        timestamp_seconds=data.timestamp_seconds,
        text=data.text.strip(),
        author_name=author,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


# ══════════════════════════════════════════════════════
#  DELETE /api/videos/comment/{comment_id}
# ══════════════════════════════════════════════════════
@router.delete("/videos/comment/{comment_id}", status_code=204)
def delete_comment(
    comment_id:   str,
    db:           Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(404, "التعليق غير موجود")

    if current_user:
        video = db.query(Video).filter(Video.id == comment.video_id).first()
        is_owner = video and video.owner_id == current_user.id
        is_author = comment.user_id == current_user.id
        if not (is_owner or is_author):
            raise HTTPException(403, "ليس لديك صلاحية حذف هذا التعليق")
    else:
        raise HTTPException(401, "يجب تسجيل الدخول لحذف التعليق")

    db.delete(comment)
    db.commit()
