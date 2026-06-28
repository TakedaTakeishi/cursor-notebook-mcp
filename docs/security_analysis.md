# Análisis de Riesgos de Seguridad - cursor-notebook-mcp

**Propósito:** Documentar las herramientas, sus salidas y los riesgos potenciales de prompt injection antes de implementar sanitización.

**Fecha:** 2026-06-27
**Versión analizada:** 0.3.2 (fork con notebook_write mejorado)

---

## Contexto

El MCP (Model Context Protocol) conecta modelos de IA con herramientas externas. Cuando invoco una herramienta, el resultado se incluye en mi contexto. Si el resultado contiene texto que parece una instrucción, podría interpretarla como tal.

**Pregunta clave:** ¿Qué herramientas pueden producir salidas que contengan texto del usuario, de archivos, o de comandos externos que podrían incluir instrucciones maliciosas?

---

## Inventario de Herramientas (30 tools)

### Categoría 1: Operaciones de archivo (crear/eliminar/renombrar)

| Tool | Salida típica | Riesgo | Notas |
|---|---|---|---|
| `notebook_create` | "Successfully created new notebook: {path}" | 🟢 Bajo | Solo paths internos |
| `notebook_delete` | "Successfully deleted notebook: {path}" | 🟢 Bajo | Solo paths internos |
| `notebook_rename` | "Successfully renamed notebook from {old} to {new}" | 🟢 Bajo | Solo paths internos |

### Categoría 2: Lectura (read operations)

| Tool | Salida típica | Riesgo | Notas |
|---|---|---|---|
| `notebook_read` | Dict con el notebook completo (celdas + outputs) | 🟡 **Medio** | **Outputs pueden contener texto del usuario** |
| `notebook_read_cell` | String con el contenido de la celda | 🟡 **Medio** | **Contenido de celda = código del usuario** |
| `notebook_read_cell_output` | Lista de outputs (stream, display_data, error) | 🟡 **Medio** | **Outputs pueden ser muy largos** |
| `notebook_read_metadata` | Dict con metadata | 🟢 Bajo | No es user-controlled |
| `notebook_read_cell_metadata` | Dict con metadata de celda | 🟢 Bajo | No es user-controlled |
| `notebook_get_outline` | Lista de estructura | 🟢 Bajo | Solo marcadores, no contenido |
| `notebook_search` | Lista de resultados de búsqueda | 🟡 **Medio** | **Incluye snippets con contexto** |
| `notebook_get_info` | Dict con info del notebook | 🟢 Bajo | Metadata, no contenido |
| `notebook_get_cell_count` | Entero | 🟢 Bajo | Solo número |
| `notebook_validate` | String "Notebook is valid" o error | 🟢 Bajo | Mensaje fijo |

### Categoría 3: Escritura (modificación)

| Tool | Salida típica | Riesgo | Notas |
|---|---|---|---|
| `notebook_edit_cell` | "Successfully edited cell {i} in {path}" | 🟢 Bajo | Solo confirmación |
| `notebook_add_cell` | "Successfully added {type} cell at index {i}" | 🟢 Bajo | Solo confirmación |
| `notebook_delete_cell` | "Successfully deleted cell {i}" | 🟢 Bajo | Solo confirmación |
| `notebook_move_cell` | "Successfully moved cell" | 🟢 Bajo | Solo confirmación |
| `notebook_split_cell` | "Successfully split cell" | 🟢 Bajo | Solo confirmación |
| `notebook_merge_cells` | "Successfully merged cell" | 🟢 Bajo | Solo confirmación |
| `notebook_change_cell_type` | "Successfully changed cell type" | 🟢 Bajo | Solo confirmación |
| `notebook_duplicate_cell` | "Successfully duplicated cell" | 🟢 Bajo | Solo confirmación |
| `notebook_clear_cell_outputs` | "Successfully cleared outputs" | 🟢 Bajo | Solo confirmación |
| `notebook_clear_all_outputs` | "Successfully cleared outputs for {N} cells" | 🟢 Bajo | Solo confirmación |
| `notebook_edit_metadata` | "Successfully updated metadata" | 🟢 Bajo | Solo confirmación |
| `notebook_edit_cell_metadata` | "Successfully updated metadata for cell" | 🟢 Bajo | Solo confirmación |
| `notebook_edit_cell_output` | "Successfully edited/added outputs" | 🟢 Bajo | Solo confirmación |
| `notebook_bulk_add_cells` | "Successfully added {N} cells" | 🟢 Bajo | Solo confirmación |
| `notebook_write` | "Successfully wrote {N} cells to {path}" | 🟢 Bajo | Solo confirmación |

