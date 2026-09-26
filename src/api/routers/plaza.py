"""Anonymous story reading and owner-controlled plaza publication."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, or_

from src.api.deps import get_current_user
from src.database.models import Game, GameState, SessionLocal, StoryPublication, User

router = APIRouter()


class PublicationUpdate(BaseModel):
    enabled: bool


class OwnedStory(BaseModel):
    game_id: int
    title: str
    chapter_count: int
    can_publish: bool
    enabled: bool
    public_id: Optional[str] = None
    updated_at: Optional[str] = None


class PublicChapter(BaseModel):
    number: int
    date: Optional[str] = None
    text: str


class PublicStoryCard(BaseModel):
    public_id: str
    title: str
    author_name: str
    chapter_count: int
    excerpt: str
    updated_at: Optional[str] = None


class PublicStoryList(BaseModel):
    items: List[PublicStoryCard]
    has_more: bool
    next_offset: int


class PublicStory(PublicStoryCard):
    chapters: List[PublicChapter]


def _utc(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _latest_state(db, game: Game) -> dict:
    snapshot = (
        db.query(GameState)
        .filter(GameState.game_id == game.game_id)
        .order_by(GameState.state_id.desc())
        .first()
    )
    state = snapshot.state_json if snapshot else game.initial_state
    return state if isinstance(state, dict) else {}


def _title(state: dict) -> str:
    value = state.get("player_name")
    return value.strip() if isinstance(value, str) and value.strip() else "未命名的故事"


def _chapters(state: dict) -> List[PublicChapter]:
    """Only materialized, completed history; never current_event_data or raw state."""
    daily = state.get("day_history")
    if not isinstance(daily, list) or not daily:
        daily = []
        legacy = state.get("round_history")
        if isinstance(legacy, list):
            for record in legacy:
                if not isinstance(record, dict):
                    continue
                daily.append({
                    "event_description": record.get("event_description"),
                    "transition_text": record.get("story_continuation"),
                    "choice": record.get("choice"),
                    "story_date": (record.get("date_info") or {}).get("date")
                    if isinstance(record.get("date_info"), dict) else None,
                })

    chapters = []
    for record in daily:
        if not isinstance(record, dict):
            continue
        if "choice" not in record:
            continue
        parts = [
            value.strip()
            for value in (record.get("event_description"), record.get("transition_text"))
            if isinstance(value, str) and value.strip()
        ]
        if not parts:
            continue
        date = record.get("story_date")
        chapters.append(PublicChapter(
            number=len(chapters) + 1,
            date=date if isinstance(date, str) and date else None,
            text="\n\n".join(parts),
        ))
    return chapters


def _owned_story(db, game: Game, publication: Optional[StoryPublication]) -> OwnedStory:
    state = _latest_state(db, game)
    count = len(_chapters(state))
    return OwnedStory(
        game_id=game.game_id,
        title=_title(state),
        chapter_count=count,
        can_publish=count > 0,
        enabled=bool(publication and publication.enabled),
        public_id=publication.public_id if publication else None,
        updated_at=_utc(game.updated_at),
    )


@router.get("/mine", response_model=List[OwnedStory])
def list_owned_stories(response: Response, user_id: int = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    with SessionLocal() as db:
        rows = (
            db.query(Game, StoryPublication)
            .outerjoin(StoryPublication, StoryPublication.game_id == Game.game_id)
            .filter(Game.user_id == user_id)
            .order_by(Game.updated_at.desc(), Game.game_id.desc())
            .all()
        )
        return [_owned_story(db, game, publication) for game, publication in rows]


@router.put("/mine/{game_id}", response_model=OwnedStory)
def set_story_publication(
    game_id: int,
    update: PublicationUpdate,
    response: Response,
    user_id: int = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    with SessionLocal() as db:
        game = db.query(Game).filter(Game.game_id == game_id, Game.user_id == user_id).first()
        if game is None:
            raise HTTPException(status_code=404, detail="Story not found")
        publication = db.query(StoryPublication).filter(StoryPublication.game_id == game_id).first()
        owned = _owned_story(db, game, publication)
        if update.enabled and not owned.can_publish:
            raise HTTPException(status_code=409, detail="Finish a chapter before sharing this story")
        if publication is None and update.enabled:
            publication = StoryPublication(game_id=game_id, public_id=uuid4().hex, enabled=True)
            db.add(publication)
        elif publication is not None:
            publication.enabled = update.enabled
        db.commit()
        return _owned_story(db, game, publication)


@router.get("", response_model=PublicStoryList)
def list_public_stories(
    response: Response,
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    response.headers["Cache-Control"] = "no-store"
    with SessionLocal() as db:
        latest = (
            db.query(GameState.game_id, func.max(GameState.state_id).label("state_id"))
            .group_by(GameState.game_id)
            .subquery()
        )
        query = (
            db.query(StoryPublication, Game, User, GameState.state_json)
            .join(Game, Game.game_id == StoryPublication.game_id)
            .join(User, User.user_id == Game.user_id)
            .outerjoin(latest, latest.c.game_id == Game.game_id)
            .outerjoin(GameState, GameState.state_id == latest.c.state_id)
            .filter(StoryPublication.enabled.is_(True))
        )
        search = q.strip()
        if search:
            title = func.coalesce(
                GameState.state_json["player_name"].as_string(),
                Game.initial_state["player_name"].as_string(),
                "",
            )
            query = query.filter(or_(title.ilike(f"%{search}%"), User.display_name.ilike(f"%{search}%")))
        items = []
        scan_offset = offset
        next_offset = offset
        ordered = query.order_by(Game.updated_at.desc(), Game.game_id.desc())
        while True:
            rows = ordered.offset(scan_offset).limit(50).all()
            if not rows:
                break
            for publication, game, user, saved_state in rows:
                scan_offset += 1
                state = saved_state if isinstance(saved_state, dict) else game.initial_state
                state = state if isinstance(state, dict) else {}
                chapters = _chapters(state)
                if not chapters:
                    continue
                if len(items) == limit:
                    return PublicStoryList(items=items, has_more=True, next_offset=next_offset)
                items.append(PublicStoryCard(
                    public_id=publication.public_id,
                    title=_title(state),
                    author_name=user.display_name or "匿名作者",
                    chapter_count=len(chapters),
                    excerpt=chapters[0].text[:160],
                    updated_at=_utc(game.updated_at),
                ))
                next_offset = scan_offset
            if len(rows) < 50:
                break
        return PublicStoryList(items=items, has_more=False, next_offset=next_offset)


@router.get("/{public_id}", response_model=PublicStory)
def get_public_story(public_id: str, response: Response):
    response.headers["Cache-Control"] = "no-store"
    with SessionLocal() as db:
        row = (
            db.query(StoryPublication, Game, User)
            .join(Game, Game.game_id == StoryPublication.game_id)
            .join(User, User.user_id == Game.user_id)
            .filter(StoryPublication.public_id == public_id, StoryPublication.enabled.is_(True))
            .first()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Story unavailable", headers={"Cache-Control": "no-store"})
        publication, game, user = row
        state = _latest_state(db, game)
        chapters = _chapters(state)
        if not chapters:
            raise HTTPException(status_code=404, detail="Story unavailable", headers={"Cache-Control": "no-store"})
        return PublicStory(
            public_id=publication.public_id,
            title=_title(state),
            author_name=user.display_name or "匿名作者",
            chapter_count=len(chapters),
            excerpt=chapters[0].text[:160],
            updated_at=_utc(game.updated_at),
            chapters=chapters,
        )
