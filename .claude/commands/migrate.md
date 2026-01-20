# Database Migrations

Create and apply Alembic database migrations.

## Creating a New Migration

1. Describe the schema change needed
2. Generate migration:
   ```bash
   alembic revision --autogenerate -m "description_of_change"
   ```
3. Review the generated migration in `migrations/versions/`
4. Check for:
   - Correct upgrade() operations
   - Matching downgrade() operations
   - No destructive operations without explicit approval

## Applying Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Apply one migration at a time
alembic upgrade +1

# Show current revision
alembic current

# Show migration history
alembic history
```

## Rolling Back

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision>
```

## Migration Best Practices

### Additive Changes (Safe)
- Adding new tables
- Adding nullable columns
- Adding indexes

### Breaking Changes (Ask First)
- Dropping tables or columns
- Renaming columns
- Changing column types
- Adding NOT NULL to existing columns

### Data Migrations

For migrations that need to transform data:

```python
def upgrade():
    # Add new column
    op.add_column('hosts', sa.Column('normalized_mac', sa.String(17)))

    # Migrate data
    connection = op.get_bind()
    connection.execute(
        text("UPDATE hosts SET normalized_mac = LOWER(mac_address)")
    )
```

## Testing Migrations

Always test migrations can apply and rollback cleanly:

```bash
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```
