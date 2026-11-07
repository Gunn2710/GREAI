"""word phrases

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('words', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'phrases',
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'),
            nullable=False,
            server_default='[]',
        ))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('words', schema=None) as batch_op:
        batch_op.drop_column('phrases')
