from contextlib import asynccontextmanager
from datetime import datetime, timezone, date
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from db import SessionLocal
from models import User, LifeArea, Track, Module, Goal, Task

def session():
    with SessionLocal() as db: yield db

def user(db: Session):
    obj = db.scalar(select(User).limit(1))
    if not obj:
        obj = User()
        db.add(obj)
        db.commit()
        db.refresh(obj)
    return obj

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Aniro API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class AreaIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    color_key: str = "lime"
    icon_key: str = "target"
    sort_order: int = 0

class TrackIn(BaseModel):
    life_area_id: str
    name: str = Field(min_length=1, max_length=120)
    color_key: str = "lime"
    sort_order: int = 0

class ModuleIn(BaseModel):
    track_id: str
    name: str = Field(min_length=1, max_length=120)
    status: Literal["active", "completed"] = "active"
    sort_order: int = 0

class GoalIn(BaseModel):
    life_area_id: str
    track_id: str | None = None
    module_id: str | None = None
    parent_goal_id: str | None = None
    horizon: Literal["10y", "5y", "2y", "1y", "3mo", "month", "week"]
    title: str = Field(min_length=1, max_length=240)
    description: str = ""
    status: Literal["active", "completed"] = "active"
    target_date: str | None = None
    sort_order: int = 0

def get(db, cls, id):
    obj = db.get(cls, id)
    if not obj: raise HTTPException(404, "Record not found")
    return obj

def as_dict(obj):
    return {col.name: (val.isoformat() if isinstance(val := getattr(obj, col.name), datetime) else val) for col in obj.__table__.columns}

def save(db, obj):
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return as_dict(obj)

def ensure_owner(db, area_id):
    area = get(db, LifeArea, area_id)
    if area.user_id != user(db).id: raise HTTPException(404, "Record not found")
    return area

def validate_track(db, area_id, track_id):
    if track_id:
        t = get(db, Track, track_id)
        if t.life_area_id != area_id: raise HTTPException(422, "Track does not belong to life area")
        return t

def validate_goal(db, data: GoalIn, own_id=None):
    ensure_owner(db, data.life_area_id)
    track = validate_track(db, data.life_area_id, data.track_id)
    if data.module_id:
        m = get(db, Module, data.module_id)
        if not track or m.track_id != track.id: raise HTTPException(422, "Module does not belong to track")
    if data.parent_goal_id:
        if data.parent_goal_id == own_id: raise HTTPException(422, "Goal cannot link to itself")
        parent = get(db, Goal, data.parent_goal_id)
        if parent.user_id != user(db).id: raise HTTPException(404, "Record not found")
        order = ["10y", "5y", "2y", "1y", "3mo", "month", "week"]
        if order.index(parent.horizon) >= order.index(data.horizon): raise HTTPException(422, "Parent must be at a longer horizon")
        seen = {own_id}
        while parent.parent_goal_id:
            if parent.parent_goal_id in seen: raise HTTPException(422, "Goal link cycle")
            seen.add(parent.parent_goal_id)
            parent = get(db, Goal, parent.parent_goal_id)
    if data.horizon == "week":
        try: start = date.fromisoformat(data.target_date or "")
        except ValueError: raise HTTPException(422, "Weekly goals need a Monday week start date")
        if start.weekday() != 0: raise HTTPException(422, "Weekly goals need a Monday week start date")

@app.get("/api/health")
def health(): return {"ok": True}

@app.get("/api/overview")
def overview(db: Session = Depends(session)):
    u = user(db)
    return {
        "areas": [as_dict(x) for x in db.scalars(select(LifeArea).where(LifeArea.user_id == u.id).order_by(LifeArea.sort_order, LifeArea.name))],
        "tracks": [as_dict(x) for x in db.scalars(select(Track).join(LifeArea).where(LifeArea.user_id == u.id).order_by(Track.sort_order, Track.name))],
        "modules": [as_dict(x) for x in db.scalars(select(Module).join(Track).join(LifeArea).where(LifeArea.user_id == u.id).order_by(Module.sort_order, Module.name))],
        "goals": [as_dict(x) for x in db.scalars(select(Goal).where(Goal.user_id == u.id).order_by(Goal.sort_order, Goal.title))],
    }

@app.post("/api/areas", status_code=201)
def add_area(data: AreaIn, db: Session = Depends(session)):
    return save(db, LifeArea(user_id=user(db).id, **data.model_dump()))

@app.put("/api/areas/{id}")
def edit_area(id: str, data: AreaIn, db: Session = Depends(session)):
    obj = ensure_owner(db, id)
    for k,v in data.model_dump().items(): setattr(obj,k,v)
    return save(db,obj)

