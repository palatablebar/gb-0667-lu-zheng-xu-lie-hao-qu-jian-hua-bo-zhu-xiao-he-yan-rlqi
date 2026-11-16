from fastapi.testclient import TestClient
from app.main import app

def test_full_sample_through_api():
    client=TestClient(app);result=client.post('/api/batches',json={'sample':'dirty'});assert result.status_code==200
    data=result.json();assert data['reconcile']['balanced'];rid=data['manifest']['run_id']
    assert client.get('/api/export/'+rid).status_code==200
    for page in ('intake','contract','model','calculate','quarantine','reconcile','batches'):assert client.get('/'+page+'?run='+rid).status_code==200

def test_invalid_input_returns_422():
    client=TestClient(app);response=client.post('/api/intake',json={'csv':'wrong,header\n1,2'});assert response.status_code==422;assert response.json()['code']=='HEADER'

def test_clean_dirty_same_path():
    client=TestClient(app);clean=client.post('/api/batches',json={'sample':'clean'}).json();dirty=client.post('/api/batches',json={'sample':'dirty'}).json()
    assert clean['quarantine']['count']==0;assert dirty['quarantine']['count']==5;assert clean['reconcile']['issued']==dirty['reconcile']['issued']
