import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.dashboard import Dashboard, DashboardWidget
from app.models.user import User
from app.schemas.dashboard import (
    DashboardCreate,
    DashboardDetail,
    DashboardRead,
    DashboardWidgetCreate,
    DashboardWidgetRead,
)

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


async def _get_dashboard_or_404(
    db: AsyncSession,
    dashboard_id: int,
    owner_id: int,
) -> Dashboard:
    result = await db.execute(
        sa.select(Dashboard).where(Dashboard.id == dashboard_id, Dashboard.owner_id == owner_id)
    )
    dashboard = result.scalar_one_or_none()
    if dashboard is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dashboard not found",
        )
    return dashboard


@router.get("/", response_model=list[DashboardRead])
async def list_dashboards(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        sa.select(Dashboard)
        .where(Dashboard.owner_id == current_user.id)
        .order_by(Dashboard.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=DashboardRead, status_code=status.HTTP_201_CREATED)
async def create_dashboard(
    payload: DashboardCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dashboard = Dashboard(
        owner_id=current_user.id,
        name=payload.name,
        description=payload.description,
    )
    db.add(dashboard)
    await db.commit()
    await db.refresh(dashboard)
    return dashboard


@router.get("/{dashboard_id}", response_model=DashboardDetail)
async def read_dashboard(
    dashboard_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dashboard = await _get_dashboard_or_404(db, dashboard_id, current_user.id)
    widgets_result = await db.execute(
        sa.select(DashboardWidget)
        .where(DashboardWidget.dashboard_id == dashboard_id)
        .order_by(DashboardWidget.created_at.asc())
    )
    widgets = widgets_result.scalars().all()
    return DashboardDetail(
        **DashboardRead.model_validate(dashboard).model_dump(),
        widgets=[DashboardWidgetRead.model_validate(widget) for widget in widgets],
    )


@router.post(
    "/{dashboard_id}/widgets",
    response_model=DashboardWidgetRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_dashboard_widget(
    dashboard_id: int,
    payload: DashboardWidgetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_dashboard_or_404(db, dashboard_id, current_user.id)
    if payload.feed_id is not None:
        result = await db.execute(sa.select(Feed).where(Feed.id == payload.feed_id))
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feed not found",
            )

    widget = DashboardWidget(
        dashboard_id=dashboard_id,
        title=payload.title,
        widget_type=payload.widget_type,
        position_x=payload.position_x,
        position_y=payload.position_y,
        width=payload.width,
        height=payload.height,
        config=payload.config,
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget