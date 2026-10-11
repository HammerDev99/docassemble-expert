"""Prueba de humo de app.py con streamlit.testing (sin red): simula un turno completo de chat."""
from pathlib import Path

import openai
import pytest
from streamlit.testing.v1 import AppTest
from openai.types.responses import ResponseCompletedEvent

from test_docassembleexpert_openai import FakeClient, _delta, make_response

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class FakeModels:
    def list(self):
        return []


@pytest.fixture
def fake_openai(monkeypatch):
    final = make_response(
        "Respuesta de prueba del asistente.",
        annotations=[{"type": "file_citation", "file_id": "file-1", "filename": "manual.pdf", "index": 32}],
    )
    events = [
        _delta("Respuesta de prueba ", 1),
        _delta("del asistente.", 2),
        ResponseCompletedEvent(type="response.completed", response=final, sequence_number=3),
    ]
    client = FakeClient(events, final)
    client.models = FakeModels()
    captured = {}

    def fake_ctor(**kwargs):
        captured.update(kwargs)
        return client

    monkeypatch.setattr(openai, "OpenAI", fake_ctor)
    return client, captured


def test_full_chat_turn_uses_responses_api(fake_openai):
    client, ctor_kwargs = fake_openai

    at = AppTest.from_file(str(APP_PATH), default_timeout=60)
    at.secrets["OPENAI_API_KEY"] = "sk-test"
    at.secrets["MISTRAL_API_KEY"] = "mistral-test"
    at.secrets["VECTOR_STORE_ID"] = "vs_test"
    at.secrets["ASSISTANT_ID"] = "asst_obsoleto"
    at.session_state["feedback_dismissed"] = True
    at.run()
    assert not at.exception, at.exception

    # Cliente construido sin el encabezado beta de Assistants
    assert ctor_kwargs["api_key"] == "sk-test"
    assert "default_headers" not in ctor_kwargs
    assert at.session_state["conversation_id"].startswith("docassembleexpert-")

    # Turno de chat
    at.chat_input[0].set_value("¿Qué puedes hacer?").run()
    assert not at.exception, at.exception

    kind, kwargs = client.responses.calls[0]
    assert kind == "stream"
    assert kwargs["instructions"].startswith("Eres DocAssemble Expert")
    assert kwargs["tools"] == [{"type": "file_search", "vector_store_ids": ["vs_test"]}]
    assert kwargs["input"] == [{"role": "user", "content": "¿Qué puedes hacer?"}]
    assert kwargs["store"] is False
    assert kwargs["prompt_cache_key"] == at.session_state["conversation_id"]

    # Historial local: visible y el que se reenvía a la API
    history = at.session_state["api_history"]
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[1]["content"] == "Respuesta de prueba del asistente."
    shown = at.session_state["messages"][-1]["content"]
    assert "[1]" in shown and "Fuente: manual.pdf" in shown
    assert at.session_state["last_response_id"] == "resp_123"

    # Segundo turno: el historial previo viaja en el input
    at.chat_input[0].set_value("¿Y los memoriales?").run()
    assert not at.exception, at.exception
    _, kwargs2 = client.responses.calls[1]
    assert [m["role"] for m in kwargs2["input"]] == ["user", "assistant", "user"]
    assert kwargs2["input"][-1]["content"] == "¿Y los memoriales?"
