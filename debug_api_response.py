import requests
import json
import datetime

# Construct URL
# Need valid params. Item=CABLE_TEAR_3_1, Station=S01, Product=TestProduct, Line=L1.
# Time: Today.
now = datetime.datetime.now()
start = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
end = now.strftime("%Y-%m-%dT23:59:59")

url = f"http://localhost:8000/api/v1/history?item_name=CABLE_TEAR_3_1&station=S01&product=TestProduct&line=L1&start_time={start}&end_time={end}&limit=10"

try:
    print(f"Fetching {url}")
    res = requests.get(url)
    if res.status_code != 200:
        print(f"Error: {res.status_code} {res.text}")
    else:
        data = res.json()
        print(f"Got {len(data)} records.")
        if len(data) > 0:
            print("Message Sample:")
            print(json.dumps(data[0], indent=2))
            
            # Check alert count
            alerts = [r for r in data if r.get('is_alert')]
            print(f"Alert Count in first {len(data)} records: {len(alerts)}")
        else:
            print("No data found.")

except Exception as e:
    print(e)
