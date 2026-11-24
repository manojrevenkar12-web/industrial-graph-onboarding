import json

import httpx

from igo.platform.readers import ClaudeReader, OpenAICompatibleReader


def _claude(text):
    def handler(req):
        assert req.headers["x-api-key"] == "k"
        return httpx.Response(200, json={"content": [{"type": "text", "text": text}]})

    return ClaudeReader("k", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_claude_reads_a_mention():
    r = _claude('{"quote": "Pumpe 2103A", "confidence": 0.9}')
    assert r.mention("Druck Pumpe 2103A", "k")["quote"] == "Pumpe 2103A"


def test_garbage_is_no_reading():
    r = _claude("I think it is the pump")
    assert r.mention("x", "k") == {"quote": None, "confidence": 0.0}
    assert r.read_question("x", "k")["intent"] is None


def test_openai_compatible_question():
    def handler(req):
        body = json.loads(req.content)
        assert body["temperature"] == 0
        msg = '{"intent": "sensors", "entity": "P-2103A", "unit": "21", "confidence": 0.8}'
        return httpx.Response(200, json={"choices": [{"message": {"content": msg}}]})

    r = OpenAICompatibleReader("http://gw/v1", "k", "m", client=httpx.Client(transport=httpx.MockTransport(handler)))
    out = r.read_question("Which sensors are installed on P-2103A?", "q")
    assert out == {"intent": "sensors", "entity": "P-2103A", "unit": 21, "confidence": 0.8}
