"""Entry point for `python -m efactura` and for the Windows .exe."""
import os
import socket
import sys
import threading
import time
import webbrowser

HOST, PORT = "127.0.0.1", 8765
URL = f"http://{HOST}:{PORT}"


def is_up() -> bool:
    with socket.socket() as s:
        return s.connect_ex((HOST, PORT)) == 0


def open_browser_when_ready() -> None:
    for _ in range(150):
        if is_up():
            webbrowser.open(URL)
            return
        time.sleep(0.1)


def main() -> None:
    no_browser = os.environ.get("EFACTURA_NO_BROWSER") == "1"
    if is_up():
        # Double-clicking the .exe a second time should just bring the app back up.
        if not no_browser:
            webbrowser.open(URL)
        return

    import uvicorn

    from efactura.app import app
    from efactura.store import DATA_DIR

    if sys.stdout and hasattr(sys.stdout, "reconfigure"):  # cp1252 can't print "ă" when piped
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW("e-Factura PFA")
    print(f"e-Factura PFA rulează la {URL}")
    print(f"Datele tale: {DATA_DIR}")
    print("Închide această fereastră ca să oprești aplicația.\n")
    if not no_browser:
        threading.Thread(target=open_browser_when_ready, daemon=True).start()
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
