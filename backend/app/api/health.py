"""Health check endpoint.

Deliberately dependency-free (no DB call) for now: this answers "is the
process up and serving requests", which is what orchestrators/load
balancers need for liveness checks. A separate ``/health/ready``
readiness check that verifies DB connectivity can be added once the DB
layer has real tables to query against.
"""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    return {"status": "healthy"}
