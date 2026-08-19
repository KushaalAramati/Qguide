# Simple local demo launcher — run:  python serve.py
import os
os.environ.setdefault("JWT_SECRET", "local-demo-secret")
os.environ.setdefault("ADMIN_EMAILS", "hnreddy@biovaram.com")
import uvicorn
if __name__ == "__main__":
    print("QGuide backend -> http://localhost:8000   (docs at /docs).  Ctrl+C to stop.")
    uvicorn.run("qguide.app.main:app", host="127.0.0.1", port=8000)
