import json
import uuid

import httpx
import pytest

from lognix.loki.client import LokiClient, LokiError, selector


def test_selector_escapes_text() -> None:
    pid = uuid.uuid4()
    assert selector(pid) == f'{{container_id="{pid}"}}'
    assert (
        selector(pid, text='a "quoted" \\ thing')
        == f'{{container_id="{pid}"}} |= "a \\"quoted\\" \\\\ thing"'
    )


async def test_query_range_flattens_and_sorts() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        body = {
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": [
                    {
                        "stream": {"container": "api", "host": "vm"},
                        "values": [["3000", "c"], ["1000", "a"]],
                    },
                    {
                        "stream": {"container": "api", "host": "vm", "x": "y"},
                        "values": [["2000", "b"]],
                    },
                ],
            },
        }
        return httpx.Response(200, json=body)

    client = LokiClient("http://loki.test", transport=httpx.MockTransport(handler))
    lines = await client.query_range(
        '{container_id="x"}', start_ns=0, end_ns=5000, limit=10, direction="forward"
    )
    await client.aclose()
    assert [ln.line for ln in lines] == ["a", "b", "c"]
    assert lines[1].labels == {"container": "api", "host": "vm", "x": "y"}
    assert seen["limit"] == "10" and seen["direction"] == "forward" and seen["start"] == "0"


async def test_query_range_errors() -> None:
    client = LokiClient(
        "http://loki.test",
        transport=httpx.MockTransport(lambda r: httpx.Response(500, text="boom")),
    )
    with pytest.raises(LokiError):
        await client.query_range('{a="b"}', start_ns=0, end_ns=1)
    await client.aclose()


def test_limit_is_capped() -> None:
    # MAX_LIMIT é aplicado no cliente; verifica através do parâmetro enviado
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.url.params))
        return httpx.Response(200, json={"status": "success", "data": {"result": []}})

    import asyncio

    client = LokiClient("http://loki.test", transport=httpx.MockTransport(handler))
    asyncio.run(client.query_range('{a="b"}', start_ns=0, end_ns=1, limit=999999))
    assert captured["limit"] == "5000"
    json.dumps(captured)
