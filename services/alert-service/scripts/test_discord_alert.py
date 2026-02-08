import urllib.request
import json
import urllib.error
import time

url = "http://localhost:9004/signal"
data = {
    "signal_code": "SIG_GOLDEN_CROSS",
    "symbol": "TEST",
    "timestamp": int(time.time()),
    "data": {
        "ema_9": "150.50",
        "sma_20": "145.20"
    }
}

headers = {'Content-Type': 'application/json'}

def send_alert():
    print(f"Sending request to {url}...")
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
        with urllib.request.urlopen(req) as response:
            print(f"Status: {response.status}")
            print(f"Response: {response.read().decode('utf-8')}")
            return True
    except urllib.error.URLError as e:
        print(f"Connection failed: {e}")
        return False

# Retry loop in case service calls are still starting up
max_retries = 5
for i in range(max_retries):
    if send_alert():
        break
    if i < max_retries - 1:
        print(f"Retrying in 2 seconds ({i+1}/{max_retries})...")
        time.sleep(2)
