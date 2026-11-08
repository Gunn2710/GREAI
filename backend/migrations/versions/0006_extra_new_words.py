"""study more: extra new words for today

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('extra_new_words', sa.Integer(), server_default=sa.text('0'), nullable=False))
        batch_op.add_column(sa.Column('extra_new_words_on', sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.drop_column('extra_new_words_on')
        batch_op.drop_column('extra_new_words')
