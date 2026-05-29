import os

from fastapi import FastAPI

from app.middleware import RateLimitMiddleware
from rate_limiter.factory import create_rate_limiter

limiter = create_rate_limiter()

app = FastAPI(title="Portcast Rate Limiter API")
app.add_middleware(RateLimitMiddleware, limiter=limiter)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "instance": os.getenv("INSTANCE_NAME", "local"),
    }


@app.get("/v1/demo")
def demo() -> dict[str, str]:
    return {"message": "demo endpoint"}


@app.get("/v1/search")
def search() -> dict[str, str]:
    return {"message": "search endpoint"}


@app.post("/v1/reports")
def reports() -> dict[str, str]:
    return {"message": "reports endpoint"}


@app.get("/v1/shipments")
def shipments() -> dict[str, str]:
    return {"message": "shipments endpoint"}
