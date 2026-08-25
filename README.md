# PO_project_prototype
# PO_project_prototype

**commmad to run the python env** : ./.venv/bin/python -m uvicorn app.main:app --reload





cd ~/Downloads/launch_po_backend_m0/backend

# Start PostgreSQL container
docker start postgres-db

# Check PostgreSQL is running
docker ps

# Test database password
docker exec -it postgres-db psql -U postgres -W
# Password: 123
# Exit PostgreSQL:
# \q

# Check environment variable
cat .env | grep DATABASE_URL

# Expected:
# DATABASE_URL=postgresql+psycopg2://postgres:123@127.0.0.1:5432/launch_po_dev

# Run migrations
./.venv/bin/alembic upgrade head

# Check tables
docker exec -it postgres-db psql -U postgres -d launch_po_dev -c "\dt"

# Start FastAPI
./.venv/bin/python -m uvicorn app.main:app --reload