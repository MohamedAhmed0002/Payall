import subprocess, sys, os, time, webbrowser

root = os.path.dirname(os.path.abspath(__file__))
backend = subprocess.Popen([sys.executable, "run.py"], cwd=os.path.join(root, "backend"))
frontend = subprocess.Popen([sys.executable, "server.py"], cwd=os.path.join(root, "Frontend"))

time.sleep(3)
webbrowser.open("http://127.0.0.1:3000")

try:
    backend.wait()
except KeyboardInterrupt:
    pass
finally:
    backend.terminate()
    frontend.terminate()