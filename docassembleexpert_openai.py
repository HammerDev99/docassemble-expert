"""
Capa de integración de DocAssemble Expert con la Responses API de OpenAI.

Sustituye a la antigua Assistants API (``client.beta.assistants`` /
``client.beta.threads`` / ``runs`` / ``messages``), retirada por OpenAI el
26 de agosto de 2026.

Principios de diseño:

* **Sin estado en el servidor.** OpenAI ya no administra "threads". El historial
  vive en la aplicación (``st.session_state``) y se envía completo en cada
  llamada. Por defecto ``store=False`` para que OpenAI no conserve las
  respuestas (datos judiciales potencialmente sensibles).
* **Sin dependencia de Streamlit.** Este módulo es Python puro para poder
  probarlo con ``pytest`` y reutilizarlo en otros proyectos.
* **Configuración en código, no en el panel de OpenAI.** Lo que antes vivía en
  el objeto Assistant (instrucciones, modelo, herramientas) ahora está en
  :class:`AssistantProfile`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import openai

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valores por defecto
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_MAX_HISTORY_MESSAGES = 40  # 20 turnos usuario/asistente
DEFAULT_MAX_DOC_CHARS = 5000  # Límite por documento inyectado en el contexto

# Instrucciones del sistema. Antes vivían en el Assistant de OpenAI; ahora se
# versionan en prompts/docassembleexpert_instrucciones.md (con este respaldo mínimo en código).
# Se pueden sobreescribir con el secreto ASSISTANT_INSTRUCTIONS.
INSTRUCTIONS_FILE = Path(__file__).resolve().parent / "prompts" / "docassembleexpert_instrucciones.md"

_FALLBACK_INSTRUCTIONS = """Eres DocAssemble Expert, un asistente virtual especializado. Tu asistente especializado en Docassemble para crear interviews automatizadas usando YAML.

