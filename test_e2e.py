import sys
from starlette.testclient import TestClient
from backend.main import app

def main():
    client = TestClient(app)

    print("1. Testing health check...")
    res = client.get("/api/health")
    print("Health check status:", res.status_code, res.json())
    assert res.status_code == 200

    print("\n2. Testing voices endpoint...")
    res = client.get("/api/voices")
    print("Voices status:", res.status_code, "Languages:", list(res.json()["voices"].keys()))
    assert res.status_code == 200

    print("\n3. Testing PDF upload with sample_test_book.pdf...")
    with open("sample_test_book.pdf", "rb") as f:
        res = client.post("/api/upload", files={"file": ("sample_test_book.pdf", f, "application/pdf")})
    print("Upload status:", res.status_code, res.json())
    assert res.status_code == 200
    file_id = res.json()["file_id"]

    print("\n4. Testing preview endpoint...")
    res = client.get(f"/api/pdf/{file_id}/preview")
    preview_data = res.json()
    print("Preview status:", res.status_code, "Total pages:", preview_data["total_pages"], "Is scanned:", preview_data["is_scanned"])
    print("Sample preview text snippet:\n", preview_data["preview_text"][:120], "...")
    assert res.status_code == 200

    print("\n5. Testing generate audiobook (runs background pipeline)...")
    gen_payload = {
        "file_id": file_id,
        "language": "en",
        "voice": "en-US-AriaNeural",
        "speed": 1.0,
        "format": "mp3",
        "split_chapters": True
    }
    res = client.post("/api/audiobook/generate", json=gen_payload)
    print("Generate response:", res.status_code, res.json())
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    book_id = res.json()["audiobook_id"]

    print("\n6. Checking Job Status...")
    res = client.get(f"/api/jobs/{job_id}")
    job_info = res.json()
    print("Job Status:", res.status_code, job_info["status"], f"{job_info['progress']}%")
    print("Message:", job_info.get("message"))
    if job_info.get("error"):
        print("ERROR:", job_info["error"])

    assert job_info["status"] == "completed"
    assert job_info["audiobook"] is not None

    print("\n7. Testing audiobook chapters and download endpoints...")
    res = client.get(f"/api/audiobook/{book_id}/chapters")
    chapters_data = res.json()
    print("Chapters endpoint:", res.status_code, len(chapters_data["chapters"]), "chapters:")
    for ch in chapters_data["chapters"]:
        print(f"   -> Chapter {ch['chapter_number']}: {ch['title']} ({ch['duration_formatted']}, {ch['file_size_formatted']})")
    assert res.status_code == 200
    assert len(chapters_data["chapters"]) >= 2

    res = client.get(f"/api/audiobook/{book_id}/download")
    print("Master audiobook download status:", res.status_code, "bytes:", len(res.content))
    assert res.status_code == 200
    assert len(res.content) > 1000

    res = client.get(f"/api/audiobook/{book_id}/stream")
    print("Master audiobook stream status:", res.status_code, "Content-Type:", res.headers.get("content-type"))
    assert res.status_code == 200

    res = client.get(f"/api/audiobook/{book_id}/chapter/1/download")
    print("Chapter 1 download status:", res.status_code, "bytes:", len(res.content))
    assert res.status_code == 200

    print("\n8. Testing OCR status endpoint...")
    res = client.get("/api/ocr/status")
    print("OCR status:", res.status_code, res.json())
    assert res.status_code == 200

    print("\n9. Testing Frontend root endpoint...")
    res = client.get("/")
    print("Frontend index.html status:", res.status_code, "length:", len(res.content))
    assert res.status_code == 200
    assert "VoiceCraft" in res.text

    print("\nALL TESTS PASSED SUCCESSFULLY! Pipeline verified end-to-end.")

if __name__ == "__main__":
    main()
