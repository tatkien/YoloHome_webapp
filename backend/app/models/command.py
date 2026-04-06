import sqlalchemy as sa

from app.db.session import Base


class Command(Base):
    __tablename__ = "commands"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    device_id = sa.Column(sa.Integer, sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    feed_id = sa.Column(sa.Integer, sa.ForeignKey("feeds.id", ondelete="SET NULL"), nullable=True)
    created_by_id = sa.Column(sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    payload = sa.Column(sa.JSON, nullable=False)
    result = sa.Column(sa.JSON, nullable=True)
    status = sa.Column(sa.String(32), nullable=False, default="pending", server_default="pending", index=True)
    delivered_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    acknowledged_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)