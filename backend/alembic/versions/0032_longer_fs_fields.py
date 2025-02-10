"""empty message

Revision ID: 0032_longer_fs_fields
Revises: 0031_datetime_to_timestamp
Create Date: 2025-01-24 02:18:30.069263

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0032_longer_fs_fields"
down_revision = "0031_datetime_to_timestamp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.alter_column(
            "slug",
            existing_type=sa.String(length=50),
            type_=sa.String(length=100),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "fs_slug",
            existing_type=sa.String(length=50),
            type_=sa.String(length=100),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "category",
            existing_type=sa.String(length=50),
            type_=sa.String(length=100),
            existing_nullable=True,
        )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.alter_column(
            "category",
            existing_type=sa.String(length=100),
            type_=sa.String(length=50),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "fs_slug",
            existing_type=sa.String(length=100),
            type_=sa.String(length=50),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "slug",
            existing_type=sa.String(length=100),
            type_=sa.String(length=50),
            existing_nullable=False,
        )

    # ### end Alembic commands ###
