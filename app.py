import os
import streamlit as st
import time
import base64
import json
import requests
import tempfile
import logging
import traceback
import io
import sys
from datetime import datetime
from pathlib import Path
from io import BytesIO
from PIL import Image
from openai import OpenAI
from docassembleexpert_openai import (
    ResponsesChat,
    build_document_context,
    clean_streaming_text,
    friendly_error_message,
    load_profile,
)
import uuid
import streamlit.components.v1 as components
import re

# =============================================
# ANALYTICS INJECTION
# =============================================
def inject_analytics():
    """Inyecta el script de analytics en el head del documento"""
    if hasattr(st, "secrets") and "ANALYTICS_SCRIPT" in st.secrets:
        website_id_match = re.search(r'data-website-id="([^"]+)"', st.secrets.ANALYTICS_SCRIPT)
        website_id = website_id_match.group(1) if website_id_match else ""

        script = f"""
        <script>
            if (!parent.document.querySelector('script[data-website-id="{website_id}"]')) {{
                var script = parent.document.createElement('script');
                script.defer = true;
                script.src = 'https://analytics.sprintjudicial.com/script.js';
                script.setAttribute('data-website-id', '{website_id}');
                parent.document.head.appendChild(script);
            }}
        </script>
        """
        components.html(script, height=0)

# =============================================
# APPLICATION IDENTITY DICTIONARY
# =============================================
# Todos los elementos específicos de identidad del proyecto están centralizados aquí
# Modifique este diccionario para cambiar la identidad de la aplicación

APP_IDENTITY = {
    # Identidad principal
    "name": "DocAssemble Expert",
    "version": "1.0.0",
    "icon": "🤖",
    "tagline": "Asistente Especializado en YAML Interviews",
    "full_title": "¡Bienvenido a DocAssemble Expert! 🤖",
    # Información del desarrollador original
    "developer": "Alexander Oviedo Fadul",
    "github_url": "https://github.com/bladealex9848",
    "website_url": "https://alexanderoviedofadul.dev/",
    "docs_url": "https://docassemble.org/docs.html",
    "linkedin_url": "https://www.linkedin.com/in/alexander-oviedo-fadul/",
    "instagram_url": "https://www.instagram.com/alexander.oviedo.fadul",
    "twitter_url": "https://twitter.com/alexanderofadul",
    "facebook_url": "https://www.facebook.com/alexanderof/",
    "whatsapp_url": "https://api.whatsapp.com/send?phone=573015930519&text=Hola%20!Quiero%20conversar%20contigo!%20",
    "repository_url": "https://github.com/bladealex9848/DocAssembleExpert",
    # Información del adaptador del fork
    "fork_developer": "Daniel Arbeláez",
    "fork_github_url": "https://github.com/HammerDev99",
    "fork_website_url": "https://portfolio.sprintjudicial.com/",
    "fork_linkedin_url": "https://www.linkedin.com/in/daniel-arbelaez-/",
    "fork_email": "daniel.arbelaez.alvarez@gmail.com",
    # Descripción de la aplicación - formas corta y larga
    "short_description": "Tu asistente especializado en Docassemble para crear interviews automatizadas usando YAML.",
    "long_description": """
    ### 🤖 ¡Hola! Soy DocAssemble Expert

    **DocAssemble Expert** es un asistente de IA especializado en **Docassemble**, el framework open-source para crear entrevistas web interactivas usando YAML. Estoy diseñado para ayudar a desarrolladores, abogados y organizaciones a crear interviews automatizadas de manera eficiente y con las mejores prácticas.

    #### ¿Qué puedo hacer por ti hoy? 🚀

    * **📝 Escritura de Question Blocks**: Crear question blocks correctos con fields, validation, help text
    * **🔄 Flujos de Interview**: Diseñar lógica condicional avanzada y navigation patterns
    * **🎯 Variables y Objetos**: Configurar Individual, DAList, DADict y relaciones entre entidades
    * **📄 Generación de Documentos**: Crear templates DOCX/PDF y attachments complejos
    * **🔧 Debugging**: Identificar y resolver errores de sintaxis YAML y lógica
    * **🌐 Multi-idioma**: Configurar interviews multilingües con language modifiers
    * **⚡ Optimización**: Sugerir mejores prácticas para performance
    * **📊 Tablas y Datos**: Crear table blocks dinámicos y exports
    * **🎨 UI/UX**: Implementar navigation bars, progress bars y CSS custom
    * **🔗 APIs**: Configurar external data sources y background tasks

    **¡No dudes en consultarme sobre desarrollo de interviews en Docassemble!**

    *Nota: Proporciono código YAML, ejemplos prácticos y mejores prácticas basadas en la documentación oficial de Docassemble.*
    """,
    # User instructions
    "usage_instructions": """
    1. **Desarrollo de Interviews**: Describe tu caso de uso y te ayudaré a crear el código YAML necesario.

    2. **Debugging de Código**: Comparte tu código YAML y mensajes de error para identificar y resolver problemas.

    3. **Mejores Prácticas**: Pregunta sobre patterns recomendados, optimización y arquitectura de interviews.

    4. **Documentación y Templates**: Solicita ejemplos de attachments, document assembly y generación de PDFs.

    5. **Integración y APIs**: Consulta sobre conexión con servicios externos, background tasks y data sources.

    6. **Casos de Uso Específicos**: Describe tu proyecto (formularios legales, workflows, automatización) para soluciones personalizadas.
    """,
    # Document processing information
    "document_processing_info": """
    Esta aplicación puede procesar:

    - Archivos YAML de Docassemble para análisis y debugging
    - Templates DOCX/PDF para document assembly
    - Código Python para custom functions y modules
    - Archivos de configuración y packages
    - Documentación y especificaciones de proyectos

    **Nota sobre privacidad**: Los documentos se procesan localmente y no se almacenan permanentemente.

    **Formatos soportados**: YAML (.yml, .yaml), PDF (.pdf), Texto (.txt), Imágenes (.jpg, .jpeg, .png), DOCX (.docx).
    """,
    # Texto de la interfaz de usuario
    "chat_placeholder": "¿Cómo puedo ayudarte con Docassemble hoy?",
    "file_upload_default_message": "He cargado el archivo '{files}' para análisis. Por favor, analiza su contenido y proporciona feedback sobre el código YAML o la estructura del documento.",
    "badges": """
    ![Visitantes](https://api.visitorbadge.io/api/visitors?path=https%3A%2F%2Fdocassembleexpert.streamlit.app&label=Visitantes&labelColor=%235d5d5d&countColor=%231e7ebf&style=flat)
    """,
    # Welcome message (displayed on first load)
    "welcome_message": """
    ### 🤖 ¡Bienvenido a DocAssemble Expert!

    Soy tu asistente especializado en **Docassemble**, el framework open-source para crear entrevistas web interactivas usando YAML.

    Puedo ayudarte con:
    * **Question blocks** con fields, validation y help text
    * **Lógica condicional** y flow control avanzado
    * **Objetos y variables** (Individual, DAList, DADict)
    * **Document assembly** con templates DOCX/PDF
    * **Debugging** de errores YAML y lógica
    * **Multi-idioma** y localization
    * **Integración con APIs** y external data
    * **UI/UX personalización** con CSS y JavaScript

    **¿En qué aspecto de Docassemble puedo ayudarte hoy?**

    Puedes empezar con:
    - "Crea un question block para recolectar información de contacto"
    - "¿Cómo implemento lógica condicional basada en respuestas?"
    - "Necesito generar un PDF con datos del interview"
    - "Mi código YAML tiene un error, ¿puedes ayudarme?"
    """,
    # Mensajes de error y configuración
    "api_key_missing": "Por favor, proporciona una clave API para continuar.",
    "conversation_started": "Sistema experto inicializado correctamente",
    "response_error": "No se pudo obtener respuesta. Por favor, intente de nuevo.",
    "config_success": "✅ Configuración completa",
    "config_warning": "⚠️ Falta configurar: {missing_items}",
    "config_needed": "❌ **Configuración incompleta**: {app_name} necesita que configures `OPENAI_API_KEY` y `MISTRAL_API_KEY` en el archivo `.streamlit/secrets.toml` o como variables de entorno.",
    # Configuración del menú
    "menu_items": {
        "Get Help": "https://docassemble.org/docs.html",
        "Report a bug": None,
        "About": "DocAssemble Expert: Asistente especializado en desarrollo de interviews automatizadas con YAML",
    },
    # Footer text
    "footer_text": """
    **Desarrollador Original:**
    {developer}
    [GitHub]({github_url}) | [Website]({website_url}) | [LinkedIn]({linkedin_url}) | [Instagram]({instagram_url}) | [Twitter]({twitter_url}) | [Facebook]({facebook_url}) | [WhatsApp]({whatsapp_url})

    **Adaptador del Fork:**
    {fork_developer} - Legal Tech Developer 🚀
    [GitHub]({fork_github_url}) | [Portafolio]({fork_website_url}) | [LinkedIn]({fork_linkedin_url}) | [Email](mailto:{fork_email})
    """,
    # Log configuration
    "log_name": "docassemble_expert",
    # Document naming (for exports and files)
    "document_prefix": "docassemble_expert",
    "conversation_export_name": "docassemble_expert_conversacion",
    # Mensajes sobre formatos de archivo
    "allowed_formats_message": "Formatos permitidos: YAML (.yml, .yaml), PDF (.pdf), Texto (.txt), Imágenes (.jpg, .jpeg, .png)",
}

