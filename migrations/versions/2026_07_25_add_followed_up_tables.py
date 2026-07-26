"""add followed_up tables and hotspots new columns

Revision ID: 2026_07_25_add_followed_up_tables
Revises: 4f9e949906b1
Create Date: 2026-07-25 12:00:00.000000

Project database: SQLite + aiosqlite.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2026_07_25_add_followed_up_tables"
down_revision: Union[str, None] = "4f9e949906b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the three new tables and extend hotspots."""
    # 1. followed_up table
    op.create_table(
        "followed_up",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("uid", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("profile_url", sa.String(length=256), nullable=False),
        sa.Column(
            "collector_strategy",
            sa.String(length=16),
            nullable=False,
            server_default="uapi",
        ),
        sa.Column("last_cursor_id", sa.String(length=64), nullable=True),
        sa.Column(
            "fetch_interval_minutes",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="active"
        ),
        sa.Column(
            "health", sa.String(length=16), nullable=False, server_default="healthy"
        ),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        # SQLite treats NULL as distinct in unique constraints, so including
        # ``deleted_at`` allows reactivating a soft-deleted (platform, uid) by
        # inserting a new row with ``deleted_at = NULL``.
        sa.UniqueConstraint(
            "platform", "uid", "deleted_at", name="uq_followed_up_platform_uid"
        ),
    )
    op.create_index("idx_followed_up_platform", "followed_up", ["platform"])
    op.create_index("idx_followed_up_is_active", "followed_up", ["is_active"])
    op.create_index("idx_followed_up_status", "followed_up", ["status"])

    # 2. followed_up_collections table
    op.create_table(
        "followed_up_collections",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("followed_up_id", sa.String(length=32), nullable=False),
        sa.Column("platform_collection_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("video_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["followed_up_id"],
            ["followed_up.id"],
            name="fk_collections_followed_up",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "followed_up_id",
            "platform_collection_id",
            name="uq_collection_per_up",
        ),
    )
    op.create_index(
        "idx_collections_followed_up", "followed_up_collections", ["followed_up_id"]
    )

    # 3. learning_events table
    op.create_table(
        "learning_events",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("hotspot_id", sa.String(length=32), nullable=False),
        sa.Column("followed_up_id", sa.String(length=32), nullable=False),
        sa.Column(
            "platform", sa.String(length=16), nullable=False, server_default="bilibili"
        ),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("summary_note_path", sa.String(length=512), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column(
            "estimated_minutes", sa.Integer(), nullable=False, server_default="15"
        ),
        sa.Column(
            "obsidian_task_created",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("apple_reminder_id", sa.String(length=64), nullable=True),
        sa.Column(
            "apple_reminders_list",
            sa.String(length=64),
            nullable=False,
            server_default="工作学习",
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "learning_status",
            sa.String(length=16),
            nullable=False,
            server_default="unread",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hotspot_id"], ["hotspots.id"], name="fk_learning_events_hotspot"
        ),
        sa.ForeignKeyConstraint(
            ["followed_up_id"], ["followed_up.id"], name="fk_learning_events_followed_up"
        ),
    )
    op.create_index("idx_learning_events_hotspot", "learning_events", ["hotspot_id"])
    op.create_index(
        "idx_learning_events_followed_up", "learning_events", ["followed_up_id"]
    )
    op.create_index(
        "idx_learning_events_scheduled_at", "learning_events", ["scheduled_at"]
    )

    # 4. hotspots table new columns (all nullable)
    with op.batch_alter_table("hotspots") as batch_op:
        batch_op.add_column(
            sa.Column("followed_up_id", sa.String(length=32), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "followed_up_collection_id", sa.String(length=32), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column("content_id", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("platform_user_id", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(sa.Column("transcript", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("key_points", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("is_tech_related", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("tech_confidence", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("tech_reason", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "decision_status",
                sa.String(length=16),
                nullable=False,
                server_default="pending",
            )
        )
        batch_op.add_column(
            sa.Column("learning_status", sa.String(length=16), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "is_backfill",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column("obsidian_source_path", sa.String(length=512), nullable=True)
        )
        batch_op.add_column(
            sa.Column("obsidian_summary_path", sa.String(length=512), nullable=True)
        )
        batch_op.add_column(
            sa.Column("learning_event_id", sa.String(length=32), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "notified", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch_op.create_foreign_key(
            "fk_hotspots_followed_up", "followed_up", ["followed_up_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_hotspots_collection",
            "followed_up_collections",
            ["followed_up_collection_id"],
            ["id"],
        )

    # 5. Partial indexes (SQLite WHERE syntax)
    # NOTE: ``hotspots`` does not currently have a ``deleted_at`` column
    # (the column is only on ``followed_up``). We omit those predicates
    # here; once hotspots gains a deleted_at column, the WHERE clauses can
    # be re-introduced without changing the index shape.
    op.execute(
        """
        CREATE INDEX idx_hotspots_active
        ON hotspots (decision_status, created_at)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_hotspots_pending
        ON hotspots (followed_up_id, created_at)
        WHERE decision_status = 'pending'
        """
    )
    op.execute(
        """
        CREATE INDEX idx_hotspots_worth_notified
        ON hotspots (followed_up_id)
        WHERE decision_status = 'worth_learning'
          AND notified = 0
        """
    )

    # Ordinary indexes
    op.create_index("idx_hotspots_followed_up_id", "hotspots", ["followed_up_id"])
    op.create_index("idx_hotspots_content_id", "hotspots", ["content_id"])


def downgrade() -> None:
    """Reverse all follow + learning schema changes."""
    op.drop_index("idx_hotspots_content_id", table_name="hotspots")
    op.drop_index("idx_hotspots_followed_up_id", table_name="hotspots")
    op.drop_index("idx_hotspots_worth_notified", table_name="hotspots")
    op.drop_index("idx_hotspots_pending", table_name="hotspots")
    op.drop_index("idx_hotspots_active", table_name="hotspots")

    with op.batch_alter_table("hotspots") as batch_op:
        batch_op.drop_constraint("fk_hotspots_collection", type_="foreignkey")
        batch_op.drop_constraint("fk_hotspots_followed_up", type_="foreignkey")
        batch_op.drop_column("notified")
        batch_op.drop_column("learning_event_id")
        batch_op.drop_column("obsidian_summary_path")
        batch_op.drop_column("obsidian_source_path")
        batch_op.drop_column("is_backfill")
        batch_op.drop_column("learning_status")
        batch_op.drop_column("decision_status")
        batch_op.drop_column("tech_reason")
        batch_op.drop_column("tech_confidence")
        batch_op.drop_column("is_tech_related")
        batch_op.drop_column("key_points")
        batch_op.drop_column("transcript")
        batch_op.drop_column("platform_user_id")
        batch_op.drop_column("content_id")
        batch_op.drop_column("followed_up_collection_id")
        batch_op.drop_column("followed_up_id")

    op.drop_index("idx_learning_events_scheduled_at", table_name="learning_events")
    op.drop_index("idx_learning_events_followed_up", table_name="learning_events")
    op.drop_index("idx_learning_events_hotspot", table_name="learning_events")
    op.drop_table("learning_events")

    op.drop_index("idx_collections_followed_up", table_name="followed_up_collections")
    op.drop_table("followed_up_collections")

    op.drop_index("idx_followed_up_status", table_name="followed_up")
    op.drop_index("idx_followed_up_is_active", table_name="followed_up")
    op.drop_index("idx_followed_up_platform", table_name="followed_up")
    op.drop_table("followed_up")
