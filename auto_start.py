import socket
import subprocess
import os
import time

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def start_service(cmd, log_file, env=None):
    with open(log_file, 'w') as f:
        return subprocess.Popen(cmd, stdout=f, stderr=f, env=env)

def main():
    # Service ports
    BROWSER_PORT = 5006
    APP_PORT = 5003

    print(f"Checking ports: {BROWSER_PORT}, {APP_PORT}...")
    
    if is_port_in_use(BROWSER_PORT):
        print(f"Warning: Port {BROWSER_PORT} is already in use.")
    if is_port_in_use(APP_PORT):
        print(f"Warning: Port {APP_PORT} is already in use.")

    print("Starting Browser Server...")
    start_service(['python3', 'browser_server.py'], 'browser_5006.log')
    
    print("Starting App Server...")
    env = os.environ.copy()
    env['BROWSER_SERVICE_URL'] = f'http://localhost:{BROWSER_PORT}'
    start_service(['python3', 'app.py'], 'app_5003.log', env=env)

    print("Waiting 10 seconds for initialization...")
    time.sleep(10)
    print("Startup sequence complete. Check logs for details.")

if __name__ == '__main__':
    main()
