import sqlalchemy as sa

from app.db.session import Base

DEVICE_TYPES = ("fan", "light", "camera")


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        # slug is unique per owner, not globally
        sa.UniqueConstraint("owner_id", "slug", name="uq_device_owner_slug"),
    )

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    name = sa.Column(sa.String(255), nullable=False)
    slug = sa.Column(sa.String(128), nullable=False, index=True)
    # fan | light | camera
    device_type = sa.Column(sa.String(32), nullable=False)
    description = sa.Column(sa.Text, nullable=True)
    key_hash = sa.Column(sa.Text, nullable=False)
    owner_id = sa.Column(
        sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_active = sa.Column(sa.Boolean, nullable=False, default=True, server_default=sa.true())
    last_seen_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)