"""description added to DeletedItem

Revision ID: 9c378d5c9118
Revises: 75cd3ce370ed
Create Date: 2023-12-21 21:11:32.541290

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c378d5c9118'
down_revision = '75cd3ce370ed'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('deleted_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('deleted_items', schema=None) as batch_op:
        batch_op.drop_column('description')

    # ### end Alembic commands ###