Responde siempre en español, con tono profesional, claro y cercano, en Markdown. Fundamenta tus respuestas en la documentación disponible y cita las fuentes cuando uses la búsqueda de archivos. No inventes información: si no la tienes, dilo. Cuando el contexto incluya documentos procesados por OCR, analízalos, resume lo relevante e indica si el texto parece incompleto."""


def load_default_instructions(path: Any = INSTRUCTIONS_FILE) -> str:
    """Lee las instrucciones del archivo de prompts; si no existe, usa el respaldo en código."""
    try:
        text = Path(path).read_text(encoding="utf-8").strip()
        if text:
            return text
    except OSError:
        logger.warning("No se encontró %s; se usan las instrucciones de respaldo.", path)
    return _FALLBACK_INSTRUCTIONS


DEFAULT_INSTRUCTIONS = load_default_instructions()

DOCUMENT_CONTEXT_HEADER = (
    "### Contexto de documentos procesados\n\n"
    "El usuario adjuntó los siguientes documentos (texto extraído por OCR). "
    "Úsalos para responder cuando sean pertinentes.\n\n"
)

FILE_SEARCH_STATUS_LABELS = {
    "response.file_search_call.in_progress": "Buscando en la base de conocimiento...",
    "response.file_search_call.searching": "Buscando en la base de conocimiento...",
    "response.file_search_call.completed": "Búsqueda completada. Redactando respuesta...",
}


class ResponsesChatError(RuntimeError):
    """Error reportado por la Responses API dentro de un stream."""


# ---------------------------------------------------------------------------
# Limpieza de marcadores internos de cita
# ---------------------------------------------------------------------------
# Con file_search el modelo emite marcadores internos del tipo
# "\ue200filecite\ue202turn0file6\ue201" (caracteres de uso privado) o, cuando
# el servidor no logra resolverlos, el texto residual "fileciteturn0file6turn0file3".
# Normalmente OpenAI los elimina y entrega `annotations`, pero no siempre.

_PUA_CHARS = "\ue000-\uf8ff"
_MARKER_RE = re.compile(
    rf"[{_PUA_CHARS}]*(?:file)?cite(?:[{_PUA_CHARS}]*turn\d+(?:file|search|news|view|image)\d+)+[{_PUA_CHARS}]*"
    rf"|[{_PUA_CHARS}]+"
)
_PARTIAL_MARKER_TAIL_RE = re.compile(
    rf"(?:[{_PUA_CHARS}]|\b(?:f|fi|fil|file|filec|fileci|filecit|c|ci|cit)?cite?(?:turn\d*(?:file\d*)?)*)$"
)
_SPACE_BEFORE_PUNCT_RE = re.compile(r"[ \t]+([.,;:!?])")
_DUPLICATE_MARKER_RE = re.compile(r"\[(\d+)\](?:\s*\[\1\])+")


def _marker_spans(text: str) -> List[Tuple[int, int]]:
    return [(m.start(), m.end()) for m in _MARKER_RE.finditer(text or "")]


def _remap_index(index: int, spans: Sequence[Tuple[int, int]]) -> int:
    """Traduce un índice del texto original al texto sin marcadores."""
    removed = 0
    for start, end in spans:
        if end <= index:
            removed += end - start
        elif start <= index < end:
            return start - removed
        else:
            break
    return index - removed


def strip_citation_markers(text: str) -> str:
    """Elimina marcadores internos de cita y caracteres de uso privado."""
    return _MARKER_RE.sub("", text or "")


def clean_streaming_text(text: str) -> str:
    """
    Limpia el texto acumulado durante el streaming: elimina marcadores completos
    y un posible marcador a medio llegar al final del texto (evita parpadeos).
    """
    cleaned = strip_citation_markers(text)
    return _PARTIAL_MARKER_TAIL_RE.sub("", cleaned)


def _tidy_spacing(text: str) -> str:
    """Quita los espacios que dejan los marcadores eliminados antes de la puntuación
    y colapsa marcadores repetidos de la misma fuente ("[1] [1]" -> "[1]")."""
    text = _DUPLICATE_MARKER_RE.sub(r"[\1]", text)
    return _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)


# ---------------------------------------------------------------------------
# Modelos de datos
# ---------------------------------------------------------------------------


@dataclass
class AssistantProfile:
    """Configuración del asistente (lo que antes era el objeto Assistant)."""

    name: str = "DocAssemble Expert"
    model: str = DEFAULT_MODEL
    instructions: str = DEFAULT_INSTRUCTIONS
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_output_tokens: Optional[int] = None
    reasoning_effort: Optional[str] = None
    vector_store_ids: List[str] = field(default_factory=list)
    max_history_messages: int = DEFAULT_MAX_HISTORY_MESSAGES
    max_doc_chars: int = DEFAULT_MAX_DOC_CHARS
    store: bool = False

    @property
    def has_knowledge_base(self) -> bool:
        return bool(self.vector_store_ids)


@dataclass
class Citation:
    number: int
    file_id: str
    filename: str


@dataclass
class ChatReply:
    """Respuesta normalizada del modelo."""

    text: str  # Texto limpio (sin marcadores), para el historial que se reenvía
    content: str  # Texto con marcadores [n] y referencias, para mostrar al usuario
    response_id: Optional[str] = None
    citations: List[Citation] = field(default_factory=list)
    status: Optional[str] = None
    usage: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _get(obj: Any, name: str, default: Any = None) -> Any:
    """Lee un atributo tanto de objetos pydantic como de diccionarios."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _truncate(text: str, max_chars: int) -> str:
    if max_chars and len(text) > max_chars:
        return text[:max_chars] + "..."
    return text


def load_profile(get_setting: Callable[[str, Any], Any], name: str = "DocAssemble Expert") -> AssistantProfile:
    """
    Construye el perfil a partir de un lector de configuración
    (``get_setting(clave, valor_por_defecto)`` que consulta env/secrets).
    """
    profile = AssistantProfile(name=name)

    model = get_setting("OPENAI_MODEL", None)
    if model:
        profile.model = str(model).strip()

    instructions = get_setting("ASSISTANT_INSTRUCTIONS", None)
    if instructions and str(instructions).strip():
        profile.instructions = str(instructions)

    temperature = get_setting("OPENAI_TEMPERATURE", None)
    if temperature not in (None, ""):
        profile.temperature = float(temperature)

    top_p = get_setting("OPENAI_TOP_P", None)
    if top_p not in (None, ""):
        profile.top_p = float(top_p)

    max_output_tokens = get_setting("OPENAI_MAX_OUTPUT_TOKENS", None)
    if max_output_tokens not in (None, ""):
        profile.max_output_tokens = int(max_output_tokens)

    reasoning_effort = get_setting("OPENAI_REASONING_EFFORT", None)
    if reasoning_effort:
        profile.reasoning_effort = str(reasoning_effort).strip()

    vector_stores = get_setting("VECTOR_STORE_ID", None)
    if vector_stores:
        if isinstance(vector_stores, (list, tuple)):
            ids = [str(v).strip() for v in vector_stores]
        else:
            ids = [v.strip() for v in str(vector_stores).split(",")]
        profile.vector_store_ids = [v for v in ids if v]

    max_history = get_setting("OPENAI_MAX_HISTORY_MESSAGES", None)
    if max_history not in (None, ""):
        profile.max_history_messages = int(max_history)

    max_doc_chars = get_setting("OPENAI_MAX_DOC_CHARS", None)
    if max_doc_chars not in (None, ""):
        profile.max_doc_chars = int(max_doc_chars)

    store = get_setting("OPENAI_STORE", None)
    if store not in (None, ""):
        profile.store = str(store).strip().lower() in ("1", "true", "yes", "si", "sí")

    if get_setting("ASSISTANT_ID", None):
        logger.warning(
            "ASSISTANT_ID está configurado pero ya no se usa: la Assistants API fue retirada. "
            "Configure ASSISTANT_INSTRUCTIONS, OPENAI_MODEL y VECTOR_STORE_ID en su lugar."
        )

    return profile


