import asyncio
import json

import httpx
import pytest

from app.core.config import settings
from app.services.intervals_real import SCOPES, IntervalsError, RealIntervalsAdapter
from app.services.vertex_assistant import ProviderFailure, VertexAssistant


def test_intervals_code_exchange_and_remote_revoke_contract(monkeypatch):
    monkeypatch.setattr(settings, "INTERVALS_CLIENT_ID", "client")
    monkeypatch.setattr(settings, "INTERVALS_CLIENT_SECRET", "fixture-secret")
    calls = []

    def handler(request):
        calls.append(request)
        if request.method == "POST":
            assert request.url == "https://intervals.icu/api/oauth/token"
            assert set(httpx.QueryParams(request.content.decode())) == {"client_id", "client_secret", "code"}
            return httpx.Response(
                200,
                json={
                    "token_type": "Bearer",
                    "access_token": "fixture-token",
                    "scope": ",".join(SCOPES),
                    "athlete": {"id": "i123"},
                },
            )
        assert request.url == "https://intervals.icu/api/v1/disconnect-app"
        assert request.headers["authorization"] == "Bearer fixture-token"
        return httpx.Response(200)

    async def run():
        adapter = RealIntervalsAdapter(httpx.MockTransport(handler))
        token = await adapter.exchange_code("fixture-code")
        assert "refresh_token" not in token
        await adapter.disconnect(token["access_token"])

    asyncio.run(run())
    assert len(calls) == 2


def test_partial_scopes_are_revoked_not_persisted():
    calls = []

    def handler(request):
        calls.append(request.method)
        return (
            httpx.Response(
                200,
                json={
                    "token_type": "Bearer",
                    "access_token": "partial",
                    "scope": "ACTIVITY:READ",
                    "athlete": {"id": "i123"},
                },
            )
            if request.method == "POST"
            else httpx.Response(200)
        )

    with pytest.raises(IntervalsError, match="REQUIRED_SCOPES_MISSING"):
        asyncio.run(RealIntervalsAdapter(httpx.MockTransport(handler)).exchange_code("code"))
    assert calls == ["POST", "DELETE"]


@pytest.mark.parametrize(
    "status,code,calls",
    [
        (401, "RECONNECT_REQUIRED", 1),
        (403, "RECONNECT_REQUIRED", 1),
        (429, "TEMPORARILY_UNAVAILABLE", 3),
        (500, "TEMPORARILY_UNAVAILABLE", 3),
        (302, "REQUEST_REJECTED", 1),
    ],
)
def test_intervals_bounded_errors_no_redirect(status, code, calls):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, headers={"location": "https://attacker.invalid/"})

    with pytest.raises(IntervalsError, match=code):
        asyncio.run(RealIntervalsAdapter(httpx.MockTransport(handler)).activity("secret", "i1"))
    assert len(requests) == calls
    assert all(r.url.host == "intervals.icu" for r in requests)


def test_intervals_external_path_is_validated_before_network():
    called = []

    def handler(request):
        called.append(request)
        return httpx.Response(200)

    with pytest.raises(IntervalsError, match="INVALID_EXTERNAL_ID"):
        asyncio.run(RealIntervalsAdapter(httpx.MockTransport(handler)).activity("secret", "../private"))
    assert not called


def configure_vertex(monkeypatch):
    for field, value in {
        "AI_GCP_PROJECT": "fixture-project",
        "AI_GCP_LOCATION": "us-central1",
        "AI_MODEL": "gemini-fixture",
    }.items():
        monkeypatch.setattr(settings, field, value)


async def token():
    return "fixture-adc-token"


def test_vertex_real_rest_stream_structured_usage_contract(monkeypatch):
    configure_vertex(monkeypatch)

    def handler(request):
        assert request.headers["authorization"] == "Bearer fixture-adc-token"
        assert request.url.path.endswith("/models/gemini-fixture:streamGenerateContent")
        assert request.url.params["alt"] == "sse"
        payload = json.loads(request.content)
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        assert "responseSchema" in payload["generationConfig"]
        first = {"candidates": [{"content": {"parts": [{"text": '{"answer":"Listo",'}]}}]}
        final = {
            "candidates": [
                {"content": {"parts": [{"text": '"citation_keys":["profile:1:1"]}'}]}, "finishReason": "STOP"}
            ],
            "usageMetadata": {"promptTokenCount": 42, "candidatesTokenCount": 12, "thoughtsTokenCount": 3},
        }
        return httpx.Response(200, text="data: " + json.dumps(first) + "\n\ndata: " + json.dumps(final) + "\n\n")

    result = asyncio.run(VertexAssistant(httpx.MockTransport(handler), token).generate({"role": "athlete"}, [], "hola"))
    assert result.answer.answer == "Listo"
    assert result.input_tokens == 42 and result.output_tokens == 15


@pytest.mark.parametrize(
    "text",
    [
        '{"answer":"fake","citation_keys":[],"publish":true}',
        '{"answer":"ok","citation_keys":[],"proposed_write":{"operation":"publish","payload_json":"{}"}}',
        "malformed",
    ],
)
def test_vertex_invalid_outputs_fail_closed(monkeypatch, text):
    configure_vertex(monkeypatch)

    def handler(request):
        chunk = {
            "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
        }
        return httpx.Response(200, text="data: " + json.dumps(chunk) + "\n\n")

    with pytest.raises(ProviderFailure, match="INVALID_OUTPUT"):
        asyncio.run(VertexAssistant(httpx.MockTransport(handler), token).generate({}, [], "hola"))


def test_vertex_stream_cancellation_closes_transport(monkeypatch):
    configure_vertex(monkeypatch)

    class SlowStream(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            yield b'data: {"candidates":[]}\n\n'
            await asyncio.sleep(10)

        async def aclose(self):
            self.closed = True

    stream = SlowStream()

    async def run():
        adapter = VertexAssistant(httpx.MockTransport(lambda _: httpx.Response(200, stream=stream)), token)
        task = asyncio.create_task(adapter.generate({}, [], "hola"))
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert stream.closed
