"""Создание таблиц: users, products, cart_items.

Revision ID: 0001
Revises:
Create Date: 2026-01-01
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE users (
            id BIGSERIAL PRIMARY KEY,
            username VARCHAR(100) NOT NULL UNIQUE,
            email VARCHAR(255) NOT NULL UNIQUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE products (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            price NUMERIC(10, 2) NOT NULL CHECK (price > 0),
            stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0)
        );
        """
    )
    op.execute(
        """
        CREATE TABLE cart_items (
            user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            product_id BIGINT NOT NULL REFERENCES products (id) ON DELETE CASCADE,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            PRIMARY KEY (user_id, product_id)
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS cart_items;")
    op.execute("DROP TABLE IF EXISTS products;")
    op.execute("DROP TABLE IF EXISTS users;")
