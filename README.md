# 🤖 DocAssemble Expert - Asistente Especializado en YAML Interviews

## 📋 Introducción

**DocAssemble Expert** es un asistente de IA especializado en **Docassemble**, el framework open-source para crear entrevistas web interactivas usando YAML. Este asistente está diseñado para ayudar a desarrolladores, abogados y organizaciones a crear interviews automatizadas de manera eficiente y con las mejores prácticas.

Docassemble permite automatizar procesos legales complejos, crear documentos inteligentes y proporcionar acceso a la justicia a través de interfaces web intuitivas. Este asistente domina completamente la sintaxis YAML específica de Docassemble, sus objetos incorporados, funciones especiales y patrones de diseño recomendados.

El asistente combina conocimiento técnico profundo con experiencia práctica en el desarrollo de interviews, desde casos simples hasta implementaciones empresariales complejas con lógica condicional avanzada, integración de APIs y generación de documentos multiparte.

---

## 🚀 Funcionalidades del Asistente

### 1. **📝 Escritura de Question Blocks YAML**
Ayuda a crear question blocks correctos con todos los elementos necesarios: question, fields, validation, help text y lógica condicional.

**Ejemplo de uso:**
```yaml
---
question: |
  ¿Cuál es su información de contacto?
fields:
  - Nombre completo: client_name
    datatype: text
    required: True
  - Email: client_email  
    datatype: email
    validation messages:
      email: "Por favor ingrese un email válido"
  - Teléfono: client_phone
    datatype: text
    required: False
---
```

### 2. **🔄 Diseño de Flujos de Interview Complejos**
Crea lógica condicional avanzada, event handling, y navigation patterns para interviews multi-etapa con ramificación inteligente.

**Ejemplo de uso:**
```yaml
---
mandatory: True
code: |
  if user.age >= 65:
    recommended_insurance = "Medicare"
  elif user.age < 18:
    if household.is_low_income:
      recommended_insurance = "CHIP"
    else:
      recommended_insurance = "parent coverage"
  else:
    recommended_insurance = "Private Insurance"
---
```

### 3. **🎯 Configuración de Variables y Objetos**
Guía en la definición correcta de variables, objetos Individual, grupos (DAList, DADict), y relaciones entre entidades.

**Ejemplo de uso:**
```yaml
---
objects:
  - client: Individual
  - opposing_parties: DAList.using(object_type=Individual)
  - case: Case
---
```

### 4. **📄 Generación de Documentos Automáticos**
Asiste en la creación de templates DOCX/PDF, attachments, y la integración de variables en documentos legales complejos.

**Ejemplo de uso:**
```yaml
---
attachment:
  name: Contrato de ${client.name.full()}
  filename: contrato_${client.name.last}
  docx template file: contrato_template.docx
  valid formats:
    - pdf
    - docx
---
```

### 5. **🔧 Debugging y Resolución de Errores**
Identifica problemas comunes en YAML, errores de sintaxis, variables no definidas, y problemas de lógica de interview.

**Casos comunes que resuelve:**
- Variables undefined causando errores de template
- Problemas de indentación YAML
- Loops infinitos en interview logic
- Conflictos de names/id en objetos

### 6. **🌐 Implementación de Multi-idioma**
Configura interviews multilingües usando language modifiers, translation files, y bloques condicionales por idioma.

**Ejemplo de uso:**
```yaml
---
language: es
question: |
  ¿Cuál es su nombre completo?
fields:
  - Nombre: user.name.first
  - Apellido: user.name.last
---
language: en  
question: |
  What is your full name?
fields:
  - First name: user.name.first
  - Last name: user.name.last
---
```

### 7. **⚡ Optimización de Performance**
Sugiere mejores prácticas para interviews eficientes: uso de depends on, reconsider, y gestión de memoria.

### 8. **📊 Integración de Tablas y Datos**
Crea table blocks dinámicos, exports a Excel/CSV, y visualización de datos complejos.

