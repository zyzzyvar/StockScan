"""Add screenshot_records table for StockView integration

Revision ID: 9dccd3ccca38
Revises: feeb34b76742
Create Date: 2026-04-01 15:41:46.018444

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9dccd3ccca38'
down_revision: Union[str, Sequence[str], None] = 'feeb34b76742'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'screenshot_records',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('result_detail_id', sa.Integer(), nullable=False),
        sa.Column('task_name', sa.String(length=255), nullable=False),
        sa.Column('ts_code', sa.String(length=20), nullable=False),
        sa.Column('screenshot_date', sa.Date(), nullable=False),
        sa.Column('screenshot_filename', sa.String(length=512), nullable=False),
        sa.Column('pdf_path', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['result_detail_id'], ['screening_result_detail.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('result_detail_id', 'task_name', 'screenshot_date', name='unique_record'),
    )
    op.create_index('idx_result_detail', 'screenshot_records', ['result_detail_id'])
    op.create_index('idx_task_date', 'screenshot_records', ['task_name', 'screenshot_date'])
    op.create_index('idx_ts_code_date', 'screenshot_records', ['ts_code', 'screenshot_date'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_ts_code_date', table_name='screenshot_records')
    op.drop_index('idx_task_date', table_name='screenshot_records')
    op.drop_index('idx_result_detail', table_name='screenshot_records')
    op.drop_table('screenshot_records')
