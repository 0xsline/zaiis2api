import os
import time
import subprocess
import signal
import sys

def kill_port(port):
    try:
        # Find PID using lsof
        cmd = f"lsof -t -i :{port}"
        pid = subprocess.check_output(cmd, shell=True).decode().strip()
        if pid:
            print(f"Killing process {pid} on port {port}...")
            os.kill(int(pid), signal.SIGKILL)
    except:
        pass

def main():
    print("Cleaning up ports...")
    kill_port(5005)
    kill_port(5002)
    time.sleep(1)

    print("Starting Browser Service on 5005...")
    # Use subprocess.Popen to start in background/independent
    browser_log = open("browser.log", "w")
    subprocess.Popen(["python3", "browser_server.py"], stdout=browser_log, stderr=browser_log)

    print("Starting API Service on 5002...")
    app_log = open("app.log", "w")
    env = os.environ.copy()
    env["BROWSER_SERVICE_URL"] = "http://localhost:5005"
    subprocess.Popen(["python3", "app.py"], stdout=app_log, stderr=app_log, env=env)

    print("Services started. Waiting 5s for warmup...")
    time.sleep(5)
    print("Ready!")

if __name__ == "__main__":
    main()
