import requests
import traceback

url = "https://anchor.fm/s/d399ffec/podcast/rss"

print(f"Testing URL: {url}")

try:
    print("Sending request...")
    # Intentionally not setting User-Agent first to reproduce the issue
    response = requests.get(url, timeout=30)
    print(f"Status Code: {response.status_code}")
    print(f"Content Type: {response.headers.get('Content-Type')}")
    print(f"Content Length: {len(response.content)}")
    
    if response.status_code != 200:
        print("Non-200 status code!")
        print(response.text[:500])
    
    response.raise_for_status()
    print("Request successful.")
    
except Exception:
    traceback.print_exc()

print("\n--- Testing with User-Agent ---")
try:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    print("Sending request with User-Agent...")
    response = requests.get(url, headers=headers, timeout=30)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("Success with User-Agent!")
    else:
        print(f"Failed with User-Agent: {response.status_code}")

except Exception:
    traceback.print_exc()
