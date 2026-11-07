"""word sets

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema. The values are filled in by the bank sync on startup."""
    with op.batch_alter_table('words', schema=None) as batch_op:
        batch_op.add_column(sa.Column('set_no', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('set_rank', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('words', schema=None) as batch_op:
        batch_op.drop_column('set_rank')
        batch_op.drop_column('set_no')
