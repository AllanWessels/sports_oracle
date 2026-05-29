"""Add eval_traces — per-turn evaluation + routing observability.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-29 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eval_traces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        # captured immediately
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("intent", sa.Text(), nullable=False),
        sa.Column("route", sa.Text(), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("num_tool_results", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("num_rag_hits", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("contexts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("prediction", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # filled by the async judge worker (NULL until judged)
        sa.Column("faithfulness", sa.Float(), nullable=True),
        sa.Column("answer_relevancy", sa.Float(), nullable=True),
        sa.Column("context_precision", sa.Float(), nullable=True),
        sa.Column("context_recall", sa.Float(), nullable=True),
        sa.Column("citation_valid", sa.Boolean(), nullable=True),
        sa.Column("judged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("judge_model", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eval_traces_created_at", "eval_traces", ["created_at"])
    op.create_index("ix_eval_traces_intent", "eval_traces", ["intent"])
    op.create_index("ix_eval_traces_judged_at", "eval_traces", ["judged_at"])


def downgrade() -> None:
    op.drop_index("ix_eval_traces_judged_at", table_name="eval_traces")
    op.drop_index("ix_eval_traces_intent", table_name="eval_traces")
    op.drop_index("ix_eval_traces_created_at", table_name="eval_traces")
    op.drop_table("eval_traces")
