import sqlalchemy as sa

from app.db.session import Base


class InvitationKey(Base):
    __tablename__ = "invitation_keys"

    id = sa.Column(sa.Integer, primary_key=True)
    key_hash = sa.Column(sa.Text, nullable=False)
    updated_by_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at = sa.Column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )
