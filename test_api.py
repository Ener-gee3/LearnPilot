import requests

url = "http://127.0.0.1:8000/generate"
data = {
    "topic": "FastAPI",
    "mode": "Concept-First Learning"
}

print(f"Testing connection to: {url}...")
try:
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    print("Response Data:")
    print(response.json())
except Exception as e:
    print(f"Error: {e}")
    print("Make sure your uvicorn server is running!")
