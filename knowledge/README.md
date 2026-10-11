# Base de conocimiento de DocAssemble Expert

Esta carpeta alimenta el **vector store** de OpenAI que usa la herramienta `file_search`
de la Responses API. Es el reemplazo de la base de conocimiento que tenía el antiguo
Assistant y que desapareció con el retiro de la Assistants API.

## Contenido

| Archivo | Se versiona | Descripción |
|---|---|---|
| `docassembleexpert_base_conocimiento.md` | Sí | Base de conocimiento compilada a partir de la información del proyecto (alcance funcional, glosario, perfiles de usuario, limitaciones y documentos oficiales de referencia). |
| Manuales y formatos oficiales (`.pdf`, `.docx`, `.xlsx` exportado a `.csv` o `.md`, etc.) | **No** (ignorados por git) | Documentos que se obtienen por los canales institucionales de la Rama Judicial. Cópielos aquí antes de ejecutar el script; nunca se suben al repositorio público. |

## Crear o actualizar el vector store

Antes de crear uno nuevo, revise en el panel de OpenAI (Storage > Vector stores) si el vector store
del antiguo Assistant sigue existiendo: los vector stores **no** se eliminaron con el retiro de la
Assistants API y conservan los manuales ya indexados. En ese caso use `--vector-store-id` con su ID.


```bash
python3 scripts/crear_vector_store.py --dry-run     # lista los archivos que se subirían
python3 scripts/crear_vector_store.py               # crea un vector store nuevo y sube los archivos
python3 scripts/crear_vector_store.py --vector-store-id vs_xxx   # agrega archivos a uno existente
```

El script imprime el identificador `vs_...`. Cópielo en `.streamlit/secrets.toml` (o en los
secrets de Streamlit Cloud) como:

```toml
VECTOR_STORE_ID = "vs_..."
```

Requiere `OPENAI_API_KEY` en el entorno o en `.streamlit/secrets.toml`. Formatos admitidos por
`file_search`: `.pdf`, `.md`, `.txt`, `.docx`, `.pptx`, `.html`, `.json`, `.csv`.
