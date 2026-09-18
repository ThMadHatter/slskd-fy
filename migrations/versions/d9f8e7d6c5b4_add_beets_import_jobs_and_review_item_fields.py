"""add_beets_import_jobs_and_review_item_fields

Revision ID: d9f8e7d6c5b4
Revises: a41f121fd3e1
Create Date: 2026-09-18 12:00:00.000000

"""
from typing import Sequence, Union
import uuid
import hashlib
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9f8e7d6c5b4'
down_revision: Union[str, Sequence[str], None] = 'a41f121fd3e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Create beets_import_jobs if missing
    if "beets_import_jobs" not in tables:
        op.create_table(
            'beets_import_jobs',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('job_id', sa.String(), nullable=False),
            sa.Column('source_path', sa.String(), nullable=False),
            sa.Column('status', sa.String(), nullable=False, server_default='queued'),
            sa.Column('total_items', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('imported_items', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('conflicts_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('error_message', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        op.create_index(op.f('ix_beets_import_jobs_id'), 'beets_import_jobs', ['id'], unique=False)
        op.create_index(op.f('ix_beets_import_jobs_job_id'), 'beets_import_jobs', ['job_id'], unique=True)

    # 2. Add missing columns to beets_review_items if table exists
    if "beets_review_items" in tables:
        columns = [c['name'] for c in inspector.get_columns('beets_review_items')]

        with op.batch_alter_table('beets_review_items', schema=None) as batch_op:
            if 'conflict_id' not in columns:
                batch_op.add_column(sa.Column('conflict_id', sa.String(), nullable=True))
            if 'fingerprint' not in columns:
                batch_op.add_column(sa.Column('fingerprint', sa.String(), nullable=True))
            if 'job_id' not in columns:
                batch_op.add_column(sa.Column('job_id', sa.String(), nullable=True))
            if 'item_type' not in columns:
                batch_op.add_column(sa.Column('item_type', sa.String(), server_default='album', nullable=False))
            if 'differences_json' not in columns:
                batch_op.add_column(sa.Column('differences_json', sa.String(), nullable=True))
            if 'recommendation_text' not in columns:
                batch_op.add_column(sa.Column('recommendation_text', sa.String(), nullable=True))
            if 'error_message' not in columns:
                batch_op.add_column(sa.Column('error_message', sa.String(), nullable=True))
            if 'retry_count' not in columns:
                batch_op.add_column(sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False))
            if 'resolution_audit' not in columns:
                batch_op.add_column(sa.Column('resolution_audit', sa.String(), nullable=True))

        # 3. Backfill data for existing rows
        rows = bind.execute(sa.text("SELECT id, downloaded_path, artist, track, status FROM beets_review_items")).fetchall()
        for row in rows:
            row_id = row[0]
            d_path = row[1] or ""
            artist = row[2] or ""
            track = row[3] or ""
            status = row[4] or "open"

            # Normalize old status "review_required" to "open"
            new_status = "open" if status in ("review_required", None, "") else status

            new_conflict_id = str(uuid.uuid4())
            fp_raw = f"{d_path}:{artist}:{track}".encode('utf-8')
            new_fingerprint = hashlib.sha256(fp_raw).hexdigest()

            bind.execute(
                sa.text(
                    "UPDATE beets_review_items "
                    "SET conflict_id = :cid, fingerprint = :fp, status = :st "
                    "WHERE id = :rid AND (conflict_id IS NULL OR conflict_id = '')"
                ),
                {"cid": new_conflict_id, "fp": new_fingerprint, "st": new_status, "rid": row_id}
            )

        # 4. Create indexes on conflict_id and fingerprint after backfill
        indexes = [i['name'] for i in inspector.get_indexes('beets_review_items')]
        with op.batch_alter_table('beets_review_items', schema=None) as batch_op:
            if 'ix_beets_review_items_conflict_id' not in indexes:
                batch_op.create_index('ix_beets_review_items_conflict_id', ['conflict_id'], unique=True)
            if 'ix_beets_review_items_fingerprint' not in indexes:
                batch_op.create_index('ix_beets_review_items_fingerprint', ['fingerprint'], unique=False)
    else:
        # Fresh database: create beets_review_items table
        op.create_table(
            'beets_review_items',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('conflict_id', sa.String(), nullable=True),
            sa.Column('fingerprint', sa.String(), nullable=True),
            sa.Column('job_id', sa.String(), nullable=True),
            sa.Column('download_id', sa.Integer(), nullable=True),
            sa.Column('item_type', sa.String(), nullable=False, server_default='album'),
            sa.Column('artist', sa.String(), nullable=False),
            sa.Column('track', sa.String(), nullable=False),
            sa.Column('album', sa.String(), nullable=True),
            sa.Column('downloaded_path', sa.String(), nullable=False),
            sa.Column('confidence_score', sa.Integer(), server_default='50'),
            sa.Column('status', sa.String(), nullable=False, server_default='open'),
            sa.Column('candidates_json', sa.String(), nullable=False),
            sa.Column('selected_match_json', sa.String(), nullable=True),
            sa.Column('differences_json', sa.String(), nullable=True),
            sa.Column('recommendation_text', sa.String(), nullable=True),
            sa.Column('error_message', sa.String(), nullable=True),
            sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('resolution_audit', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        op.create_index(op.f('ix_beets_review_items_id'), 'beets_review_items', ['id'], unique=False)
        op.create_index('ix_beets_review_items_conflict_id', 'beets_review_items', ['conflict_id'], unique=True)
        op.create_index('ix_beets_review_items_fingerprint', 'beets_review_items', ['fingerprint'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "beets_review_items" in tables:
        indexes = [i['name'] for i in inspector.get_indexes('beets_review_items')]
        columns = [c['name'] for c in inspector.get_columns('beets_review_items')]

        with op.batch_alter_table('beets_review_items', schema=None) as batch_op:
            if 'ix_beets_review_items_conflict_id' in indexes:
                batch_op.drop_index('ix_beets_review_items_conflict_id')
            if 'ix_beets_review_items_fingerprint' in indexes:
                batch_op.drop_index('ix_beets_review_items_fingerprint')

            for col in ['conflict_id', 'fingerprint', 'job_id', 'item_type', 'differences_json',
                        'recommendation_text', 'error_message', 'retry_count', 'resolution_audit']:
                if col in columns:
                    batch_op.drop_column(col)

    if "beets_import_jobs" in tables:
        op.drop_table('beets_import_jobs')
