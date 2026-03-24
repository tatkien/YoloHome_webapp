import sqlalchemy as sa

from app.db.session import Base


class Dashboard(Base):
    __tablename__ = "dashboards"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    owner_id = sa.Column(sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = sa.Column(sa.String(255), nullable=False)
    description = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


class DashboardWidget(Base):
    __tablename__ = "dashboard_widgets"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    dashboard_id = sa.Column(sa.Integer, sa.ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False, index=True)
    title = sa.Column(sa.String(255), nullable=False)
    widget_type = sa.Column(sa.String(64), nullable=False)
    position_x = sa.Column(sa.Integer, nullable=False, default=0, server_default="0")
    position_y = sa.Column(sa.Integer, nullable=False, default=0, server_default="0")
    width = sa.Column(sa.Integer, nullable=False, default=4, server_default="4")
    height = sa.Column(sa.Integer, nullable=False, default=3, server_default="3")
    config = sa.Column(sa.JSON, nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)