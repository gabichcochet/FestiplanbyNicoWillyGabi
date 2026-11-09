import os
import tempfile
import pytest

_database_path = os.path.join(tempfile.gettempdir(), f"festiplan-tests-{os.getpid()}.db")
os.environ["FESTIPLAN_DATABASE_URL"] = f"sqlite:///{_database_path}"

@pytest.fixture(scope="session")
def prepare():
 from app import models
 from app.database import Base,engine

 Base.metadata.create_all(bind=engine)
 yield
 Base.metadata.drop_all(bind=engine)
 try:
   os.unlink(_database_path)
 except OSError:
   pass

@pytest.fixture()
def client(prepare):
 from fastapi.testclient import TestClient
 from app.database import Base,SessionLocal
 from app.main import app

 db=SessionLocal()
 for table in reversed(Base.metadata.sorted_tables): 
   db.execute(table.delete())
 db.commit(); db.close()
 with TestClient(app) as c: 
   yield c
