# Backend deployment

Database migrations are a required deployment step. Application startup does not create or alter production tables.

```powershell
git pull
# activate the project Python environment
cd backend
alembic upgrade head
python scripts/check_database_schema.py
python -m fastapi run app/main.py
```

Do not start the updated application until both migration commands succeed. The schema check compares the database's `alembic_version` with the application's Alembic head and verifies that the progressive resource-generation tables exist.
