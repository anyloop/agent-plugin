"""Scoped local media tool contract tests."""

from pathlib import Path

from adant_local import media


class PutResponse:
    status_code = 200


def test_upload_uses_presigned_three_step_flow(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    source.write_bytes(b"image-bytes")
    calls = []

    def fake_request(method, route, **kwargs):
        calls.append((method, route, kwargs))
        if route == "/v1/files/create-upload":
            return {"id": "file-1", "upload_url": "https://upload.test/file-1"}
        if route == "/v1/files/complete":
            return {"id": "file-1", "filename": "source.png"}
        return {"download_url": "https://download.test/file-1"}

    put_calls = []
    monkeypatch.setattr(media, "_request_json", fake_request)
    monkeypatch.setattr(
        media.httpx,
        "put",
        lambda url, **kwargs: put_calls.append((url, kwargs)) or PutResponse(),
    )

    result = media.upload_local_file(str(source))

    assert result["uploadId"] == "file-1"
    assert [call[1] for call in calls] == [
        "/v1/files/create-upload",
        "/v1/files/complete",
        "/v1/files/file-1/content",
    ]
    assert put_calls[0][1]["headers"]["content-length"] == str(len(b"image-bytes"))


def test_analyze_uploads_and_sends_signed_url(monkeypatch):
    monkeypatch.setattr(
        media,
        "upload_local_file",
        lambda _path: {"uploadId": "file-2", "url": "https://signed.test/video"},
    )
    seen = {}

    def fake_request(method, route, **kwargs):
        seen.update({"method": method, "route": route, **kwargs})
        return {"text": "three scenes"}

    monkeypatch.setattr(media, "_request_json", fake_request)
    result = media.analyze_local_file("video.mp4", {"prompt": "break it down"})

    assert result == {"uploadId": "file-2", "analysis": "three scenes"}
    assert seen["route"] == "/v1/media.video.analyze"
    assert seen["payload"]["videoUrl"] == "https://signed.test/video"


def test_edit_downloads_completed_artifact(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    output = tmp_path / "result.png"
    monkeypatch.setattr(
        media,
        "upload_local_file",
        lambda _path: {"uploadId": "file-3", "url": "https://signed.test/image"},
    )
    monkeypatch.setattr(
        media,
        "_request_json",
        lambda *_args, **_kwargs: {
            "jobId": "job-1",
            "status": "completed",
            "artifactUrl": "https://artifact.test/result",
        },
    )
    monkeypatch.setattr(
        media,
        "_download_artifact",
        lambda _url, path: Path(path).write_bytes(b"edited"),
    )

    result = media.edit_local_image(
        str(source), {"prompt": "make it blue", "output_path": str(output)}
    )

    assert result["outputPath"] == str(output)
    assert output.read_bytes() == b"edited"
