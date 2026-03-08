"""Simple smoke test for Git Archaeologist FastAPI app."""

from fastapi.testclient import TestClient

from api.app import app


if __name__ == "__main__":
    client = TestClient(app)
    response = client.get("/health")
    print("status_code:", response.status_code)
    print("body:", response.json())
