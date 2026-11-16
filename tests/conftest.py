import pytest
from app.config import ROOT,COLUMNS
from app.pipeline import run
from app.modules.m1_intake.rules import parse
from app.modules.m2_contract.service import execute

@pytest.fixture
def sample():return run({'sample':'dirty'})

@pytest.fixture
def normalized():return execute(parse((ROOT/'sample_data/clean.csv').read_bytes())['rows'])['rows']

@pytest.fixture(autouse=True)
def database(tmp_path,monkeypatch):monkeypatch.setenv('DB_PATH',str(tmp_path/'test.sqlite'))
