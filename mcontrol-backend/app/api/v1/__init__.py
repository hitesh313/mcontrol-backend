from fastapi import APIRouter

from app.api.v1 import auth, customers, suppliers

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(suppliers.router)
api_router.include_router(customers.router)
