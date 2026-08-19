from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import account, admin, auth, generations, internal
from backend.app.settings import load_settings

settings = load_settings()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(internal.router)
app.include_router(auth.router)
app.include_router(account.router)
app.include_router(admin.router)
app.include_router(generations.router)
