# DocAssemble Expert: base de conocimiento compilada

Documento compilado a partir de la documentación del proyecto (README e identidad de la aplicación). Complementa los documentos oficiales que se indexan en el vector store.

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

---

## ⚠️ Limitaciones

El asistente **NO puede**:

- **Ejecutar código YAML en tiempo real** - No tiene acceso a un servidor Docassemble para probar código
- **Acceder a archivos del servidor** - No puede ver logs, debugging info en vivo, o archivos específicos del usuario
- **Hacer deployment automático** - No puede instalar packages o configurar servidores
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
