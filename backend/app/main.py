from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.activities import router as activities_router
from app.api.auth import router as auth_router
from app.api.balances import router as balances_router
from app.api.dashboard import router as dashboard_router
from app.api.expenses import router as expenses_router
from app.api.groups import router as groups_router
from app.api.health import router as health_router
from app.api.settlements import router as settlements_router
from app.api.websockets import router as websockets_router


app = FastAPI(title="SplitMate API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(activities_router)
app.include_router(balances_router)
app.include_router(groups_router)
app.include_router(expenses_router)
app.include_router(settlements_router)
app.include_router(websockets_router)
