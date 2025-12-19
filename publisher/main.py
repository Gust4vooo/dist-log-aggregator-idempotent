import requests
import json
import time
import uuid
import random
import concurrent.futures
import os

AGGREGATOR_URL = os.getenv("AGGREGATOR_URL", "http://aggregator:8000/publish")
TOTAL_EVENTS = 20000     
DUPLICATION_RATE = 0.3    
CONCURRENCY = 20           

sent_event_ids = []

def generate_event():

    global sent_event_ids
    
    if sent_event_ids and random.random() < DUPLICATION_RATE:
        event_id = random.choice(sent_event_ids)
        is_retry = True
    else:
        event_id = str(uuid.uuid4())
        sent_event_ids.append(event_id)
        is_retry = False

    return {
        "topic": random.choice(["user_login", "payment_processed", "order_created", "system_log"]),
        "event_id": event_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "publisher_load_test",
        "payload": {
            "amount": random.randint(10, 1000), 
            "status": "active",
            "is_simulated_retry": is_retry
        }
    }

def send_event(seq_num):
    event = generate_event()
    try:
        response = requests.post(AGGREGATOR_URL, json=event, timeout=10)
        return response.status_code
    except Exception as e:
        return f"Error: {str(e)}"

def start_simulation():
    print(f"[START] Memulai Simulasi UAS")
    print(f"Target: {TOTAL_EVENTS} events")
    print(f"Duplikasi: {DUPLICATION_RATE*100}%")
    print(f"Concurrency: {CONCURRENCY} threads")
    
    print("Menunggu sistem siap (10 detik)...")
    time.sleep(10) 
    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(send_event, i) for i in range(TOTAL_EVENTS)]
        
        completed = 0
        for f in concurrent.futures.as_completed(futures):
            completed += 1
            if completed % 1000 == 0:
                elapsed = time.time() - start_time
                print(f"   -> Progress: {completed}/{TOTAL_EVENTS} events ({elapsed:.1f}s)")

    total_duration = time.time() - start_time
    print(f"\n[SELESAI] Semua request terkirim!")
    print(f"Total Waktu: {total_duration:.2f} detik")
    print(f"Throughput: {TOTAL_EVENTS/total_duration:.2f} request/detik")

if __name__ == "__main__":
    start_simulation()
    print("Publisher masuk mode tidur (Idle)")
    while True:
        time.sleep(60)