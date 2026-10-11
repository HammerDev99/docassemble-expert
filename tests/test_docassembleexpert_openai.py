"""Pruebas de la capa de integración con la Responses API (sin red, sin Streamlit)."""
import subprocess
import sys
from pathlib import Path

import httpx2
import openai
import pytest
from openai.types.responses import (
    Response,
    ResponseCompletedEvent,
    ResponseFileSearchCallSearchingEvent,
    ResponseTextDeltaEvent,
)

import docassembleexpert_openai as t


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------


def make_response(text="Hola", annotations=None, status="completed", refusal=None):
    content = []
    if text is not None:
        content.append({"type": "output_text", "text": text, "annotations": annotations or []})
    if refusal is not None:
        content.append({"type": "refusal", "refusal": refusal})
    return Response.model_validate(
        {
            "id": "resp_123",
            "object": "response",
            "created_at": 0,
            "model": "gpt-test",
            "status": status,
            "parallel_tool_calls": True,
            "tool_choice": "auto",
            "tools": [],
            "output": [
                {"type": "message", "id": "msg_1", "role": "assistant", "status": "completed", "content": content}
            ],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
                "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": 0},
            },
            "incomplete_details": {"reason": "max_output_tokens"} if status == "incomplete" else None,
        }
    )


class FakeStream:
    def __init__(self, events, final):
        self.events = events
        self.final = final

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        return iter(self.events)

    def get_final_response(self):
        return self.final


class FakeResponses:
    def __init__(self, events=None, final=None):
        self.events = events or []
        self.final = final
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(("stream", kwargs))
        return FakeStream(self.events, self.final)

    def create(self, **kwargs):
        self.calls.append(("create", kwargs))
        return self.final


class FakeClient:
    def __init__(self, events=None, final=None):
        self.responses = FakeResponses(events, final)


# --------------------------------------------------------------------------
# Contexto documental e historial
# --------------------------------------------------------------------------


def test_build_document_context_truncates_and_reports_errors():
    docs = {
        "a.pdf": {"text": "x" * 6000},
        "b.pdf": {"error": "boom", "raw_response": {"text": "texto crudo"}},
        "c.pdf": {"error": "sin texto"},
        "d.pdf": "cadena",
    }
    ctx = t.build_document_context(docs, max_chars=5000)
    assert ctx.startswith(t.DOCUMENT_CONTEXT_HEADER)
    assert "-- Documento: a.pdf --\n" + "x" * 5000 + "..." in ctx
    assert "-- Documento: b.pdf --\ntexto crudo" in ctx
    assert "(Error al extraer texto: sin texto)" in ctx
    assert "(Formato no reconocido)" in ctx


def test_build_document_context_empty():
    assert t.build_document_context({}) == ""
    assert t.build_document_context(None) == ""


def test_sanitize_and_trim_history():
    history = [
        {"role": "user", "content": "1"},
        {"role": "assistant", "content": ""},
        {"role": "system", "content": "ignorar"},
        {"role": "assistant", "content": "2"},
        {"role": "user", "content": "3"},
    ]
    clean = t.sanitize_history(history)
    assert [m["content"] for m in clean] == ["1", "2", "3"]
    assert [m["content"] for m in t.trim_history(clean, 2)] == ["2", "3"]
    assert t.trim_history(clean, 0) == clean


def test_build_input_order():
    items = t.build_input([{"role": "user", "content": "hola"}, {"role": "assistant", "content": "buenas"}], "nuevo", "DOCS")
    assert items[0] == {"role": "developer", "content": "DOCS"}
    assert items[1:3] == [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "buenas"}]
    assert items[-1] == {"role": "user", "content": "nuevo"}
    assert t.build_input([], "solo", "")[0] == {"role": "user", "content": "solo"}


def test_build_request_minimal_profile_omits_sampling_and_tools():
    profile = t.AssistantProfile()
    req = t.build_request(profile, [], "hola")
    assert req["model"] == t.DEFAULT_MODEL
    assert req["instructions"] == t.DEFAULT_INSTRUCTIONS
    assert req["store"] is False
    for key in ("tools", "temperature", "top_p", "max_output_tokens", "reasoning", "prompt_cache_key"):
        assert key not in req


def test_build_request_with_knowledge_base_and_params():
    profile = t.AssistantProfile(
        model="gpt-5.5",
        temperature=0.2,
        top_p=0.9,
        max_output_tokens=800,
        reasoning_effort="low",
        vector_store_ids=["vs_1", "vs_2"],
        max_history_messages=2,
        store=True,
    )
    history = [{"role": "user", "content": str(i)} for i in range(5)]
    req = t.build_request(profile, history, "hola", "DOCS", cache_key="conv-1")
    assert req["tools"] == [{"type": "file_search", "vector_store_ids": ["vs_1", "vs_2"]}]
    assert req["temperature"] == 0.2 and req["top_p"] == 0.9
    assert req["max_output_tokens"] == 800
    assert req["reasoning"] == {"effort": "low"}
    assert req["prompt_cache_key"] == "conv-1"
    assert req["store"] is True
    # developer + 2 últimos del historial + nuevo
    assert [m["content"] for m in req["input"]] == ["DOCS", "3", "4", "hola"]


