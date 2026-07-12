from fastapi import APIRouter, HTTPException

from lingjing_ai.services.analytics_snapshot import AnalyticsSnapshotError, AnalyticsSnapshotStore


BUILD_COMMAND = (
    'python scripts\\build_tourism_analytics_snapshot.py --input '
    '"景点景区旅游数据行为分析数据.xlsx" --output '
    '"data\\tourism_analytics_snapshot.json"'
)


def build_analytics_router(store: AnalyticsSnapshotStore) -> APIRouter:
    router = APIRouter()

    @router.get("/api/admin/analytics/dashboard")
    def get_admin_analytics_dashboard() -> dict:
        try:
            return store.load()
        except AnalyticsSnapshotError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"{exc} 初始化命令：{BUILD_COMMAND}",
            ) from exc

    return router
