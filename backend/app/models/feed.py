import sqlalchemy as sa

from app.db.session import Base


class Feed(Base):
    __tablename__ = "feeds"
    __table_args__ = (sa.UniqueConstraint("device_id", "key", name="uq_feeds_device_key"),)

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    device_id = sa.Column(sa.Integer, sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    name = sa.Column(sa.String(255), nullable=False)
    key = sa.Column(sa.String(128), nullable=False, index=True)
    description = sa.Column(sa.Text, nullable=True)
    data_type = sa.Column(sa.String(64), nullable=False, default="text", server_default="text")
    last_value = sa.Column(sa.Text, nullable=True)
    last_value_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)