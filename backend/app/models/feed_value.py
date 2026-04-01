import sqlalchemy as sa

from app.db.session import Base


class FeedValue(Base):
    __tablename__ = "feed_values"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    feed_id = sa.Column(sa.Integer, sa.ForeignKey("feeds.id", ondelete="CASCADE"), nullable=False, index=True)
    value = sa.Column(sa.Text, nullable=False)
    source = sa.Column(sa.String(32), nullable=False, default="device", server_default="device")
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)