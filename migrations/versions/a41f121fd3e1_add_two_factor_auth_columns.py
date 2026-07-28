"""add_two_factor_auth_columns

Revision ID: a41f121fd3e1
Revises: 6ef5ed252102
Create Date: 2026-07-27 13:25:10.683277

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a41f121fd3e1'
down_revision: Union[str, Sequence[str], None] = '6ef5ed252102'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('two_factor_secret', sa.String(), nullable=True))
    op.add_column('users', sa.Column('two_factor_enabled', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'two_factor_secret')
    op.drop_column('users', 'two_factor_enabled')
