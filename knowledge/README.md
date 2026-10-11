# Base de conocimiento de DocAssemble Expert

Esta carpeta alimenta el **vector store** de OpenAI que usa la herramienta `file_search`
de la Responses API. Es el reemplazo de la base de conocimiento que tenía el antiguo
Assistant y que desapareció con el retiro de la Assistants API.

## Contenido

| Archivo | Se versiona | Descripción |
|---|---|---|
| `docassembleexpert_base_conocimiento.md` | Sí | Base de conocimiento compilada a partir de la información del proyecto (alcance funcional, glosario, perfiles de usuario, limitaciones y documentos oficiales de referencia). |
| Manuales y formatos oficiales (`.pdf`, `.docx`, `.xlsx` exportado a `.csv` o `.md`, etc.) | **No** (ignorados por git) | Documentos que se obtienen por los canales institucionales de la Rama Judicial. Cópielos aquí antes de ejecutar el script; nunca se suben al repositorio público. |

## Corpus de entrevistas del Suffolk LIT Lab (`suffolk/`)

`scripts/cosechar_suffolk.py` descarga los paquetes públicos `docassemble-*` del Suffolk LIT Lab
(cuentas de GitHub `SuffolkLITLab`, `mplp`, `masslegalhelp`, `LemmaLegalConsulting` y `LSVermont`, las mismas entrevistas del Document
Assembly Line que se instalan en apps-dev.suffolklitlab.org) y genera:

- `suffolk/_catalogo.md`: índice por área (familia, vivienda, laboral, penal...) con el equivalente
  orientativo en la jurisdicción colombiana.
- `suffolk/paquetes/<repo>.md`: un archivo por paquete con metadata, README, YAML completo, módulos
  Python, el texto de las plantillas DOCX (con sus etiquetas Jinja) y los campos de las plantillas PDF.

Solo se copian repositorios con licencia declarada (casi todos MIT); los demás quedan listados en el
catálogo. La carpeta está ignorada por git: se regenera con el script, y los clones se guardan en
`.cache/suffolk/`.

```bash
python3 scripts/cosechar_suffolk.py --solo-listar   # ver qué se descargaría
python3 scripts/cosechar_suffolk.py                 # clonar/actualizar y generar el Markdown
python3 scripts/crear_vector_store.py --vector-store-id vs_xxx --sincronizar --dry-run   # revisar antes de actualizar
```

## Actualización desde GitHub Actions

El flujo **Actualizar base de conocimiento** (`.github/workflows/actualizar-conocimiento.yml`) hace la cosecha y la
sincronización con `--sincronizar` desde la pestaña Actions > Run workflow. Requiere los secretos del
repositorio `OPENAI_API_KEY` y `VECTOR_STORE_ID`. La opción "simular" muestra los cambios sin aplicarlos.
Por defecto no poda: si un repositorio de origen desaparece, su paquete se conserva en el vector store. La casilla
"podar" (`--podar`) solo borra paquetes cosechados (`docassemble-*.md`) que ya no se encuentran, y se detiene si
serían más del 10 %.

## Crear o actualizar el vector store

Antes de crear uno nuevo, revise en el panel de OpenAI (Storage > Vector stores) si el vector store
del antiguo Assistant sigue existiendo: los vector stores **no** se eliminaron con el retiro de la
Assistants API y conservan los manuales ya indexados. En ese caso use `--vector-store-id` con su ID.


```bash
python3 scripts/crear_vector_store.py --dry-run     # lista los archivos que se subirían
python3 scripts/crear_vector_store.py               # crea un vector store nuevo y sube los archivos
python3 scripts/crear_vector_store.py --vector-store-id vs_xxx   # agrega archivos a uno existente
python3 scripts/crear_vector_store.py --vector-store-id vs_xxx --sincronizar   # solo lo nuevo o modificado
```

El script imprime el identificador `vs_...`. Cópielo en `.streamlit/secrets.toml` (o en los
secrets de Streamlit Cloud) como:

```toml
VECTOR_STORE_ID = "vs_..."
```

Requiere `OPENAI_API_KEY` en el entorno o en `.streamlit/secrets.toml`. Formatos admitidos por
`file_search`: `.pdf`, `.md`, `.txt`, `.docx`, `.pptx`, `.html`, `.json`, `.csv`.
