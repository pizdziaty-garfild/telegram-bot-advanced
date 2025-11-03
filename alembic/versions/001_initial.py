"""Initial migration with all core tables

Revision ID: 001_initial
Revises: 
Create Date: 2025-11-01 09:44:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    """Create all core tables"""
    
    # Users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=False, default='user'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('api_id', sa.Integer(), nullable=True),
        sa.Column('api_hash', sa.String(length=255), nullable=True),
        sa.Column('license_key', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id')
    )
    op.create_index(op.f('ix_users_telegram_id'), 'users', ['telegram_id'], unique=False)
    
    # Groups table
    op.create_table('groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('type', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('custom_interval', sa.Integer(), nullable=True),
        sa.Column('excluded_from_global', sa.Boolean(), nullable=False, default=False),
        sa.Column('added_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['added_by'], ['users.telegram_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id')
    )
    op.create_index(op.f('ix_groups_telegram_id'), 'groups', ['telegram_id'], unique=False)
    
    # Sessions table
    op.create_table('sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('chat_id', sa.String(length=100), nullable=False),
        sa.Column('state', sa.String(length=50), nullable=False, default='idle'),
        sa.Column('state_data', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id'),
        sa.UniqueConstraint('user_id', 'chat_id', name='unique_user_chat_session')
    )
    
    # Jobs table
    op.create_table('jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.String(length=100), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('message_content', sa.Text(), nullable=True),
        sa.Column('message_type', sa.String(length=50), nullable=False, default='text'),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('interval_minutes', sa.Integer(), nullable=True),
        sa.Column('is_recurring', sa.Boolean(), nullable=False, default=True),
        sa.Column('status', sa.String(length=20), nullable=False, default='pending'),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.telegram_id'], ),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id')
    )
    
    # Audit logs table
    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=True),
        sa.Column('resource_id', sa.String(length=100), nullable=True),
        sa.Column('old_values', sa.JSON(), nullable=True),
        sa.Column('new_values', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Config table
    op.create_table('config',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.JSON(), nullable=True),
        sa.Column('encrypted', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('key')
    )

def downgrade():
    """Drop all core tables"""
    op.drop_table('config')
    op.drop_table('audit_logs')
    op.drop_table('jobs')
    op.drop_table('sessions')
    op.drop_index(op.f('ix_groups_telegram_id'), table_name='groups')
    op.drop_table('groups')
    op.drop_index(op.f('ix_users_telegram_id'), table_name='users')
    op.drop_table('users')