# ---------------------------------------------------------------------------
# Construcción del contexto y de la petición
# ---------------------------------------------------------------------------


def extract_document_text(doc_content: Any, max_chars: int = DEFAULT_MAX_DOC_CHARS) -> Optional[str]:
    """Obtiene el texto útil de un resultado de OCR (mismas reglas que la versión anterior)."""
    if not isinstance(doc_content, dict):
        return None
    text = doc_content.get("text")
    if isinstance(text, str) and text.strip():
        return _truncate(text, max_chars)
    raw = doc_content.get("raw_response")
    if isinstance(raw, dict) and isinstance(raw.get("text"), str) and raw["text"].strip():
        return _truncate(raw["text"], max_chars)
    return None


def build_document_context(doc_contents: Optional[Dict[str, Any]], max_chars: int = DEFAULT_MAX_DOC_CHARS) -> str:
    """Convierte los documentos OCR de la sesión en un bloque de texto para el modelo."""
    if not doc_contents:
        return ""

    blocks: List[str] = []
    for doc_name, doc_content in doc_contents.items():
        text = extract_document_text(doc_content, max_chars)
        if text:
            blocks.append(f"-- Documento: {doc_name} --\n{text}\n")
        elif isinstance(doc_content, dict) and "error" in doc_content:
            blocks.append(f"-- Documento: {doc_name} -- (Error al extraer texto: {doc_content['error']})\n")
        elif isinstance(doc_content, dict):
            blocks.append(f"-- Documento: {doc_name} -- (No se pudo extraer texto)\n")
        else:
            blocks.append(f"-- Documento: {doc_name} -- (Formato no reconocido)\n")

    if not blocks:
        return ""
    return DOCUMENT_CONTEXT_HEADER + "\n".join(blocks)


