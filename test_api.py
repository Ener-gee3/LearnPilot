import requests

# The URL where your local FastAPI server is running
url = "http://127.0.0.1:8000/generate"

# Mock data to test the endpoint
data = {
    "topic": "Python Functions",
    "mode": "Concept-First Learning",
    "code_snippet": "def hello(): print('world')"
}

print(f"Sending POST request to: {url}")

try:
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("Success! Response from server:")
        print(response.json())
    else:
        print(f"Server returned an error: {response.text}")

except Exception as e:
    print(f"Connection Error: {e}")
    print("Ensure your server is running (uvicorn main:app --reload)")