### Categoría 4: Ejecución externa (alto riesgo)

| Tool | Salida típica | Riesgo | Notas |
|---|---|---|---|
| `notebook_export` | Mensaje de éxito o error de nbconvert | 🔴 **Alto** | **Ejecuta `nbconvert`, captura stdout/stderr** |

### Categoría 5: Utilidades

| Tool | Salida típica | Riesgo | Notas |
|---|---|---|---|
| `notebook_get_server_path_context` | Dict con configuración del servidor | 🟢 Bajo | Solo paths internos |

---

## Análisis Detallado de Riesgos

### 🔴 Riesgo Alto: `notebook_export`

**Por qué es riesgoso:**
- Ejecuta un subproceso externo (`nbconvert`)
- Captura `stdout` y `stderr` del subproceso
- Estos pueden contener texto del usuario (por ejemplo, si el notebook tiene un print() con strings)
- Errores de nbconvert pueden contener tracebacks con código del usuario

**Ejemplo de salida potencialmente peligrosa:**
```
[IPKernelApp] WARNING | Kernel is running over TCP without encryption...
[NbConvertApp] Writing 89736 bytes to curso_takeishi\clases\clase_1.ipynb
```

Durante mi sesión, vi cómo outputs de `uv run nbconvert` contenían warnings y mensajes que parecían instrucciones.

### 🟡 Riesgo Medio: Tools de lectura con contenido del usuario

**Herramientas afectadas:**
- `notebook_read` (incluye todos los outputs)
- `notebook_read_cell` (incluye el source de la celda)
- `notebook_read_cell_output` (incluye outputs)
- `notebook_search` (incluye snippets con contexto)

**Por qué es riesgoso:**
- El usuario escribe código en las celdas (que puede incluir cualquier cosa)
- Los outputs pueden contener resultados de `print()`, errores, tracebacks
- Si un usuario (o un archivo) incluye texto malicioso en una celda, se propaga al contexto

**Pero también:**
- El usuario es el dueño de su código. No podemos "sanitizar" su código sin romper funcionalidad.
- El riesgo es legítimo solo si un atacante puede escribir en los notebooks.

### 🟢 Riesgo Bajo: Tools de escritura y utilidades

- Solo retornan confirmaciones con paths internos
- No incluyen contenido del usuario
- Paths son validados contra allowed_roots

---

## Recomendaciones (sin implementar todavía)

### Prioridad 1: Documentar

✅ **HECHO:** Este documento es la Prioridad 1.

### Prioridad 2: Truncar outputs de `notebook_export`

- Truncar `stdout`/`stderr` de nbconvert a un tamaño máximo (ej: 5000 caracteres)
- Sanitizar mensajes que parezcan instrucciones al modelo

### Prioridad 3: Límites de tamaño en outputs de lectura

- `notebook_read`: limitar el tamaño total del notebook devuelto
- `notebook_read_cell`: ya tiene límite de `max_cell_source_size`
- `notebook_read_cell_output`: ya tiene límite de `max_cell_output_size`

### Prioridad 4: NO sanitizar contenido del usuario

- El código del usuario en celdas NO debe sanitizarse
- Eso destruiría funcionalidad (ej: un print() legítimo con texto largo)
- El usuario es responsable de su código

---

## Próximos Pasos

1. **Crear tests** que verifiquen el comportamiento actual (baseline)
2. **Implementar truncado** en `notebook_export` (Prioridad 2)
3. **Ejecutar tests** para asegurar que nada se rompe
4. **Documentar** los cambios en el CHANGELOG.md
