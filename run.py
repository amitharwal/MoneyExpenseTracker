"""Start Ledger and open it in your browser.  Usage:  python run.py  [--no-browser]"""
import socket
import sys
import threading
import webbrowser

from config import DATA_DIR, HOST, PORT


def _port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((HOST, port)) == 0


def main():
    url = f"http://localhost:{PORT}/"
    open_browser = "--no-browser" not in sys.argv

    if _port_in_use(PORT):
        # Already running (e.g. in another terminal): just open it
        print(f"Ledger is already running at {url}")
        if open_browser:
            webbrowser.open(url)
        return

    from waitress import serve
    from app import app

    print(f"Ledger is running at {url}")
    print(f"Your data lives in {DATA_DIR}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.6, webbrowser.open, args=(url,)).start()
    serve(app, host=HOST, port=PORT, threads=8, _quiet=True)


if __name__ == "__main__":
    main()