def sanitize_history(history: Optional[Iterable[Dict[str, Any]]]) -> List[Dict[str, str]]:
    """Deja solo mensajes user/assistant con contenido de texto no vacío."""
    clean: List[Dict[str, str]] = []
    for message in history or []:
        role = _get(message, "role")
        content = _get(message, "content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            clean.append({"role": role, "content": content})
    return clean


def trim_history(history: Sequence[Dict[str, str]], max_messages: int = DEFAULT_MAX_HISTORY_MESSAGES) -> List[Dict[str, str]]:
    """Conserva únicamente los últimos ``max_messages`` mensajes."""
    if max_messages is None or max_messages <= 0:
        return list(history)
    return list(history)[-max_messages:]


def build_input(
    history: Sequence[Dict[str, str]],
    user_text: str,
    document_context: str = "",
) -> List[Dict[str, str]]:
    """
    Arma la lista ``input`` de la Responses API:
    contexto documental (developer) + historial + mensaje nuevo del usuario.
    """
    items: List[Dict[str, str]] = []
    if document_context:
        items.append({"role": "developer", "content": document_context})
    items.extend({"role": m["role"], "content": m["content"]} for m in history)
    items.append({"role": "user", "content": user_text})
    return items


def build_tools(profile: AssistantProfile) -> List[Dict[str, Any]]:
    tools: List[Dict[str, Any]] = []
    if profile.vector_store_ids:
        tools.append({"type": "file_search", "vector_store_ids": list(profile.vector_store_ids)})
    return tools


def build_request(
    profile: AssistantProfile,
    history: Optional[Iterable[Dict[str, Any]]],
    user_text: str,
    document_context: str = "",
    cache_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Parámetros para ``client.responses.create`` / ``client.responses.stream``."""
    clean_history = trim_history(sanitize_history(history), profile.max_history_messages)
    kwargs: Dict[str, Any] = {
        "model": profile.model,
        "instructions": profile.instructions,
        "input": build_input(clean_history, user_text, document_context),
        "store": profile.store,
    }
    tools = build_tools(profile)
    if tools:
        kwargs["tools"] = tools
    if profile.temperature is not None:
        kwargs["temperature"] = profile.temperature
    if profile.top_p is not None:
        kwargs["top_p"] = profile.top_p
    if profile.max_output_tokens:
        kwargs["max_output_tokens"] = profile.max_output_tokens
    if profile.reasoning_effort:
        kwargs["reasoning"] = {"effort": profile.reasoning_effort}
    if cache_key:
        kwargs["prompt_cache_key"] = cache_key
    return kwargs


# ---------------------------------------------------------------------------
# Procesamiento de la respuesta
# ---------------------------------------------------------------------------


def format_citations(
    parts: Sequence[Tuple[str, Sequence[Any]]],
    file_names: Optional[Dict[str, str]] = None,
) -> Tuple[str, str, List[Citation]]:
    """
    Inserta marcadores ``[n]`` en el texto y arma el pie de referencias.

    ``parts`` es una secuencia de ``(texto, anotaciones)``; cada ``index`` de
    anotación es relativo a su propio texto.

    Devuelve ``(texto_limpio, texto_con_referencias, citas)``.
    """
    file_names = file_names or {}
    sources: Dict[str, Citation] = {}
    rendered_parts: List[str] = []
    plain_parts: List[str] = []

    for text, annotations in parts:
        raw_text = text or ""
        spans = _marker_spans(raw_text)
        text = strip_citation_markers(raw_text)
        plain_parts.append(_tidy_spacing(text))
        markers = set()
        for ann in annotations or []:
            if _get(ann, "type") != "file_citation":
                continue
            file_id = _get(ann, "file_id") or ""
            filename = _get(ann, "filename") or file_names.get(file_id) or "Documento de referencia"
            key = file_id or filename
            if key not in sources:
                sources[key] = Citation(number=len(sources) + 1, file_id=file_id, filename=filename)
            index = _get(ann, "index")
            if isinstance(index, int):
                index = _remap_index(min(max(index, 0), len(raw_text)), spans)
                markers.add((min(max(index, 0), len(text)), sources[key].number))

        rendered = text
        for index, number in sorted(markers, reverse=True):
            rendered = rendered[:index] + f"[{number}]" + rendered[index:]
        rendered_parts.append(_tidy_spacing(rendered))

    plain_text = "\n\n".join(p for p in plain_parts if p)
    content = "\n\n".join(p for p in rendered_parts if p)
    citations = sorted(sources.values(), key=lambda c: c.number)
    if citations:
        references = "\n".join(f"[{c.number}] Fuente: {c.filename}" for c in citations)
        content = f"{content}\n\n--- Referencias: ---\n{references}"
    return plain_text, content, citations


def extract_reply(response: Any, file_names: Optional[Dict[str, str]] = None) -> ChatReply:
    """Normaliza un objeto ``Response`` de la Responses API."""
    parts: List[Tuple[str, Sequence[Any]]] = []
    refusals: List[str] = []

    for item in _get(response, "output", None) or []:
        if _get(item, "type") != "message":
            continue
        for part in _get(item, "content", None) or []:
            part_type = _get(part, "type")
            if part_type == "output_text":
                parts.append((_get(part, "text") or "", _get(part, "annotations") or []))
            elif part_type == "refusal":
                refusals.append(_get(part, "refusal") or "")

    plain_text, content, citations = format_citations(parts, file_names)

    if not plain_text.strip() and refusals:
        plain_text = content = "\n\n".join(r for r in refusals if r)

    status = _get(response, "status")
    if status == "incomplete":
        details = _get(response, "incomplete_details")
        reason = _get(details, "reason") or "límite alcanzado"
        content = f"{content}\n\n_(Respuesta incompleta: {reason})_" if content else f"_(Respuesta incompleta: {reason})_"

    usage_obj = _get(response, "usage")
    usage = {}
    if usage_obj is not None:
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = _get(usage_obj, key)
            if isinstance(value, int):
                usage[key] = value

    return ChatReply(
        text=plain_text,
        content=content,
        response_id=_get(response, "id"),
        citations=citations,
        status=status,
        usage=usage,
    )


def friendly_error_message(exc: BaseException) -> str:
    """Mensaje en español para el usuario final según el tipo de error de OpenAI."""
    if isinstance(exc, openai.AuthenticationError):
        return "La API Key de OpenAI no es válida o fue revocada. Verifique OPENAI_API_KEY."
    if isinstance(exc, openai.PermissionDeniedError):
        return "La cuenta de OpenAI no tiene acceso al modelo o recurso solicitado."
    if isinstance(exc, openai.NotFoundError):
        return "OpenAI no encontró el modelo o la base de conocimiento. Revise OPENAI_MODEL y VECTOR_STORE_ID."
    if isinstance(exc, openai.RateLimitError):
        return "Se alcanzó el límite de uso o la cuota de OpenAI. Intente de nuevo en unos segundos."
    if isinstance(exc, openai.APITimeoutError):
        return "OpenAI tardó demasiado en responder. Intente nuevamente."
    if isinstance(exc, openai.APIConnectionError):
        return "No fue posible conectar con OpenAI. Verifique la conexión a internet."
    if isinstance(exc, openai.BadRequestError):
        return f"OpenAI rechazó la solicitud: {getattr(exc, 'message', str(exc))}"
    if isinstance(exc, openai.InternalServerError):
        return "OpenAI reportó un error interno. Intente nuevamente en unos minutos."
    if isinstance(exc, ResponsesChatError):
        return f"OpenAI reportó un error durante la respuesta: {exc}"
    return "Ocurrió un error al comunicarse con el asistente. Por favor, intente nuevamente."


# ---------------------------------------------------------------------------
# Cliente de conversación
# ---------------------------------------------------------------------------


class ResponsesChat:
    """
    Envía un turno de conversación a la Responses API.

    El historial lo aporta la aplicación en cada llamada; esta clase no guarda
    estado entre turnos salvo ``last_reply`` (resultado del último turno).
    """

    def __init__(self, client: Any, profile: AssistantProfile):
        self.client = client
        self.profile = profile
        self.last_reply: Optional[ChatReply] = None

    def stream_reply(
        self,
        history: Optional[Iterable[Dict[str, Any]]],
        user_text: str,
        document_context: str = "",
        cache_key: Optional[str] = None,
        on_status: Optional[Callable[[str], None]] = None,
        file_names: Optional[Dict[str, str]] = None,
    ) -> Iterator[str]:
        """
        Genera fragmentos de texto a medida que llegan. Al terminar deja la
        respuesta completa (con citas) en ``self.last_reply``.
        """
        self.last_reply = None
        kwargs = build_request(self.profile, history, user_text, document_context, cache_key)
        logger.info(
            "Responses API (stream): modelo=%s, items=%d, tools=%s",
            kwargs["model"], len(kwargs["input"]), [t["type"] for t in kwargs.get("tools", [])],
        )
        first_delta = True
        with self.client.responses.stream(**kwargs) as stream:
            for event in stream:
                event_type = getattr(event, "type", "")
                if event_type in ("response.output_text.delta", "response.refusal.delta"):
                    if first_delta and on_status:
                        on_status("Redactando respuesta...")
                    first_delta = False
                    yield event.delta
                elif event_type in FILE_SEARCH_STATUS_LABELS and on_status:
                    on_status(FILE_SEARCH_STATUS_LABELS[event_type])
                elif event_type == "error":
                    raise ResponsesChatError(getattr(event, "message", None) or "error desconocido")
                elif event_type == "response.failed":
                    error = _get(getattr(event, "response", None), "error")
                    raise ResponsesChatError(_get(error, "message") or "la respuesta falló")
            final = stream.get_final_response()
        self.last_reply = extract_reply(final, file_names)
        logger.info("Respuesta completada: id=%s, uso=%s", self.last_reply.response_id, self.last_reply.usage)

    def reply(
        self,
        history: Optional[Iterable[Dict[str, Any]]],
        user_text: str,
        document_context: str = "",
        cache_key: Optional[str] = None,
        file_names: Optional[Dict[str, str]] = None,
    ) -> ChatReply:
        """Variante sin streaming (respaldo)."""
        kwargs = build_request(self.profile, history, user_text, document_context, cache_key)
        logger.info(
            "Responses API (create): modelo=%s, items=%d", kwargs["model"], len(kwargs["input"])
        )
        response = self.client.responses.create(**kwargs)
        self.last_reply = extract_reply(response, file_names)
        return self.last_reply