def test_load_profile_from_settings():
    settings = {
        "OPENAI_MODEL": " gpt-5.5 ",
        "ASSISTANT_INSTRUCTIONS": "Instrucciones propias",
        "OPENAI_TEMPERATURE": "0.3",
        "VECTOR_STORE_ID": "vs_a, vs_b",
        "OPENAI_MAX_HISTORY_MESSAGES": "10",
        "OPENAI_STORE": "true",
        "ASSISTANT_ID": "asst_viejo",
    }
    profile = t.load_profile(lambda k, d=None: settings.get(k, d))
    assert profile.model == "gpt-5.5"
    assert profile.instructions == "Instrucciones propias"
    assert profile.temperature == 0.3
    assert profile.vector_store_ids == ["vs_a", "vs_b"]
    assert profile.max_history_messages == 10
    assert profile.store is True
    assert profile.has_knowledge_base


def test_load_profile_defaults():
    profile = t.load_profile(lambda k, d=None: d)
    assert profile.model == t.DEFAULT_MODEL
    assert profile.temperature is None
    assert profile.vector_store_ids == []
    assert profile.store is False


# --------------------------------------------------------------------------
# Citas y extracción de la respuesta
# --------------------------------------------------------------------------


def test_format_citations_inserts_markers_and_references():
    text = "Primera idea. Segunda idea."
    annotations = [
        {"type": "file_citation", "file_id": "f1", "filename": "manual.pdf", "index": 14},
        {"type": "file_citation", "file_id": "f2", "filename": "tutela.pdf", "index": 27},
        {"type": "file_citation", "file_id": "f1", "filename": "manual.pdf", "index": 27},
        {"type": "url_citation", "url": "https://x", "start_index": 0, "end_index": 1},
    ]
    plain, content, citations = t.format_citations([(text, annotations)])
    assert plain == text
    assert content.startswith("Primera idea. [1]Segunda idea.[1][2]")
    assert "--- Referencias: ---\n[1] Fuente: manual.pdf\n[2] Fuente: tutela.pdf" in content
    assert [c.filename for c in citations] == ["manual.pdf", "tutela.pdf"]


def test_format_citations_without_annotations():
    plain, content, citations = t.format_citations([("texto", [])])
    assert plain == content == "texto"
    assert citations == []


def test_extract_reply_from_sdk_response_with_citations():
    resp = make_response(
        "Respuesta con fuente.",
        annotations=[{"type": "file_citation", "file_id": "file-1", "filename": "manual.pdf", "index": 21}],
    )
    reply = t.extract_reply(resp)
    assert reply.response_id == "resp_123"
    assert reply.text == "Respuesta con fuente."
    assert reply.content == "Respuesta con fuente.[1]\n\n--- Referencias: ---\n[1] Fuente: manual.pdf"
    assert reply.usage == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    assert reply.status == "completed"


def test_extract_reply_refusal_and_incomplete():
    refusal = t.extract_reply(make_response(text=None, refusal="No puedo ayudar con eso."))
    assert refusal.content == "No puedo ayudar con eso."
    incomplete = t.extract_reply(make_response("Parcial", status="incomplete"))
    assert incomplete.content.endswith("_(Respuesta incompleta: max_output_tokens)_")
    assert incomplete.text == "Parcial"


# --------------------------------------------------------------------------
# Cliente de conversación
# --------------------------------------------------------------------------


def _delta(text, seq):
    return ResponseTextDeltaEvent(
        type="response.output_text.delta", delta=text, content_index=0, item_id="msg_1",
        output_index=0, sequence_number=seq, logprobs=[],
    )


def test_stream_reply_yields_deltas_and_sets_last_reply():
    final = make_response("Hola mundo")
    events = [
        ResponseFileSearchCallSearchingEvent(
            type="response.file_search_call.searching", item_id="fs_1", output_index=0, sequence_number=1
        ),
        _delta("Hola ", 2),
        _delta("mundo", 3),
        ResponseCompletedEvent(type="response.completed", response=final, sequence_number=4),
    ]
    client = FakeClient(events, final)
    chat = t.ResponsesChat(client, t.AssistantProfile(vector_store_ids=["vs_1"]))
    statuses = []
    chunks = list(chat.stream_reply([{"role": "user", "content": "antes"}], "hola", "DOCS", on_status=statuses.append))
    assert chunks == ["Hola ", "mundo"]
    assert statuses == ["Buscando en la base de conocimiento...", "Redactando respuesta..."]
    assert chat.last_reply.text == "Hola mundo"
    kind, kwargs = client.responses.calls[0]
    assert kind == "stream"
    assert kwargs["tools"][0]["type"] == "file_search"
    assert [m["role"] for m in kwargs["input"]] == ["developer", "user", "user"]


