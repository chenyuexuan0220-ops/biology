from app.db import SessionLocal
from app.services.seed import seed

with SessionLocal.begin() as db:
    print(seed(db))
