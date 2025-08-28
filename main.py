from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app import models, crud
from app.database import engine, SessionLocal
from app.ui import create_ui
from nicegui import ui

def init_db():
    # Create all tables
    models.Base.metadata.create_all(bind=engine)

    # Get a DB session
    db = SessionLocal()
    try:
        # Seed initial settings
        crud.update_setting(db, key='failover_threshold_count', value='2')
        crud.update_setting(db, key='failover_threshold_period_minutes', value='5')
        print("Database initialized and default settings seeded.")
    finally:
        db.close()

app = FastAPI(
    title="AI Provider API Server",
    description="An intelligent API server to manage and route requests to various AI providers.",
    version="0.1.0",
)

from app.api import router as api_router
app.include_router(api_router)

app.mount("/images", StaticFiles(directory="images"), name="images")
app.mount("/css", StaticFiles(directory="css"), name="css")
app.mount("/js", StaticFiles(directory="js"), name="js")

# The @ui.page decorator is now used in ui.py, so we don't call create_ui() directly.
@app.on_event("startup")
async def on_startup():
    init_db()

create_ui()
ui.run_with(
    app,
    title="NiceAPI",
    favicon="images/favicon.png",
    storage_secret="a_super_secret_key_that_should_be_changed"
)