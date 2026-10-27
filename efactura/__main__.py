import webbrowser

import uvicorn

if __name__ == "__main__":
    url = "http://127.0.0.1:8765"
    print(f"e-Factura PFA rulează la {url}")
    webbrowser.open(url)
    uvicorn.run("efactura.app:app", host="127.0.0.1", port=8765)
