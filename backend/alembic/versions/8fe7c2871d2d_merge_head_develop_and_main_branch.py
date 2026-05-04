"""Merge head develop and main branch

Revision ID: 8fe7c2871d2d
Revises: 37ef4b08b6fb, e1553abf9d21
Create Date: 2026-05-04 09:29:51.859766

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8fe7c2871d2d'
down_revision: Union[str, Sequence[str], None] = ('37ef4b08b6fb', 'e1553abf9d21')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
