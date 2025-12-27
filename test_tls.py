import tls_client
print("Imported tls_client")
try:
    session = tls_client.Session(client_identifier="chrome_120")
    print("Session created")
    resp = session.get("https://www.google.com")
    print(f"Response: {resp.status_code}")
except Exception as e:
    print(f"Error: {e}")