# Configuración avanzada de logging - Implementación multi-destino
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(
    log_dir, f"{APP_IDENTITY['log_name']}_{datetime.now().strftime('%Y%m%d')}.log"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - "
    + APP_IDENTITY["log_name"]
    + " - %(levelname)s [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_file)],
)

# Versión de la aplicación
APP_VERSION = APP_IDENTITY["version"]

# Configuración de página Streamlit
st.set_page_config(
    page_title=APP_IDENTITY["full_title"],
    page_icon=APP_IDENTITY["icon"],
    layout="wide",
    initial_sidebar_state="collapsed",  # Menú lateral contraído por defecto
    menu_items=APP_IDENTITY["menu_items"],
)

inject_analytics()


# Decorador para manejo de errores con retries
def handle_error(max_retries=2):
    """
    Decorador avanzado para manejo de errores con capacidad de reintento

    Parámetros:
        max_retries: Número máximo de reintentos ante fallos
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            last_exception = None

            while retries <= max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_msg = f"Error en {func.__name__} (intento {retries+1}/{max_retries+1}): {str(e)}"
                    logging.error(error_msg)

                    if retries < max_retries:
                        logging.info(f"Reintentando {func.__name__}...")
                        retries += 1
                        time.sleep(1)  # Espera antes de reintentar
                    else:
                        logging.error(
                            f"Error final después de {max_retries+1} intentos: {traceback.format_exc()}"
                        )
                        st.error(error_msg)
                        break

            return None

        return wrapper

    return decorator


# Sistema multicapa para reinicio de la aplicación
def rerun_app():
    """
    Sistema multicapa para reiniciar la aplicación Streamlit.
    Implementa múltiples estrategias de recuperación en caso de fallo.
    """
    try:
        # Método 1 (preferido): Función actual en Streamlit
        st.rerun()
    except (AttributeError, Exception) as e:
        logging.warning(f"Método primario de reinicio falló: {str(e)}")

        # Método 2: Mensaje al usuario con opción manual
        st.info("Por favor, recarga la página para ver los cambios")

        # Método 3: Intento con JavaScript nativo
        try:
            html_code = """
            <script>
                // Reintento con un retraso para permitir renderización
                setTimeout(function() {
                    window.parent.location.reload();
                }, 2000);
            </script>
            """
            st.components.v1.html(html_code, height=0, width=0)
        except Exception as e3:
            logging.error(f"Reinicio con JavaScript falló: {str(e3)}")


# Detectar entorno de ejecución
def is_streamlit_cloud():
    """
    Detecta si la aplicación se está ejecutando en Streamlit Cloud
    con verificación multi-indicador
    """
    try:
        # Múltiples indicadores para una detección más robusta
        indicators = [
            os.environ.get("STREAMLIT_SHARING_MODE") is not None,
            os.environ.get("STREAMLIT_SERVER_BASE_URL_IS_SET") is not None,
            os.environ.get("IS_STREAMLIT_CLOUD") == "true",
            os.path.exists("/.streamlit/config.toml"),
            "STREAMLIT_RUNTIME" in os.environ,
        ]

        # Si al menos dos indicadores son positivos, consideramos que es Cloud
        return sum(indicators) >= 2
    except Exception as e:
        logging.warning(f"Error al detectar entorno: {str(e)}")
        return False


# Lectura unificada de configuración: variables de entorno primero, luego secrets.toml
def get_setting(name, default=None):
    """
    Obtiene un valor de configuración desde variables de entorno o st.secrets.
    """
    value = os.environ.get(name)
    if value not in (None, ""):
        return value
    try:
        if hasattr(st, "secrets") and name in st.secrets:
            return st.secrets[name]
    except Exception as e:  # secrets.toml ausente o ilegible
        logging.debug(f"No se pudo leer st.secrets[{name}]: {str(e)}")
    return default


# Crear cliente OpenAI (Responses API). Se cachea por API Key para no
# reconstruirlo ni verificar conectividad en cada rerun de Streamlit.
@st.cache_resource(show_spinner=False)
def _build_openai_client(api_key):
    client = OpenAI(api_key=api_key, timeout=120.0, max_retries=2)
    # Verificar credenciales con una llamada liviana
    client.models.list()
    logging.info("Cliente OpenAI inicializado correctamente")
    return client


def create_openai_client(api_key):
    """
    Devuelve un cliente OpenAI verificado o None si no fue posible conectar.
    """
    try:
        return _build_openai_client(api_key)
    except Exception as e:
        logging.error(f"Error inicializando cliente OpenAI: {str(e)}")
        st.error(f"No se pudo conectar a OpenAI: {friendly_error_message(e)}")
        return None


# Sistema multicapa para exportación de conversaciones
def export_chat_to_pdf(messages):
    """
    Sistema multicapa para exportación de conversaciones a PDF.
    Implementa múltiples estrategias de generación con manejo de fallos.
    """
    try:
        # Método 1 (preferido): FPDF con manejo mejorado
        return _export_chat_to_pdf_primary(messages)
    except Exception as e:
        logging.warning(f"Método primario de exportación a PDF falló: {str(e)}")
        try:
            # Método 2: ReportLab como alternativa
            return _export_chat_to_pdf_secondary(messages)
        except Exception as e2:
            logging.warning(f"Método secundario de exportación a PDF falló: {str(e2)}")
            try:
                # Método 3: Conversión simple como último recurso
                return _export_chat_to_pdf_fallback(messages)
            except Exception as e3:
                logging.error(
                    f"Todos los métodos de exportación a PDF fallaron: {str(e3)}"
                )
                # Último recurso: Devolver contenido en markdown codificado
                md_content = export_chat_to_markdown(messages)
                st.warning(
                    "No fue posible generar un PDF. Se ha creado un archivo markdown en su lugar."
                )
                return base64.b64encode(md_content.encode()).decode(), "markdown"


def _export_chat_to_pdf_primary(messages):
    """
    Método primario: FPDF optimizado con manejo de errores mejorado
    y división inteligente de texto para evitar problemas de espacio
    """
    from fpdf import FPDF
    import re

    class CustomPDF(FPDF):
        def header(self):
            self.set_font("helvetica", "B", 12)
            self.cell(
                0,
                10,
                f'{APP_IDENTITY["name"]} - Historial de Conversación',
                0,
                new_y="NEXT",
                align="C",
            )
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font("helvetica", "I", 8)
            self.cell(0, 10, f"Página {self.page_no()}", 0, 0, "C")

        def add_message(self, role, content):
            # Añadir título del mensaje
            self.set_font("helvetica", "B", 11)
            self.cell(0, 10, role, 0, new_y="NEXT", align="L")
            self.ln(2)

            # Añadir contenido con procesamiento seguro
            self.set_font("helvetica", "", 10)
            self._safe_add_content(content)
            self.ln(5)

        def _safe_add_content(self, content):
            # Procesar markdown básico
            content = self._process_markdown(content)

            # Dividir en párrafos
            paragraphs = content.split("\n\n")

            for paragraph in paragraphs:
                if not paragraph.strip():
                    self.ln(5)
                    continue

                # Dividir párrafos largos en líneas seguras
                lines = self._safe_wrap_text(paragraph, max_width=180)

                for line in lines:
                    if not line.strip():
                        continue

                    if line.startswith("- ") or line.startswith("* "):
                        # Elemento de lista
                        self.cell(5, 10, "", 0, 0)
                        self.cell(5, 10, "•", 0, 0)
                        self._safe_multi_cell(0, 10, line[2:])
                    else:
                        # Párrafo normal
                        self._safe_multi_cell(0, 10, line)

                # Espacio entre párrafos
                self.ln(2)

        def _process_markdown(self, text):
            # Simplificar encabezados
            text = re.sub(r"^#{1,6}\s+(.*?)$", r"\1", text, flags=re.MULTILINE)

            # Eliminar elementos multimedia
            text = re.sub(r"!\[.*?\]\(.*?\)", "[IMAGEN]", text)

            # Simplificar enlaces
            text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)

            return text

        def _safe_wrap_text(self, text, max_width=180):
            """Divide texto en líneas seguras para renderizar"""
            lines = []
            for raw_line in text.split("\n"):
                if len(raw_line) < max_width:
                    lines.append(raw_line)
                    continue

                # Dividir líneas largas en palabras
                words = raw_line.split(" ")
                current_line = ""

                for word in words:
                    test_line = current_line + " " + word if current_line else word

                    if len(test_line) <= max_width:
                        current_line = test_line
                    else:
                        lines.append(current_line)
                        current_line = word

                if current_line:
                    lines.append(current_line)

            return lines

        def _safe_multi_cell(self, w, h, txt, border=0, align="J", fill=False):
            """Versión segura de multi_cell con manejo de errores integrado"""
            try:
                # Eliminar caracteres no ASCII si es necesario
                if not all(ord(c) < 128 for c in txt):
                    txt = "".join(c if ord(c) < 128 else "?" for c in txt)

                # Limitar longitud de línea si es necesario
                if len(txt) > 200:
                    chunks = [txt[i : i + 200] for i in range(0, len(txt), 200)]
                    for chunk in chunks:
                        self.multi_cell(w, h, chunk, border, align, fill)
                else:
                    self.multi_cell(w, h, txt, border, align, fill)
            except Exception as e:
                logging.warning(
                    f"Error en multi_cell: {str(e)}. Intentando versión simplificada."
                )
                # Versión de respaldo extremadamente simplificada
                safe_txt = "".join(c for c in txt if c.isalnum() or c in " .,;:-?!()")
                self.multi_cell(w, h, safe_txt[:100] + "...", border, align, fill)

    # Crear el PDF
    pdf = CustomPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Añadir fecha
    pdf.set_font("helvetica", "I", 10)
    pdf.cell(
        0, 10, f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 0, new_y="NEXT"
    )
    pdf.ln(5)

    # Añadir mensajes
    for msg in messages:
        role = "Usuario" if msg["role"] == "user" else APP_IDENTITY["name"]
        pdf.add_message(role, msg["content"])

    # Generar PDF
    output = io.BytesIO()
    pdf.output(output)
    return output.getvalue(), "pdf"


def _export_chat_to_pdf_secondary(messages):
    """
    Método secundario: ReportLab para generación alternativa de PDF
    con manejo mejorado de texto extenso
    """
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors

    # Crear buffer y documento
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72,
    )

    # Configurar estilos
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Title",
            fontName="Helvetica-Bold",
            fontSize=14,
            alignment=1,
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="User",
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=colors.blue,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Assistant",
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=colors.green,
            spaceAfter=6,
        )
    )

    # Elementos del documento
    elements = []

    # Título y fecha
    elements.append(
        Paragraph(
            f"{APP_IDENTITY['name']} - Historial de Conversación", styles["Title"]
        )
    )
    elements.append(Spacer(1, 0.25 * inch))
    elements.append(
        Paragraph(
            f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Italic"]
        )
    )
    elements.append(Spacer(1, 0.25 * inch))

    # Función de seguridad para procesar texto
    def safe_process_text(text, max_chunk=2000):
        # Escapar caracteres especiales HTML
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # Convertir newlines a <br/>
        text = text.replace("\n", "<br/>")

        # Dividir texto muy largo en secciones manejables
        if len(text) > max_chunk:
            chunks = []
            for i in range(0, len(text), max_chunk):
                chunks.append(text[i : i + max_chunk])
            return chunks
        return [text]

    # Procesar mensajes
    for msg in messages:
        role = "Usuario" if msg["role"] == "user" else APP_IDENTITY["name"]
        style = styles["User"] if msg["role"] == "user" else styles["Assistant"]

        # Título del mensaje
        elements.append(Paragraph(role, style))

        # Contenido procesado en porciones seguras
        content_chunks = safe_process_text(msg["content"])
        for i, chunk in enumerate(content_chunks):
            try:
                elements.append(Paragraph(chunk, styles["Normal"]))
                if i < len(content_chunks) - 1:
                    elements.append(Spacer(1, 0.1 * inch))
            except Exception as e:
                logging.warning(f"Error al procesar chunk {i}: {str(e)}")
                # Versión ultra simplificada como respaldo
                elements.append(
                    Paragraph(
                        "[Contenido simplificado debido a error de formato]",
                        styles["Normal"],
                    )
                )

        elements.append(Spacer(1, 0.2 * inch))

    # Generar documento con manejo de errores
    try:
        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data, "pdf"
    except Exception as e:
        logging.error(f"Error en ReportLab: {str(e)}")
        raise e


def _export_chat_to_pdf_fallback(messages):
    """
    Método de último recurso: PDF simple sin formato avanzado
    diseñado para máxima compatibilidad y robustez
    """
    from fpdf import FPDF

    # PDF básico con manejo mínimo
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)

    # Título
    pdf.set_font("helvetica", style="B", size=16)
    pdf.cell(
        200,
        10,
        f"{APP_IDENTITY['name']} - Historial de Conversación",
        ln=True,
        align="C",
    )
    pdf.ln(5)

    # Fecha
    pdf.set_font("helvetica", style="I", size=10)
    pdf.cell(200, 10, f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.ln(10)

    # Mensajes - formato mínimo con máxima seguridad
    pdf.set_font("helvetica", size=11)
    for msg in messages:
        role = "Usuario" if msg["role"] == "user" else APP_IDENTITY["name"]

        # Encabezado del mensaje
        pdf.set_font("helvetica", style="B", size=12)
        pdf.cell(200, 10, role, ln=True)
        pdf.ln(2)

        # Contenido ultra-simple, sin formato
        pdf.set_font("helvetica", size=10)

        # Extraer texto plano con máxima seguridad
        simple_text = "".join(c if ord(c) < 128 else "?" for c in msg["content"])
        simple_text = simple_text.replace("\n", " ").replace("\r", "")

        # Dividir texto en líneas muy cortas para evitar errores
        line_length = 50  # Longitud muy conservadora
        for i in range(0, len(simple_text), line_length):
            chunk = simple_text[i : i + line_length]
            try:
                pdf.cell(0, 10, chunk, ln=True)
            except:
                # Si falla incluso con texto simplificado, usar solo alfanuméricos
                ultra_safe = "".join(c for c in chunk if c.isalnum() or c == " ")
                try:
                    pdf.cell(0, 10, ultra_safe, ln=True)
                except:
                    # Abandonar este chunk si todo falla
                    pass

        pdf.ln(10)

    # Generar PDF
    try:
        output = io.BytesIO()
        pdf.output(output)
        return output.getvalue(), "pdf"
    except Exception as e:
        logging.error(f"Error incluso en fallback: {str(e)}")
        raise e


def export_chat_to_markdown(messages):
    """
    Exporta el historial de chat a formato markdown
    con mejoras de formato y legibilidad
    """
    md_content = f"# {APP_IDENTITY['name']} - Historial de Conversación\n\n"
    md_content += f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    for msg in messages:
        role = "Usuario" if msg["role"] == "user" else APP_IDENTITY["name"]
        md_content += f"## {role}\n\n{msg['content']}\n\n"
        md_content += "---\n\n"  # Separador para mejorar legibilidad

    return md_content


# Definición de formatos permitidos y sus extensiones
ALLOWED_FILE_FORMATS = {
    "YAML": [".yml", ".yaml"],
    "PDF": [".pdf"],
    "Imagen": [".jpg", ".jpeg", ".png"],
    "Texto": [".txt"],
}

# Lista plana de todas las extensiones permitidas
ALLOWED_EXTENSIONS = [ext for exts in ALLOWED_FILE_FORMATS.values() for ext in exts]


# Funciones de OCR con Mistral
@handle_error(max_retries=1)
def validate_file_format(file):
    """
    Valida que el archivo tenga un formato permitido y que su contenido
    sea consistente con la extensión declarada.

    Parámetros:
        file: Objeto de archivo cargado por el usuario mediante Streamlit

    Retorno:
        tuple: (es_válido, tipo_documento, mensaje_error)
    """
    file_type = None

    # Verificar que el archivo tenga nombre
    if not hasattr(file, "name"):
        return False, None, "El archivo no tiene nombre"

    # Obtener extensión y verificar que esté permitida
    file_name = file.name.lower()
    file_ext = os.path.splitext(file_name)[1]

    if file_ext not in ALLOWED_EXTENSIONS:
        allowed_exts = ", ".join(ALLOWED_EXTENSIONS)
        return False, None, f"Formato de archivo no permitido. Use: {allowed_exts}"

    # Determinar el tipo de documento según la extensión
    for doc_type, extensions in ALLOWED_FILE_FORMATS.items():
        if file_ext in extensions:
            file_type = doc_type
            break

    # Verificar contenido según el tipo de archivo
    try:
        # Guardar posición del cursor
        position = file.tell()

        # Verificar contenido según tipo
        if file_type == "PDF":
            # Verificar firma de PDF
            header = file.read(8)
            file.seek(position)  # Restaurar posición

            if not header.startswith(b"%PDF"):
                return False, None, "El archivo no es un PDF válido"

        elif file_type == "Imagen":
            # Intentar abrir como imagen
            try:
                img = Image.open(file)
                img.verify()  # Verificar que la imagen sea válida
                file.seek(position)  # Restaurar posición
            except Exception as e:
                file.seek(position)  # Restaurar posición
                return False, None, f"El archivo no es una imagen válida: {str(e)}"

        elif file_type == "YAML":
            # Verificar que sea YAML válido
            try:
                import yaml
                content = file.read()
                yaml.safe_load(content)
                file.seek(position)  # Restaurar posición
            except Exception as e:
                file.seek(position)  # Restaurar posición
                return False, None, f"El archivo no es YAML válido: {str(e)}"

    except Exception as e:
        # Restaurar posición en caso de error
        try:
            file.seek(position)
        except:
            pass
        return False, None, f"Error validando el archivo: {str(e)}"

    # Si llegamos aquí, el archivo es válido
    return True, file_type, None


@handle_error(max_retries=1)
def detect_document_type(file):
    """
    Detecta automáticamente si un archivo es un PDF, imagen o YAML
    con múltiples verificaciones para mayor precisión

    Parámetros:
        file: Objeto de archivo cargado por el usuario mediante Streamlit

    Retorno:
        string: Tipo de documento detectado ("PDF", "Imagen", "YAML", "Texto")
    """
    # 1. Verificar por MIME type
    if hasattr(file, "type"):
        mime_type = file.type
        if mime_type.startswith("application/pdf"):
            return "PDF"
        elif mime_type.startswith("image/"):
            return "Imagen"
        elif mime_type in ["text/yaml", "application/x-yaml"]:
            return "YAML"

    # 2. Verificar por extensión del nombre
    if hasattr(file, "name"):
        name = file.name.lower()
        if name.endswith(".pdf"):
            return "PDF"
        elif name.endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp")):
            return "Imagen"
        elif name.endswith((".yml", ".yaml")):
            return "YAML"
        elif name.endswith(".txt"):
            return "Texto"

    # 3. Verificar contenido con análisis de bytes
    try:
        # Guardar posición del cursor
        position = file.tell()
        # Leer los primeros bytes
        header = file.read(8)
        file.seek(position)  # Restaurar posición

        # Verificar firmas de archivo comunes
        if header.startswith(b"%PDF"):
            return "PDF"
        elif header.startswith(b"\x89PNG") or header.startswith(b"\xff\xd8"):
            return "Imagen"
    except:
        pass

    # 4. Intentar abrir como imagen (último recurso)
    try:
        Image.open(file)
        file.seek(0)  # Restaurar el puntero
        return "Imagen"
    except:
        file.seek(0)  # Restaurar el puntero

    # Asumir Texto por defecto
    return "Texto"


@handle_error(max_retries=1)
def prepare_image_for_ocr(file_data):
    """
    Prepara una imagen para ser procesada con OCR,
    optimizando formato y calidad para mejorar resultados

    Parámetros:
        file_data: Datos binarios de la imagen

    Retorno:
        tuple: (datos_optimizados, mime_type)
    """
    try:
        # Abrir la imagen con PIL
        img = Image.open(BytesIO(file_data))

        # Optimizaciones avanzadas para OCR
        # 1. Convertir a escala de grises si tiene más de un canal
        if img.mode != "L" and img.mode != "1":
            img = img.convert("L")

        # 2. Ajustar tamaño si es muy grande (límite 4000px)
        max_dimension = 4000
        if img.width > max_dimension or img.height > max_dimension:
            ratio = min(max_dimension / img.width, max_dimension / img.height)
            new_width = int(img.width * ratio)
            new_height = int(img.height * ratio)
            img = img.resize((new_width, new_height), Image.LANCZOS)

        # 3. Evaluar y determinar mejor formato
        # JPEG para imágenes fotográficas, PNG para documentos/texto
        save_format = "JPEG"
        save_quality = 95

        # Detectar si es más probable que sea un documento (blanco/negro predominante)
        histogram = img.histogram()
        if img.mode == "L" and (histogram[0] + histogram[-1]) > sum(histogram) * 0.8:
            save_format = "PNG"

        # 4. Guardar con parámetros optimizados
        buffer = BytesIO()
        if save_format == "JPEG":
            img.save(buffer, format=save_format, quality=save_quality, optimize=True)
        else:
            img.save(buffer, format=save_format, optimize=True)

        buffer.seek(0)
        return buffer.read(), f"image/{save_format.lower()}"

    except Exception as e:
        logging.warning(f"Optimización de imagen fallida: {str(e)}")
        return file_data, "image/jpeg"  # Formato por defecto


@handle_error(max_retries=1)
def extract_text_from_ocr_response(response):
    """
    Extrae texto de diferentes formatos de respuesta OCR
    con soporte para múltiples estructuras de datos

    Parámetros:
        response: Respuesta JSON del servicio OCR

    Retorno:
        dict: Diccionario con el texto extraído
    """
    # Registro para diagnóstico
    logging.info(f"Procesando respuesta OCR de tipo: {type(response)}")

    # Caso 1: Si hay páginas con markdown (formato preferido)
    if "pages" in response and isinstance(response["pages"], list):
        pages = response["pages"]
        if pages and "markdown" in pages[0]:
            markdown_text = "\n\n".join(page.get("markdown", "") for page in pages)
            if markdown_text.strip():
                return {"text": markdown_text, "format": "markdown"}

    # Caso 2: Si hay un texto plano en la respuesta
    if "text" in response:
        return {"text": response["text"], "format": "text"}

    # Caso 3: Si hay elementos estructurados
    if "elements" in response:
        elements = response["elements"]
        if isinstance(elements, list):
            text_parts = []
            for element in elements:
                if "text" in element:
                    text_parts.append(element["text"])
            return {"text": "\n".join(text_parts), "format": "elements"}

    # Caso 4: Si hay un campo 'content' principal
    if "content" in response:
        return {"text": response["content"], "format": "content"}

    # Caso 5: Extracción recursiva de todos los campos de texto
    try:
        response_str = json.dumps(response, indent=2)
        # Si la respuesta es muy grande, limitar extracción
        if len(response_str) > 10000:
            response_str = response_str[:10000] + "... [truncado]"

        extracted_text = extract_all_text_fields(response)
        if extracted_text:
            return {"text": extracted_text, "format": "extracted"}

        return {
            "text": "No se pudo encontrar texto estructurado en la respuesta OCR. Vea los detalles técnicos.",
            "format": "unknown",
            "raw_response": response_str,
        }
    except Exception as e:
        logging.error(f"Error al procesar respuesta OCR: {str(e)}")
        return {"error": f"Error al procesar la respuesta: {str(e)}"}


@handle_error(max_retries=0)
def extract_all_text_fields(data, prefix="", max_depth=5, current_depth=0):
    """
    Función recursiva optimizada para extraer todos los campos de texto
    de un diccionario anidado con límites de profundidad

    Parámetros:
        data: Diccionario o lista de datos
        prefix: Prefijo para la ruta de acceso (uso recursivo)
        max_depth: Profundidad máxima de recursión
        current_depth: Profundidad actual (uso recursivo)

    Retorno:
        string: Texto extraído
    """
    # Evitar recursión infinita
    if current_depth > max_depth:
        return []

    result = []

    if isinstance(data, dict):
        for key, value in data.items():
            new_prefix = f"{prefix}.{key}" if prefix else key

            if isinstance(value, str) and len(value) > 1:
                result.append(f"{new_prefix}: {value}")
            elif (
                isinstance(value, (dict, list)) and value
            ):  # Solo recursión si hay contenido
                child_results = extract_all_text_fields(
                    value, new_prefix, max_depth, current_depth + 1
                )
                result.extend(child_results)

    elif isinstance(data, list):
        # Limitar número de elementos procesados en listas muy grandes
        max_items = 20
        for i, item in enumerate(data[:max_items]):
            new_prefix = f"{prefix}[{i}]"
            if isinstance(item, (dict, list)) and item:
                child_results = extract_all_text_fields(
                    item, new_prefix, max_depth, current_depth + 1
                )
                result.extend(child_results)
            elif isinstance(item, str) and len(item) > 1:
                result.append(f"{new_prefix}: {item}")

        # Indicar si se truncó la lista
        if len(data) > max_items:
            result.append(
                f"{prefix}: [... {len(data) - max_items} elementos adicionales omitidos]"
            )

    return "\n".join(result)


@handle_error(max_retries=1)
def process_document_with_mistral_ocr(api_key, file_bytes, file_type, file_name):
    """
    Procesa un documento con OCR de Mistral
    con sistema de recuperación ante fallos

    Parámetros:
        api_key: API key de Mistral
        file_bytes: Bytes del archivo
        file_type: Tipo de archivo ("PDF", "Imagen", "Texto", "YAML")
        file_name: Nombre del archivo

    Retorno:
        dict: Texto extraído del documento
    """
    job_id = str(uuid.uuid4())
    logging.info(f"Procesando documento {file_name} con Mistral OCR (ID: {job_id})")

    # Mostrar estado
    with st.status(f"Procesando documento {file_name}...", expanded=True) as status:
        try:
            status.update(label="Preparando documento para OCR...", state="running")

            # Para archivos YAML, extraer contenido directamente
            if file_type == "YAML":
                try:
                    import yaml
                    yaml_content = file_bytes.decode("utf-8")
                    # Validar que sea YAML válido
                    yaml.safe_load(yaml_content)
                    return {"text": yaml_content, "format": "yaml"}
                except Exception as e:
                    # Si falla la validación YAML, intentar como texto
                    logging.warning(f"Error procesando YAML, tratando como texto: {str(e)}")
                    file_type = "Texto"

            # Guardar una copia del archivo para depuración
            debug_dir = os.path.join(
                tempfile.gettempdir(), f"{APP_IDENTITY['document_prefix']}_debug"
            )
            os.makedirs(debug_dir, exist_ok=True)
            debug_file_path = os.path.join(debug_dir, f"debug_{job_id}_{file_name}")

            with open(debug_file_path, "wb") as f:
                f.write(file_bytes)

            logging.info(f"Archivo de depuración guardado en: {debug_file_path}")

            # Sistema de procesamiento con verificación según tipo
            if file_type == "PDF":
                # Verificar que el PDF sea válido
                try:
                    import PyPDF2

                    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                    page_count = len(reader.pages)
                    sample_text = ""
                    if page_count > 0:
                        sample_text = reader.pages[0].extract_text()[:100]
                    logging.info(
                        f"PDF válido con {page_count} páginas. Muestra: {sample_text}"
                    )

                    # Codificar PDF en base64
                    encoded_file = base64.b64encode(file_bytes).decode("utf-8")
                    document = {
                        "type": "document_url",
                        "document_url": f"data:application/pdf;base64,{encoded_file}",
                    }
                except Exception as e:
                    logging.error(f"Error al validar PDF: {str(e)}")
                    status.update(
                        label=f"Error al validar PDF: {str(e)}", state="error"
                    )
                    return {"error": f"El archivo no es un PDF válido: {str(e)}"}
            elif file_type == "Imagen":
                # Optimizar imagen para mejores resultados
                try:
                    optimized_bytes, mime_type = prepare_image_for_ocr(file_bytes)

                    # Codificar en base64
                    encoded_file = base64.b64encode(optimized_bytes).decode("utf-8")
                    document = {
                        "type": "image_url",
                        "image_url": f"data:{mime_type};base64,{encoded_file}",
                    }
                except Exception as e:
                    logging.error(f"Error al procesar imagen: {str(e)}")
                    status.update(
                        label=f"Error al procesar imagen: {str(e)}", state="error"
                    )
                    return {"error": f"El archivo no es una imagen válida: {str(e)}"}
            elif file_type == "Texto":
                # Para archivos de texto, extraer contenido directamente
                try:
                    # Intentar leer con diferentes codificaciones
                    try:
                        text_content = file_bytes.decode("utf-8")
                        return {"text": text_content, "format": "text"}
                    except UnicodeDecodeError:
                        # Intentar con otras codificaciones comunes
                        for encoding in ["latin-1", "cp1252", "iso-8859-1"]:
                            try:
                                text_content = file_bytes.decode(encoding)
                                return {"text": text_content, "format": "text"}
                            except UnicodeDecodeError:
                                continue

                    # Si llegamos aquí, no pudimos decodificar el texto
                    # Intentar enviar como documento plano
                    status.update(
                        label=f"Convirtiendo documento de texto {file_name} para OCR...",
                        state="running",
                    )

                    # Codificar en base64 y enviar como documento
                    encoded_file = base64.b64encode(file_bytes).decode("utf-8")
                    document = {
                        "type": "document_url",
                        "document_url": f"data:text/plain;base64,{encoded_file}",
                    }
                except Exception as e:
                    logging.error(f"Error al procesar documento de texto: {str(e)}")
                    status.update(
                        label=f"Error al procesar documento: {str(e)}", state="error"
                    )
                    return {"error": f"Error al procesar documento de texto: {str(e)}"}
            else:
                # Tipo de documento no soportado
                error_msg = f"Tipo de documento no soportado: {file_type}"
                logging.error(error_msg)
                status.update(label=error_msg, state="error")
                return {"error": error_msg}

            status.update(
                label="Enviando documento a la API de Mistral...", state="running"
            )

            # Configurar los headers
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }

            # Preparar payload
            payload = {"model": "mistral-ocr-latest", "document": document}

            # Guardar payload para depuración (excluyendo contenido base64 por tamaño)
            debug_payload = {
                "model": payload["model"],
                "document": {
                    "type": payload["document"]["type"],
                    "content_size": len(encoded_file),
                    "content_format": "base64",
                },
            }
            logging.info(f"Payload para OCR: {json.dumps(debug_payload)}")

            # Sistema de retry interno para la API de Mistral
            max_retries = 2
            retry_delay = 2
            last_error = None

            for retry in range(max_retries + 1):
                try:
                    # Hacer la solicitud a Mistral OCR API
                    response = requests.post(
                        "https://api.mistral.ai/v1/ocr",
                        json=payload,
                        headers=headers,
                        timeout=90,  # Timeout ampliado para documentos grandes
                    )

                    logging.info(
                        f"Respuesta de OCR API - Estado: {response.status_code}"
                    )

                    if response.status_code == 200:
                        try:
                            result = response.json()
                            # Guardar respuesta para depuración
                            with open(
                                os.path.join(
                                    debug_dir, f"response_{job_id}_{file_name}.json"
                                ),
                                "w",
                            ) as f:
                                json.dump(result, f, indent=2)

                            status.update(
                                label=f"Documento {file_name} procesado exitosamente",
                                state="complete",
                            )

                            # Verificar existencia de contenido
                            if not result or (isinstance(result, dict) and not result):
                                return {
                                    "error": "La API no devolvió contenido",
                                    "raw_response": str(result),
                                }

                            # Extraer texto de la respuesta
                            extracted_content = extract_text_from_ocr_response(result)

                            if "error" in extracted_content:
                                status.update(
                                    label=f"Error al extraer texto: {extracted_content['error']}",
                                    state="error",
                                )
                                return {
                                    "error": extracted_content["error"],
                                    "raw_response": result,
                                }

                            return extracted_content
                        except Exception as e:
                            error_message = (
                                f"Error al procesar respuesta JSON: {str(e)}"
                            )
                            logging.error(error_message)
                            # Guardar respuesta cruda para depuración
                            with open(
                                os.path.join(
                                    debug_dir, f"raw_response_{job_id}_{file_name}.txt"
                                ),
                                "w",
                            ) as f:
                                f.write(response.text[:10000])  # Limitar tamaño
                            status.update(label=error_message, state="error")
                            last_error = e
                    elif response.status_code == 429:  # Rate limit
                        if retry < max_retries:
                            wait_time = retry_delay * (retry + 1)
                            logging.warning(
                                f"Rate limit alcanzado. Esperando {wait_time}s antes de reintentar..."
                            )
                            status.update(
                                label=f"Límite de tasa alcanzado. Reintentando en {wait_time}s...",
                                state="running",
                            )
                            time.sleep(wait_time)
                            continue
                        else:
                            error_message = "Límite de tasa alcanzado. No se pudo procesar después de reintentos."
                            logging.error(error_message)
                            status.update(label=error_message, state="error")
                            return {
                                "error": error_message,
                                "raw_response": response.text,
                            }
                    else:
                        error_message = f"Error en API OCR ({response.status_code}): {response.text[:500]}"
                        logging.error(error_message)
                        status.update(label=f"Error: {error_message}", state="error")
                        last_error = Exception(error_message)
                        break
                except requests.exceptions.Timeout:
                    if retry < max_retries:
                        wait_time = retry_delay * (retry + 1)
                        logging.warning(
                            f"Timeout al contactar API. Esperando {wait_time}s antes de reintentar..."
                        )
                        status.update(
                            label=f"Timeout. Reintentando en {wait_time}s...",
                            state="running",
                        )
                        time.sleep(wait_time)
                    else:
                        error_message = (
                            "Timeout al contactar API después de múltiples intentos."
                        )
                        logging.error(error_message)
                        status.update(label=error_message, state="error")
                        return {"error": error_message}
                except Exception as e:
                    if retry < max_retries:
                        wait_time = retry_delay * (retry + 1)
                        logging.warning(
                            f"Error: {str(e)}. Esperando {wait_time}s antes de reintentar..."
                        )
                        status.update(
                            label=f"Error. Reintentando en {wait_time}s...",
                            state="running",
                        )
                        time.sleep(wait_time)
                    else:
                        error_message = f"Error al procesar documento: {str(e)}"
                        logging.error(error_message)
                        status.update(label=f"Error: {error_message}", state="error")
                        last_error = e
                        break

            # Si llegamos aquí después de reintentos, devolver último error
            return {
                "error": f"Error después de reintentos: {str(last_error)}",
                "details": traceback.format_exc(),
            }

        except Exception as e:
            error_message = f"Error general al procesar documento: {str(e)}"
            logging.error(error_message)
            logging.error(traceback.format_exc())
            status.update(label=f"Error: {error_message}", state="error")
            return {"error": error_message}


# Función segura para gestionar el contexto de documentos
@handle_error(max_retries=0)
def manage_document_context():
    """
    Permite al usuario gestionar qué documentos mantener en el contexto actual
    con manejo seguro de actualización de estado
    """
    if "document_contents" in st.session_state and st.session_state.document_contents:
        st.write("Documentos en contexto actual:")

        # Crear checkboxes para cada documento
        docs_to_keep = {}
        for doc_name in st.session_state.document_contents:
            docs_to_keep[doc_name] = st.checkbox(
                f"{doc_name}", value=True, key=f"keep_{doc_name}"
            )

        # Botón para aplicar cambios
        if st.button("Actualizar contexto", key="update_context"):
            # Eliminar documentos no seleccionados
            docs_to_remove = [doc for doc, keep in docs_to_keep.items() if not keep]
            if docs_to_remove:
                for doc in docs_to_remove:
                    if doc in st.session_state.document_contents:
                        del st.session_state.document_contents[doc]
                    if doc in st.session_state.uploaded_files:
                        st.session_state.uploaded_files.remove(doc)

                st.success(
                    f"Se eliminaron {len(docs_to_remove)} documentos del contexto."
                )
                # Usar sistema seguro de reinicio
                rerun_app()
            else:
                st.info("No se seleccionaron documentos para eliminar.")
    else:
        st.info("No hay documentos cargados en el contexto actual.")


# Perfil del asistente (reemplaza al objeto Assistant que vivía en OpenAI)
@st.cache_resource(show_spinner=False)
def build_assistant_profile():
    """
    Construye la configuración del asistente desde env/secrets:
    OPENAI_MODEL, ASSISTANT_INSTRUCTIONS, VECTOR_STORE_ID, OPENAI_TEMPERATURE, etc.
    """
    profile = load_profile(get_setting, name=APP_IDENTITY["name"])
    logging.info(
        f"Perfil del asistente: modelo={profile.model}, "
        f"base_conocimiento={'sí' if profile.has_knowledge_base else 'no'}, "
        f"historial_max={profile.max_history_messages}"
    )
    return profile


# Inicializar la conversación local (sustituye a client.beta.threads.create)
def initialize_conversation():
    """
    Crea un identificador local de conversación. El historial se guarda en
    st.session_state.api_history y se envía completo en cada llamada.
    """
    conversation_id = f"docassembleexpert-{uuid.uuid4().hex}"
    logging.info(f"Conversación local creada: {conversation_id}")
    return conversation_id


def _session_file_names():
    """Mapa file_id -> nombre, para citas de file_search (compatibilidad)."""
    metadata = st.session_state.get("file_metadata") or {}
    names = {}
    for file_id, meta in metadata.items():
        if isinstance(meta, dict) and meta.get("name"):
            names[file_id] = meta["name"]
    return names


# Función para generar la respuesta del asistente con contexto de documentos
def generate_assistant_reply(client, profile, user_text):
    """
    Envía el turno a la Responses API con el historial de la sesión y el
    contexto de documentos, mostrando la respuesta en streaming.

    Devuelve un dict {"role": "assistant", "content": ..., "id": ...} o None.
    """
    chat = ResponsesChat(client, profile)
    history = st.session_state.get("api_history", [])
    document_context = build_document_context(
        st.session_state.get("document_contents", {}), profile.max_doc_chars
    )
    if document_context:
        logging.info(
            f"Contexto con {len(st.session_state.document_contents)} documentos. "
            f"Tamaño: {len(document_context)} caracteres"
        )

    with st.chat_message("assistant"):
        status = st.status(
            "Analizando consulta y procesando información...", expanded=False
        )
        placeholder = st.empty()
        streamed = []

        def on_status(label):
            status.update(label=label, state="running")

        try:
            for delta in chat.stream_reply(
                history,
                user_text,
                document_context=document_context,
                cache_key=st.session_state.get("conversation_id"),
                on_status=on_status,
                file_names=_session_file_names(),
            ):
                streamed.append(delta)
                placeholder.markdown(clean_streaming_text("".join(streamed)) + "▌")
            reply = chat.last_reply
        except Exception as e:
            logging.error(f"Error en comunicación con OpenAI: {str(e)}")
            logging.error(traceback.format_exc())
            status.update(label="Error en el procesamiento", state="error")
            placeholder.empty()
            st.error(friendly_error_message(e))
            return None

        if reply is None or not reply.content.strip():
            status.update(label="Sin respuesta del modelo", state="error")
            placeholder.empty()
            st.error(APP_IDENTITY["response_error"])
            return None

        status.update(label="Análisis completado", state="complete")
        placeholder.markdown(reply.content)

    # Historial para la API: texto limpio, sin marcadores ni referencias
    st.session_state.api_history.append({"role": "user", "content": user_text})
    st.session_state.api_history.append({"role": "assistant", "content": reply.text})
    st.session_state.last_response_id = reply.response_id

    return {"role": "assistant", "content": reply.content, "id": reply.response_id}


# Función para limpiar la sesión actual
@handle_error(max_retries=0)
def clean_current_session():
    """
    Limpia todos los recursos de la sesión actual
    con verificación de resultados
    """
    try:
        resources_cleaned = {
            "documents": 0,
            "messages": (
                len(st.session_state.messages) if "messages" in st.session_state else 0
            ),
        }

        # Limpiar documentos procesados
        if "document_contents" in st.session_state:
            resources_cleaned["documents"] = len(st.session_state.document_contents)
            st.session_state.document_contents = {}

        # Limpiar lista de archivos
        if "uploaded_files" in st.session_state:
            st.session_state.uploaded_files = []

        # Limpiar historial de mensajes
        if "messages" in st.session_state:
            st.session_state.messages = []
        st.session_state.api_history = []
        st.session_state.last_response_id = None

        # Limpiar otros estados relacionados con documentos
        for key in ["file_metadata"]:
            if key in st.session_state:
                st.session_state[key] = {}

        # Verificar limpieza exitosa
        clean_success = True
        if (
            "document_contents" in st.session_state
            and st.session_state.document_contents
        ):
            clean_success = False
        if "messages" in st.session_state and st.session_state.messages:
            clean_success = False

        if clean_success:
            logging.info(
                f"Sesión limpiada exitosamente: {resources_cleaned['documents']} documentos, {resources_cleaned['messages']} mensajes"
            )
        else:
            logging.warning(
                "Limpieza de sesión incompleta - algunos elementos persistieron"
            )

        return resources_cleaned
    except Exception as e:
        logging.error(f"Error limpiando sesión: {str(e)}")
        return {"documents": 0, "messages": 0, "error": str(e)}


# ----- INICIALIZACIÓN DE INTERFAZ -----

# Título principal
st.title(f"{APP_IDENTITY['name']} {APP_IDENTITY['icon']} {APP_IDENTITY['tagline']}")

# Barra lateral con toda la información e instrucciones
with st.sidebar:
    st.title(f"{APP_IDENTITY['icon']} Configuración y Recursos")

    # Obtener API Key de OpenAI (env -> secrets.toml -> usuario)
    openai_api_key = get_setting("OPENAI_API_KEY")
    if not openai_api_key:
        openai_api_key = st.text_input(
            "API Key de OpenAI", type="password", help="Ingrese su API Key de OpenAI"
        )

    # Obtener API Key de Mistral (env -> secrets.toml -> usuario)
    mistral_api_key = get_setting("MISTRAL_API_KEY")
    if not mistral_api_key:
        mistral_api_key = st.text_input(
            "API Key de Mistral",
            type="password",
            help="Ingrese su API Key de Mistral para OCR",
        )

    # Perfil del asistente: modelo, instrucciones y base de conocimiento.
    # Ya no se requiere ASSISTANT_ID: la configuración vive en el código/secrets.
    assistant_profile = build_assistant_profile()

    # Verificar configuración
    if openai_api_key and mistral_api_key:
        st.success(APP_IDENTITY["config_success"])
    else:
        missing = []
        if not openai_api_key:
            missing.append("API Key de OpenAI")
        if not mistral_api_key:
            missing.append("API Key de Mistral")
        st.warning(
            APP_IDENTITY["config_warning"].format(missing_items=", ".join(missing))
        )

    st.caption(
        f"Modelo: `{assistant_profile.model}` · Base de conocimiento: "
        f"{'activa' if assistant_profile.has_knowledge_base else 'no configurada'}"
    )

    # Mostrar entorno
    env_type = "Streamlit Cloud" if is_streamlit_cloud() else "Local"
    st.info(f"Entorno detectado: {env_type}")

    # Opciones de exportación de chat
    st.subheader("💾 Exportar Conversación")
    export_format = st.radio("Formato de exportación:", ("Markdown",))

    if st.button("Descargar conversación"):
        if "messages" in st.session_state and st.session_state.messages:
            if export_format == "Markdown":
                md_content = export_chat_to_markdown(st.session_state.messages)
                b64 = base64.b64encode(md_content.encode()).decode()
                href = f'<a href="data:text/markdown;base64,{b64}" download="{APP_IDENTITY["conversation_export_name"]}.md">Descargar archivo Markdown</a>'
                st.markdown(href, unsafe_allow_html=True)
        else:
            st.warning("No hay conversación para exportar.")

    # Administrador de contexto de documentos
    st.subheader("📄 Gestión de Documentos")
    manage_document_context()

    # Botón para limpiar la sesión actual
    if st.button(
        "🧹 Limpiar sesión actual",
        type="secondary",
        help="Elimina todos los archivos y datos de la sesión actual",
    ):
        with st.spinner("Limpiando recursos de la sesión..."):
            result = clean_current_session()
            if isinstance(result, dict) and "error" not in result:
                st.success(
                    f"Sesión limpiada: {result['documents']} documentos, {result['messages']} mensajes"
                )
            else:
                st.error("No se pudo limpiar la sesión completamente")
            rerun_app()

    # Documentos cargados
    if "uploaded_files" in st.session_state and st.session_state.uploaded_files:
        st.subheader("📚 Documentos disponibles")
        for idx, filename in enumerate(st.session_state.uploaded_files):
            st.markdown(f"📄 **{filename}**")

        st.info("Estos documentos están disponibles para consulta en la conversación.")

    # Enlaces a recursos de Docassemble
    st.markdown("---")
    st.subheader("📋 Recursos de Docassemble")
    
    # Crear botones para los recursos principales
    if st.button("📚 Documentación Principal", key="docs_main"):
        st.markdown("[Acceder](https://docassemble.org/docs.html)")
    
    if st.button("🌍 Tutorial Hello World", key="tutorial_hello"):
        st.markdown("[Acceder](https://docassemble.org/docs/helloworld.html)")
    
    if st.button("🎮 Playground Interactivo", key="playground"):
        st.markdown("[Acceder](https://docassemble.org/docs/playground.html)")
    
    if st.button("📖 Ejemplos y Recipes", key="recipes"):
        st.markdown("[Acceder](https://docassemble.org/docs/recipes.html)")
    
    if st.button("⚖️ Legal Module", key="legal_module"):
        st.markdown("[Acceder](https://docassemble.org/docs/legal.html)")
    
    if st.button("📝 Document Assembly", key="doc_assembly"):
        st.markdown("[Acceder](https://docassemble.org/docs/documents.html)")
    
    if st.button("🔌 API Documentation", key="api_docs"):
        st.markdown("[Acceder](https://docassemble.org/docs/api.html)")
    
    if st.button("💬 Slack Community", key="slack"):
        st.markdown("[Únete a docassemble.slack.com](https://docassemble.slack.com)")

    # Área informativa
    st.markdown("---")
    st.subheader(f"{APP_IDENTITY['icon']} Sobre {APP_IDENTITY['name']}")
    st.markdown(APP_IDENTITY["long_description"])

    # Añadir información de uso
    st.markdown("---")
    st.subheader("💡 Cómo usar " + APP_IDENTITY["name"])
    st.markdown(APP_IDENTITY["usage_instructions"])

    # Instrucciones para documentos
    st.markdown("---")
    st.subheader("📄 Procesamiento de documentos")
    st.info(APP_IDENTITY["document_processing_info"])
    st.caption(APP_IDENTITY["allowed_formats_message"])

    # Footer en la barra lateral
    st.markdown("---")
    st.subheader("Desarrollado por:")
    st.markdown(
        APP_IDENTITY["footer_text"].format(
            developer=APP_IDENTITY["developer"],
            github_url=APP_IDENTITY["github_url"],
            website_url=APP_IDENTITY["website_url"],
            linkedin_url=APP_IDENTITY["linkedin_url"],
            instagram_url=APP_IDENTITY["instagram_url"],
            twitter_url=APP_IDENTITY["twitter_url"],
            facebook_url=APP_IDENTITY["facebook_url"],
            whatsapp_url=APP_IDENTITY["whatsapp_url"],
            fork_developer=APP_IDENTITY["fork_developer"],
            fork_github_url=APP_IDENTITY["fork_github_url"],
            fork_website_url=APP_IDENTITY["fork_website_url"],
            fork_linkedin_url=APP_IDENTITY["fork_linkedin_url"],
            fork_email=APP_IDENTITY["fork_email"],
        ),
        unsafe_allow_html=True,
    )

# Detener si no tenemos la configuración completa
if not openai_api_key or not mistral_api_key:
    st.markdown(APP_IDENTITY["config_needed"].format(app_name=APP_IDENTITY["name"]))
    st.stop()

# ----- INICIALIZACIÓN DE ESTADO -----

# Inicializar variables de estado
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

# Historial que se envía a la Responses API (solo texto user/assistant)
if "api_history" not in st.session_state:
    st.session_state.api_history = []

if "last_response_id" not in st.session_state:
    st.session_state.last_response_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []

if "document_contents" not in st.session_state:
    st.session_state.document_contents = {}

if "file_metadata" not in st.session_state:
    st.session_state.file_metadata = {}

# Crear clientes
openai_client = create_openai_client(openai_api_key)

# Inicializar conversación local si no existe (ya no hay threads en OpenAI)
if not st.session_state.conversation_id and openai_client:
    st.session_state.conversation_id = initialize_conversation()
    st.success(
        f"{APP_IDENTITY['icon']} {APP_IDENTITY['conversation_started']} {APP_IDENTITY['icon']}"
    )

# ----- INTERFAZ DE CHAT -----

# Contenedor de historial de chat - mostrar mensajes previos
chat_history_container = st.container()

with chat_history_container:
    # Mostrar mensajes previos
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Mostrar mensaje de bienvenida si no hay mensajes
    if not st.session_state.messages:
        with st.chat_message("assistant"):
            st.markdown(APP_IDENTITY["welcome_message"])

# Chat input con soporte nativo para adjuntar archivos
# Extraer extensiones sin el punto para el parámetro file_type
file_types = [ext[1:] for ext in ALLOWED_EXTENSIONS]  # Quitar el punto inicial

# Mostrar mensaje sobre formatos permitidos
st.caption(APP_IDENTITY["allowed_formats_message"])

# Input de chat con soporte para archivos
prompt = st.chat_input(
    APP_IDENTITY["chat_placeholder"],
)

# Procesar la entrada del usuario
if prompt:
    # Mostrar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Procesar la respuesta usando OpenAI
    if st.session_state.conversation_id and openai_client:
        try:
            # Enviar mensaje y obtener respuesta
            response = generate_assistant_reply(
                openai_client, assistant_profile, prompt
            )

            if response:
                # Añadir respuesta al historial
                st.session_state.messages.append(response)
        except Exception as e:
            st.error(f"Error al procesar la respuesta: {str(e)}")
            logging.error(f"Error procesando respuesta: {traceback.format_exc()}")
    else:
        st.error("Error: Sistema no inicializado correctamente.")
