import pytest
import requests
import uuid
import time
import concurrent.futures

BASE_URL = "http://localhost:8000"

def get_stats():
    return requests.get(f"{BASE_URL}/stats").json()

def generate_payload(topic="unit_test", event_id=None, missing_field=None):
    payload = {
        "topic": topic,
        "event_id": event_id or str(uuid.uuid4()),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "pytest",
        "payload": {"test": "data"}
    }
    if missing_field:
        del payload[missing_field]
    return payload


def test_01_stats_endpoint_accessible():
    # Memastikan endpoint /stats bisa diakses dan mengembalikan JSON yang benar
    response = requests.get(f"{BASE_URL}/stats")
    assert response.status_code == 200
    data = response.json()
    assert "received" in data
    assert "unique_processed" in data

def test_02_events_endpoint_accessible():
    # Memastikan endpoint /events bisa diakses
    response = requests.get(f"{BASE_URL}/events")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_03_validation_missing_topic():
    # Event tanpa topic harus ditolak (422 Unprocessable Entity).
    data = generate_payload(missing_field="topic")
    response = requests.post(f"{BASE_URL}/publish", json=data)
    assert response.status_code == 422

def test_04_validation_missing_event_id():
    # Event tanpa event_id harus ditolak.
    data = generate_payload(missing_field="event_id")
    response = requests.post(f"{BASE_URL}/publish", json=data)
    assert response.status_code == 422

def test_05_validation_missing_timestamp():
    # Event tanpa timestamp harus ditolak.
    data = generate_payload(missing_field="timestamp")
    response = requests.post(f"{BASE_URL}/publish", json=data)
    assert response.status_code == 422

def test_06_validation_invalid_timestamp_format():
    # Format timestamp yang salah harus ditolak.
    data = generate_payload()
    data["timestamp"] = "bukan-tanggal-valid"
    response = requests.post(f"{BASE_URL}/publish", json=data)
    assert response.status_code == 422


def test_07_publish_unique_event():
    # Event baru harus sukses diterima.
    data = generate_payload(topic="test_dedup")
    response = requests.post(f"{BASE_URL}/publish", json=data)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_08_publish_duplicate_event_ignored():
    # Mengirim event yang SAMA PERSIS harus diabaikan (status: ignored).
    # Kirim pertama
    event_id = str(uuid.uuid4())
    data = generate_payload(topic="test_dedup", event_id=event_id)
    requests.post(f"{BASE_URL}/publish", json=data)
    
    # Kirim ulang (Duplikat)
    response = requests.post(f"{BASE_URL}/publish", json=data)
    
    # Assert
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"

def test_09_composite_primary_key_logic():
    # ID sama tapi topik beda, harus diterima (Sesuai logic Composite Key).
    shared_id = str(uuid.uuid4())
    
    # Kirim Topik A
    data_a = generate_payload(topic="Topik_A", event_id=shared_id)
    res_a = requests.post(f"{BASE_URL}/publish", json=data_a)
    
    # Kirim Topik B (dengan ID yang sama)
    data_b = generate_payload(topic="Topik_B", event_id=shared_id)
    res_b = requests.post(f"{BASE_URL}/publish", json=data_b)
    
    assert res_a.json()["status"] == "success"
    assert res_b.json()["status"] == "success"

def test_10_stats_counter_integrity():
    # Memastikan counter 'unique_processed' bertambah dengan benar.
    initial_stats = get_stats()
    
    # Kirim 1 data unik
    requests.post(f"{BASE_URL}/publish", json=generate_payload())
    
    final_stats = get_stats()
    assert final_stats["unique_processed"] == initial_stats["unique_processed"] + 1

def test_11_concurrency_race_condition():
    
    """ Simulasi Race Condition: 
    10 thread menembak ID yang sama secara bersamaan.
    Hanya 1 yang boleh 'success', 9 lainnya harus 'ignored' """
    
    race_id = str(uuid.uuid4())
    data = generate_payload(topic="race_test", event_id=race_id)
    
    results = []
    def send_request():
        res = requests.post(f"{BASE_URL}/publish", json=data)
        return res.json()["status"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(send_request) for _ in range(10)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())
    
    # Validasi: Hanya ada 1 success, sisanya ignored
    assert results.count("success") == 1
    assert results.count("ignored") == 9

def test_12_audit_stats_increment():
    # Memastikan tabel audit_stats mencatat duplikat dari tes konkurensi tadi.
    stats = get_stats()
    assert stats["duplicate_dropped"] > 0

def test_13_stress_small_batch():
    # Stress test kecil: Kirim 50 event secepat mungkin dan ukur waktu.
    start_time = time.time()
    count = 50
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(requests.post, f"{BASE_URL}/publish", json=generate_payload()) for _ in range(count)]
        concurrent.futures.wait(futures)
        
    duration = time.time() - start_time
    print(f"\n[INFO] 50 Request selesai dalam {duration:.2f} detik")
    assert duration < 5.0 


def test_14_get_events_content():
    # Memastikan data yang dikirim bisa diambil kembali via GET /events.
    unique_topic = f"topic_{uuid.uuid4()}"
    data = generate_payload(topic=unique_topic)
    requests.post(f"{BASE_URL}/publish", json=data)
    
    # Ambil events
    res = requests.get(f"{BASE_URL}/events?limit=100")
    events = res.json()
    
    # Cari event kita
    found = any(e["topic"] == unique_topic for e in events)
    assert found is True

def test_15_get_events_limit_param():
    # Parameter ?limit=... harus berfungsi.
    res = requests.get(f"{BASE_URL}/events?limit=2")
    data = res.json()
    assert isinstance(data, list)
    assert len(data) <= 2

def test_16_uptime_check():
    # Memastikan stats memiliki field uptime_seconds (sesuai update terakhir).
    stats = get_stats()
    assert "uptime_seconds" in stats
    assert isinstance(stats["uptime_seconds"], (int, float))