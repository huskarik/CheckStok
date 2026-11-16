from fastapi import APIRouter

from app.api.routes.goods import router as goods_router
from app.api.routes.inventory import router as inventory_router
from app.api.routes.warehouses import router as warehouses_router

router = APIRouter(prefix="/api/v1")
router.include_router(goods_router)
router.include_router(warehouses_router)
router.include_router(inventory_router)
