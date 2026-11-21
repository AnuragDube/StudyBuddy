"""add users table and user_id foreign keys for per-user schedules

Revision ID: 0002_add_users
Revises: 0001_initial_schema
Create Date: 2026-11-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_user_settings_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.create_index("ix_user_settings_user_id", ["user_id"], unique=True)

    with op.batch_alter_table("study_plans") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_study_plans_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.create_index("ix_study_plans_user_id", ["user_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("study_plans") as batch_op:
        batch_op.drop_index("ix_study_plans_user_id")
        batch_op.drop_constraint("fk_study_plans_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.drop_index("ix_user_settings_user_id")
        batch_op.drop_constraint("fk_user_settings_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
