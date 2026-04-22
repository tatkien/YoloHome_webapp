import sqlalchemy as sa

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    username = sa.Column(sa.String(64), unique=True, nullable=False, index=True)
    full_name = sa.Column(sa.String(255), nullable=True)
    hashed_password = sa.Column(sa.Text, nullable=False)
    role = sa.Column(
        sa.String(32), nullable=False, default="user", server_default="user"
    )
    is_active = sa.Column(
        sa.Boolean, nullable=False, default=True, server_default=sa.true()
    )
    created_at = sa.Column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )