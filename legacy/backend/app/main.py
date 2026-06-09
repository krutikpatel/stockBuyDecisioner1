from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.stock import router as stock_router

app = FastAPI(title="Stock Decision Tool", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stock_router)


@app.get("/health")
def health():
    return {"status": "ok"}