**Ejemplo de uso:**
```yaml
---
table: income_table
rows: income_sources
columns:
  - Fuente: row_item.source
  - Monto: currency(row_item.amount)
  - Frecuencia: row_item.frequency
edit:
  - source
  - amount
---
```

### 9. **🎨 Personalización de UI/UX**
Implementa features avanzadas como navigation bars, progress bars, CSS custom, y JavaScript integration.

### 10. **🔗 APIs y Integración Externa**
Configura external data sources, background tasks, y conexiones con servicios externos.

### 11. **⚖️ Entrevistas legales basadas en el Document Assembly Line**
La base de conocimiento incluye el código de 412 paquetes `docassemble-*` de código abierto del Suffolk LIT Lab
(Boston) y de organizaciones aliadas (Illinois Legal Aid Online, tribunales de Alaska, Greater Boston Legal Services,
Michigan Legal Help, Legal Services Vermont, entre otras): metadata, YAML, módulos Python, texto de plantillas DOCX
y campos de PDF. El asistente los usa como patrones probados para diseñar entrevistas colombianas de familia,
laboral, civil y penal, cita el paquete de referencia y sustituye normas, autoridades y formularios de EE. UU. por
los colombianos.

**Ejemplo de uso:**
> "Quiero una entrevista para solicitar una medida de protección por violencia intrafamiliar."
>
> El asistente toma como referencia `docassemble.MA209AProtectiveOrder`, explica su flujo y propone el YAML
> adaptado a la comisaría de familia (Ley 294 de 1996), con la lista de puntos que un abogado debe verificar.

---

## 🏗️ Arquitectura del proyecto

| Pieza | Archivo o servicio | Función |
|---|---|---|
| Interfaz | `app.py` (Streamlit) | Chat, carga de documentos con OCR (Mistral) y exportación |
| Motor del asistente | `docassembleexpert_openai.py` | Responses API de OpenAI con la herramienta `file_search` |
| Instrucciones | `prompts/docassembleexpert_instrucciones.md` | Comportamiento y reglas del asistente |
| Base de conocimiento | Vector store de OpenAI, alimentado desde `knowledge/` | Documentación del proyecto y corpus del Document Assembly Line |
| Cosecha del corpus | `scripts/cosechar_suffolk.py` | Descarga los paquetes públicos y los convierte en Markdown |
| Indexación | `scripts/crear_vector_store.py` | Crea el vector store o lo sincroniza (solo lo nuevo o modificado) |
| Actualización | GitHub Action **Actualizar base de conocimiento** | Cosecha, sincroniza y respalda el corpus a demanda |
| Respaldo | Repositorio privado del autor | Copia del corpus generado que nunca borra paquetes |
| Despliegue | Streamlit Community Cloud | Se redespliega solo con cada push a `main` |

El corpus generado no se versiona en este repositorio (`knowledge/*` y `.cache/` están en `.gitignore`): vive en el
vector store y en el respaldo privado. Detalle completo en [knowledge/README.md](knowledge/README.md).