def test_stream_reply_raises_on_error_event():
    class ErrorEvent:
        type = "error"
        message = "quota exceeded"

    client = FakeClient([ErrorEvent()], make_response("x"))
    chat = t.ResponsesChat(client, t.AssistantProfile())
    with pytest.raises(t.ResponsesChatError, match="quota exceeded"):
        list(chat.stream_reply([], "hola"))


def test_reply_non_streaming():
    client = FakeClient(final=make_response("Directo"))
    chat = t.ResponsesChat(client, t.AssistantProfile())
    reply = chat.reply([], "hola")
    assert reply.content == "Directo"
    assert client.responses.calls[0][0] == "create"


def test_friendly_error_messages():
    request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    auth = openai.AuthenticationError("bad key", response=httpx2.Response(401, request=request), body=None)
    assert "OPENAI_API_KEY" in t.friendly_error_message(auth)
    rate = openai.RateLimitError("slow", response=httpx2.Response(429, request=request), body=None)
    assert "límite" in t.friendly_error_message(rate)
    assert "intente nuevamente" in t.friendly_error_message(ValueError("x")).lower()


# --------------------------------------------------------------------------
# Instrucciones del sistema y base de conocimiento
# --------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]


def test_default_instructions_come_from_prompts_file():
    expected = (ROOT / "prompts" / "docassembleexpert_instrucciones.md").read_text(encoding="utf-8").strip()
    assert t.DEFAULT_INSTRUCTIONS == expected
    assert t.DEFAULT_INSTRUCTIONS.startswith("Eres DocAssemble Expert")


def test_load_default_instructions_falls_back_when_file_missing(tmp_path):
    assert t.load_default_instructions(tmp_path / "no_existe.md") == t._FALLBACK_INSTRUCTIONS


def test_vector_store_script_dry_run_lists_knowledge_files():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "crear_vector_store.py"), "--dry-run"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "docassembleexpert_base_conocimiento.md" in result.stdout
    assert "README.md" not in result.stdout
    assert "no se llamó a OpenAI" in result.stdout


# --------------------------------------------------------------------------
# Marcadores internos de cita de file_search
# --------------------------------------------------------------------------


def test_strip_citation_markers_removes_pua_and_textual_markers():
    raw = "Primera idea\ue200filecite\ue202turn0file6\ue201. Segunda fileciteturn0file6turn0file3. Fin."
    assert t.strip_citation_markers(raw) == "Primera idea. Segunda . Fin."
    assert t.strip_citation_markers("sin marcadores") == "sin marcadores"


def test_format_citations_remaps_indexes_after_stripping_markers():
    raw = "Primera idea\ue200filecite\ue202turn0file0\ue201. Segunda idea fileciteturn0file6turn0file3. Fin."
    marker1_end = raw.index("\ue201") + 1          # índice justo después del primer marcador
    marker2_end = raw.index("file3") + len("file3")  # justo después del marcador textual
    annotations = [
        {"type": "file_citation", "file_id": "f1", "filename": "manual.pdf", "index": marker1_end},
        {"type": "file_citation", "file_id": "f2", "filename": "base.md", "index": marker2_end},
    ]
    plain, content, citations = t.format_citations([(raw, annotations)])
    assert plain == "Primera idea. Segunda idea. Fin."
    assert content.startswith("Primera idea[1]. Segunda idea [2]. Fin.")
    assert [c.filename for c in citations] == ["manual.pdf", "base.md"]


def test_format_citations_tidies_space_left_by_server_stripped_marker():
    text = "del sistema . En la app se presenta ."
    plain, content, _ = t.format_citations([(text, [{"type": "file_citation", "file_id": "f1", "filename": "m.pdf", "index": 12}])])
    assert plain == "del sistema. En la app se presenta."
    assert content.startswith("del sistema [1]. En la app se presenta.")


def test_clean_streaming_text_hides_partial_marker_at_end():
    assert t.clean_streaming_text("expediente \ue200filecite\ue202turn0") == "expediente "
    assert t.clean_streaming_text("expediente filecite") == "expediente "
    assert t.clean_streaming_text("expediente fileciteturn0file") == "expediente "
    assert t.clean_streaming_text("expediente fileciteturn0file6turn0file3. Si quieres") == "expediente . Si quieres"
    assert t.clean_streaming_text("texto normal que termina en cita.") == "texto normal que termina en cita."
    assert t.clean_streaming_text("la cite") == "la "


def test_format_citations_collapses_adjacent_duplicate_markers():
    text = "soportes del caso [1] [1]. Otra idea."
    annotations = [
        {"type": "file_citation", "file_id": "f1", "filename": "a.pdf", "index": 18},
        {"type": "file_citation", "file_id": "f1", "filename": "a.pdf", "index": 19},
    ]
    _, content, _ = t.format_citations([("soportes del caso  . Otra idea.", annotations)])
    assert content.startswith("soportes del caso [1]. Otra idea.")
    assert t._tidy_spacing("x [2] [2] [2] y [3]") == "x [2] y [3]"
    assert t._tidy_spacing("x [1] [2]") == "x [1] [2]"