@app.post("/api/tracks", status_code=201)
def add_track(data: TrackIn, db: Session = Depends(session)):
    ensure_owner(db, data.life_area_id)
    return save(db, Track(**data.model_dump()))

@app.put("/api/tracks/{id}")
def edit_track(id: str, data: TrackIn, db: Session = Depends(session)):
    obj = get(db, Track, id)
    ensure_owner(db, obj.life_area_id)
    ensure_owner(db, data.life_area_id)
    if obj.life_area_id != data.life_area_id and (obj.modules or db.scalar(select(Goal.id).where(Goal.track_id == id).limit(1))): raise HTTPException(409, "Move child records first")
    for k,v in data.model_dump().items(): setattr(obj,k,v)
    return save(db,obj)

@app.post("/api/modules", status_code=201)
def add_module(data: ModuleIn, db: Session = Depends(session)):
    ensure_owner(db, get(db,Track,data.track_id).life_area_id)
    return save(db, Module(**data.model_dump()))

@app.put("/api/modules/{id}")
def edit_module(id: str, data: ModuleIn, db: Session = Depends(session)):
    obj = get(db,Module,id)
    ensure_owner(db,get(db,Track,obj.track_id).life_area_id)
    ensure_owner(db,get(db,Track,data.track_id).life_area_id)
    if obj.track_id != data.track_id and db.scalar(select(Goal.id).where(Goal.module_id == id).limit(1)): raise HTTPException(409,"Move linked goals first")
    for k,v in data.model_dump().items(): setattr(obj,k,v)
    return save(db,obj)

@app.post("/api/goals", status_code=201)
def add_goal(data: GoalIn, db: Session = Depends(session)):
    validate_goal(db,data)
    if data.horizon == "week" and not data.target_date: raise HTTPException(422,"Weekly goals need a week start date")
    return save(db,Goal(user_id=user(db).id,**data.model_dump()))

@app.put("/api/goals/{id}")
def edit_goal(id: str, data: GoalIn, db: Session = Depends(session)):
    obj = get(db,Goal,id)
    if obj.user_id != user(db).id: raise HTTPException(404,"Record not found")
    validate_goal(db,data,id)
    if data.horizon == "week" and not data.target_date: raise HTTPException(422,"Weekly goals need a week start date")
    for k,v in data.model_dump().items(): setattr(obj,k,v)
    return save(db,obj)

TABLES = {"areas": LifeArea,"tracks": Track,"modules": Module,"goals": Goal}

from plan_api import router as plan_router
app.include_router(plan_router)
from stage3_api import router as stage3_router
app.include_router(stage3_router)

@app.post("/api/{kind}/{id}/archive")
def archive(kind: str,id: str,restore: bool = False,db: Session = Depends(session)):
    if kind not in TABLES: raise HTTPException(404,"Unknown record type")
    obj=get(db,TABLES[kind],id)
    if kind == "areas": ensure_owner(db,id)
    elif kind == "tracks": ensure_owner(db,obj.life_area_id)
    elif kind == "modules": ensure_owner(db,get(db,Track,obj.track_id).life_area_id)
    elif obj.user_id != user(db).id: raise HTTPException(404,"Record not found")
    obj.archived_at = None if restore else datetime.now(timezone.utc)
    return save(db,obj)

@app.delete("/api/{kind}/{id}")
def delete(kind: str,id: str,confirm: bool = Query(False),db: Session = Depends(session)):
    if not confirm: raise HTTPException(400,"Deletion requires confirmation")
    if kind not in TABLES: raise HTTPException(404,"Unknown record type")
    obj=get(db,TABLES[kind],id)
    if kind == "areas":
        ensure_owner(db,id)
        refs = db.scalar(select(Track.id).where(Track.life_area_id==id).limit(1)) or db.scalar(select(Goal.id).where(Goal.life_area_id==id).limit(1))
    elif kind == "tracks":
        ensure_owner(db,obj.life_area_id)
        refs = db.scalar(select(Module.id).where(Module.track_id==id).limit(1)) or db.scalar(select(Goal.id).where(Goal.track_id==id).limit(1))
    elif kind == "modules":
        ensure_owner(db,get(db,Track,obj.track_id).life_area_id)
        refs = db.scalar(select(Goal.id).where(Goal.module_id==id).limit(1)) or db.scalar(select(Task.id).where(Task.module_id==id).limit(1))
    else:
        if obj.user_id != user(db).id: raise HTTPException(404,"Record not found")
        refs = db.scalar(select(Goal.id).where(Goal.parent_goal_id==id).limit(1)) or db.scalar(select(Task.id).where(Task.goal_id==id).limit(1))
    if refs: raise HTTPException(409,"This item is referenced. Archive it to preserve linked records.")
    db.delete(obj)
    db.commit()
    return {"deleted":True}