### Ejecución local

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # completar OPENAI_API_KEY, MISTRAL_API_KEY y VECTOR_STORE_ID
streamlit run app.py
python3 -m pytest                                             # pruebas, sin red
```

`.streamlit/secrets.toml` está ignorado por git. Nunca escriba claves reales en `secrets.toml.example`, que sí se
versiona.

### Actualizar la base de conocimiento

Desde GitHub: pestaña **Actions** > **Actualizar base de conocimiento** > **Run workflow**.

| Opción | Efecto |
|---|---|
| (por defecto) | Cosecha los paquetes, sube al vector store solo lo nuevo o modificado y copia el corpus al respaldo privado |
| simular | Muestra qué cambiaría sin tocar el vector store ni el respaldo |
| podar | Borra del vector store los paquetes cuyo repositorio ya no existe (apagada por defecto, para conservarlos) |
| forzar poda | Permite que la poda supere el 10 % de los paquetes |

Secretos del repositorio (Settings > Secrets and variables > Actions): `OPENAI_API_KEY`, `VECTOR_STORE_ID` y
`CORPUS_DEPLOY_KEY` (llave de despliegue con escritura solo sobre el repositorio de respaldo). GitHub los oculta en
los registros y no los entrega a pull requests de forks. Las Actions no se ejecutan solas: se lanzan a mano.

Equivalente local:

```bash
python3 scripts/cosechar_suffolk.py
python3 scripts/crear_vector_store.py --vector-store-id vs_... --sincronizar --dry-run   # revisar
python3 scripts/crear_vector_store.py --vector-store-id vs_... --sincronizar
```

En macOS, algunos repositorios con archivos que solo difieren en mayúsculas generan una versión distinta a la de
GitHub Actions (Linux); por eso conviene sincronizar desde la Action.

---

## ⚠️ Limitaciones

El asistente **NO puede**:

- **Ejecutar código YAML en tiempo real** - No tiene acceso a un servidor Docassemble para probar código
- **Acceder a archivos del servidor** - No puede ver logs, debugging info en vivo, o archivos específicos del usuario
- **Hacer deployment automático** - No puede instalar packages o configurar servidores
- **Dar asesoría jurídica** - Las entrevistas adaptadas de Massachusetts deben validarse con la norma colombiana vigente y con un abogado
- **Debugging en tiempo real** - Requiere que el usuario proporcione el código YAML y mensajes de error específicos
- **Acceso a base de datos** - No puede consultar datos almacenados en interviews activos
- **Testing automático** - No puede ejecutar pruebas de interviews sin acceso al Playground

---

## 📋 Enlaces y Recursos Útiles

### 📚 Documentación Oficial
- **Documentación Principal:** https://docassemble.org/docs.html
- **Tutorial Hello World:** https://docassemble.org/docs/helloworld.html
- **Playground Interactivo:** https://docassemble.org/docs/playground.html
- **Ejemplos y Recipes:** https://docassemble.org/docs/recipes.html

### 🔧 Herramientas de Desarrollo
- **GitHub Oficial:** https://github.com/jhpyle/docassemble
- **Docker Installation:** https://docassemble.org/docs/docker.html
- **Package Management:** https://docassemble.org/docs/packages.html

### 🏛️ Recursos Legales
- **Legal Module:** https://docassemble.org/docs/legal.html
- **Document Assembly:** https://docassemble.org/docs/documents.html
- **API Documentation:** https://docassemble.org/docs/api.html

### ⚖️ Document Assembly Line (Suffolk LIT Lab)
- **Proyecto:** https://assemblyline.suffolklitlab.org/
- **Código fuente:** https://github.com/SuffolkLITLab
- **Formularios en producción:** https://courtformsonline.org

### 🌐 Comunidad y Soporte
- **Slack Community:** docassemble.slack.com
- **Support Resources:** https://docassemble.org/docs/support.html
- **Contributing Guide:** https://docassemble.org/docs/contributing.html

---

## 📊 Escenarios de Uso

### 👨‍💼 **Desarrollador de Software**
*"Necesito crear una interview compleja con múltiples ramificaciones y generación de PDF"*
- Ayuda con arquitectura de interview logic
- Optimización de performance y debugging
- Integración con APIs externas y databases

### ⚖️ **Abogado/Legal Professional**
*"Quiero automatizar formularios legales y generar documentos customizados"*
- Templates para documentos legales comunes
- Validación de datos específicos legales
- Workflows para casos típicos (divorcios, contratos, etc.)

### 🎓 **Estudiante/Aprendiz**
*"Estoy aprendiendo Docassemble y necesito entender los conceptos básicos"*
- Explicaciones paso a paso de sintaxis YAML
- Ejemplos graduales desde básico hasta avanzado
- Mejores prácticas y patrones comunes

### 🏢 **Organización Sin Fines de Lucro**
*"Queremos ofrecer acceso a la justicia mediante interviews automatizados"*
- Diseño de interviews accesibles y multi-idioma
- Optimización para usuarios no técnicos
- Deployment y mantenimiento simplificado

### 🏛️ **Institución Gubernamental**
*"Necesitamos digitalizar procesos burocráticos complejos"*
- Workflows de aprobación multi-nivel
- Integración con sistemas legacy
- Compliance y audit trails

---

## 👥 Contribuciones

### 🤝 Cómo Mejorar Este Asistente

**Reporta Problemas:**
- Identifica casos de uso no cubiertos
- Señala errores en ejemplos de código
- Sugiere nuevas funcionalidades

**Comparte Conocimiento:**
- Proporciona ejemplos de casos reales
- Documenta patterns y mejores prácticas
- Contribuye con templates y snippets

**Feedback Constructivo:**
- Evalúa la utilidad de las respuestas
- Sugiere mejoras en explicaciones
- Comparte experiencias de implementación

---

## 📝 Licencia

Este asistente se basa en la documentación oficial de **Docassemble**, la cual está disponible bajo licencia open-source. El framework Docassemble es desarrollado por Jonathan Pyle y la comunidad de contributors.

**Términos de Uso:**
- Utilización libre para propósitos educativos y comerciales
- Respeto a las licencias de dependencies y third-party libraries
- Reconocimiento apropiado al proyecto Docassemble original
- El corpus del Document Assembly Line no se distribuye en este repositorio; cada paquete conserva la licencia de su
  autor (en su mayoría MIT), indicada en el archivo generado y en el catálogo

---

## 🙏 Agradecimientos

**Reconocimiento Especial:**
- **Jonathan Pyle** - Creador y maintainer principal de Docassemble
- **Docassemble Community** - Contributors, testers, y usuarios activos
- **Suffolk LIT Lab y el Document Assembly Line** - Y las organizaciones aliadas que publican sus entrevistas con licencia abierta
- **Legal Technology Pioneers** - Por impulsar la democratización del acceso a la justicia
- **Open Source Community** - Por hacer posible herramientas como esta

---

## Autoría, licencia y aviso

- **Autor:** Daniel Arbeláez Álvarez. Construido a partir de una plantilla de otro autor ([perfil del autor de la plantilla](https://github.com/alexanderoviedofadul)), con equipo y cuentas propias, sin encargo ni instrucción de ninguna entidad o dependencia.
- **Inicio:** Primer commit: 24/09/2025 (hora de Colombia).
- **Licencia:** MIT, "Copyright (c) 2025 Daniel" (ver [LICENSE](LICENSE)).
- **Demo:** [docassemble-expert.streamlit.app](https://docassemble-expert.streamlit.app). La demo usa servicios de IA de terceros. No ingreses datos personales ni información de procesos reales.

*Herramienta personal de software libre, publicada a título personal. No representa a la Rama Judicial; su uso en un despacho requiere las autorizaciones institucionales que correspondan.*

## 👤 Autor

Desarrollado por [Daniel Arbeláez](https://github.com/HammerDev99) a partir de una plantilla de otro autor ([perfil del autor de la plantilla](https://github.com/alexanderoviedofadul)).

[GitHub](https://github.com/HammerDev99) | [Portafolio](https://portfolio.sprintjudicial.com/) | [LinkedIn](https://www.linkedin.com/in/daniel-arbelaez-/) | [Email](mailto:daniel.arbelaez.alvarez@gmail.com)

---

## 💼 Mensaje Final

Este asistente representa un paso hacia la **democratización de la tecnología legal**. Docassemble es una herramienta poderosa que puede transformar cómo las personas acceden a servicios legales y cómo los profesionales del derecho optimizan sus procesos.

**El valor de este asistente radica en:**

🎯 **Reducir la curva de aprendizaje** para nuevos usuarios de Docassemble

⚡ **Acelerar el desarrollo** de interviews complejos

🔍 **Proporcionar debugging experto** para resolver problemas técnicos

📚 **Ofrecer mejores prácticas** basadas en la documentación oficial completa

🌍 **Democratizar el acceso** a herramientas de automatización legal

**¡Comienza a crear interviews poderosos y accesibles hoy mismo!**