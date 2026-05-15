"""add statement validation tables

Revision ID: 20260205_001
Revises: -
Create Date: 2026-02-05

Creates:
  - statement_validations
  - statement_validation_flags
  - statement_validation_transactions
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '20260205_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------
    # statement_validations
    # -----------------------------------------------------------
    op.create_table(
        'statement_validations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('matter_id', sa.Integer(), sa.ForeignKey('matters.id'), nullable=False, index=True),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('file_hash_sha256', sa.String(64), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(100)),

        sa.Column('bank_hint', sa.String(200)),
        sa.Column('period_start', sa.String(20)),
        sa.Column('period_end', sa.String(20)),

        sa.Column('authenticity_score', sa.Float(), nullable=False, server_default='0'),
        sa.Column('status', sa.Enum('Trusted', 'Review', 'HighRisk', name='validationstatus'),
                  nullable=False, server_default='Review'),
        sa.Column('identified_bank_template', sa.String(200)),

        sa.Column('file_integrity_result', sa.JSON()),
        sa.Column('template_match_result', sa.JSON()),
        sa.Column('extraction_result', sa.JSON()),
        sa.Column('math_check_result', sa.JSON()),
        sa.Column('anomaly_check_result', sa.JSON()),

        sa.Column('admin_override', sa.Boolean(), server_default='0'),
        sa.Column('admin_override_by', sa.String(200)),
        sa.Column('admin_override_rationale', sa.Text()),
        sa.Column('admin_override_at', sa.DateTime(timezone=True)),

        sa.Column('blocked', sa.Boolean(), server_default='0'),

        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # -----------------------------------------------------------
    # statement_validation_flags
    # -----------------------------------------------------------
    op.create_table(
        'statement_validation_flags',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('validation_id', sa.Integer(),
                  sa.ForeignKey('statement_validations.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('pipeline_stage', sa.String(50), nullable=False),
        sa.Column('code', sa.String(100), nullable=False),
        sa.Column('severity', sa.Enum('info', 'low', 'medium', 'high', 'critical', name='flagseverity'),
                  nullable=False, server_default='medium'),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('details', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # -----------------------------------------------------------
    # statement_validation_transactions
    # -----------------------------------------------------------
    op.create_table(
        'statement_validation_transactions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('validation_id', sa.Integer(),
                  sa.ForeignKey('statement_validations.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('date', sa.String(20)),
        sa.Column('description', sa.Text()),
        sa.Column('amount', sa.Float()),
        sa.Column('direction', sa.String(10)),
        sa.Column('balance', sa.Float()),
        sa.Column('transaction_type', sa.String(50)),
        sa.Column('raw_row', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('statement_validation_transactions')
    op.drop_table('statement_validation_flags')
    op.drop_table('statement_validations')

    # Drop enums (only needed for PostgreSQL)
    try:
        op.execute("DROP TYPE IF EXISTS validationstatus")
        op.execute("DROP TYPE IF EXISTS flagseverity")
    except Exception:
        pass
