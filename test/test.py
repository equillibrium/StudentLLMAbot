import requests

def is_geo_blocked(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 403:
            return True, "403 Forbidden - Likely geo-blocked"
        elif "geo-blocked" in response.text.lower():
            return True, "Content indicates geo-blocking"
        else:
            return False, "Accessible"
    except requests.exceptions.RequestException as e:
        return None, f"Request failed: {e}"

# Replace with a GROQ URL
test_url = "https://console.groq.com"
blocked, message = is_geo_blocked(test_url)

if blocked is None:
    print("Error:", message)
elif blocked:
    print("Geo-blocked:", message)
else:
    print("Accessible:", message)
