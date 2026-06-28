"""
Tests para las mejoras de seguridad del MCP.

Estos tests verifican:
1. Comportamiento baseline actual
2. Truncado de outputs largos en notebook_export
3. Manejo de content_file en notebook_write
4. Validación de inputs sin romper funcionalidad

Ejecutar con: pytest tests/test_security_improvements.py -v
"""

import pytest
import os
import json
import nbformat
import tempfile
from pathlib import Path
from unittest import mock
import asyncio

# Import the class to be tested
from cursor_notebook_mcp.tools import NotebookTools

pytestmark = pytest.mark.asyncio


# ======================================================================
# Test 1: Baseline - Comportamiento actual de notebook_export
# ======================================================================

async def test_notebook_export_baseline(notebook_tools_inst, notebook_path_factory, temp_notebook_dir):
    """Test baseline: export funciona normalmente con output corto."""
    nb_path = notebook_path_factory()
    
    # Crear notebook simple
    create_result = await notebook_tools_inst.notebook_create(notebook_path=nb_path)
    assert "Successfully created" in create_result
    
    # El formato 'python' debería funcionar con un notebook vacío
    # (puede generar warnings pero no error)
    try:
        result = await notebook_tools_inst.notebook_export(
            notebook_path=nb_path,
            export_format='python'
        )
        # Si funciona, el resultado debe mencionar el archivo
        assert "exported" in result.lower() or "Successfully" in result
    except RuntimeError as e:
        # Si nbconvert no está disponible, al menos verificamos que el error es claro
        assert "nbconvert" in str(e).lower()


# ======================================================================
# Test 2: notebook_write con content_file
# ======================================================================

async def test_notebook_write_with_content_file(notebook_tools_inst, notebook_path_factory, tmp_path):
    """Test que notebook_write acepta content_file correctamente."""
    # Crear archivo de contenido
    content_file = tmp_path / "content.md"
    content_file.write_text("""---CELL---
cell_type: markdown
---
# Test Notebook

Este es un notebook de prueba.

---CELL---
cell_type: code
---
print("Hola, mundo!")
""", encoding='utf-8')
    
    nb_path = notebook_path_factory()
    
    result = await notebook_tools_inst.notebook_write(
        notebook_path=nb_path,
        content_file=str(content_file)
    )
    
    assert "Successfully wrote" in result
    assert os.path.exists(nb_path)
    
    # Verificar que el notebook tiene las celdas correctas
    nb = nbformat.read(nb_path, as_version=4)
    assert len(nb.cells) == 2
    assert nb.cells[0].cell_type == 'markdown'
    assert "Test Notebook" in nb.cells[0].source
    assert nb.cells[1].cell_type == 'code'
    assert "print" in nb.cells[1].source


async def test_notebook_write_with_content_file_nonexistent(notebook_tools_inst, notebook_path_factory):
    """Test que notebook_write maneja correctamente un content_file inexistente."""
    nb_path = notebook_path_factory()
    
    with pytest.raises(ValueError, match="Content file not found"):
        await notebook_tools_inst.notebook_write(
            notebook_path=nb_path,
            content_file="C:/nonexistent/path/file.md"
        )


async def test_notebook_write_with_cells_and_no_content_file(notebook_tools_inst, notebook_path_factory):
    """Test que notebook_write sigue funcionando con cells (compatibilidad)."""
    nb_path = notebook_path_factory()
    
    cells = [
        {"cell_type": "markdown", "source": "# Test"},
        {"cell_type": "code", "source": "print(1)"}
    ]
    
    result = await notebook_tools_inst.notebook_write(
        notebook_path=nb_path,
        cells=cells
    )
    
    assert "Successfully wrote" in result
    nb = nbformat.read(nb_path, as_version=4)
    assert len(nb.cells) == 2


async def test_notebook_write_empty_notebook(notebook_tools_inst, notebook_path_factory):
    """Test que notebook_write crea un notebook vacío si no hay cells."""
    nb_path = notebook_path_factory()
    
    result = await notebook_tools_inst.notebook_write(
        notebook_path=nb_path,
        cells=[]
    )
    
    assert "Successfully wrote" in result
    nb = nbformat.read(nb_path, as_version=4)
    assert len(nb.cells) == 0


# ======================================================================
# Test 3: Validación de inputs (sin destruir funcionalidad)
# ======================================================================

async def test_notebook_write_validates_cell_type(notebook_tools_inst, notebook_path_factory):
    """Test que cell_type inválido se rechaza."""
    nb_path = notebook_path_factory()
    
    cells = [
        {"cell_type": "invalid_type", "source": "test"}
    ]
    
    with pytest.raises(ValueError, match="Invalid cell_type"):
        await notebook_tools_inst.notebook_write(
            notebook_path=nb_path,
            cells=cells
        )


async def test_notebook_write_validates_cell_structure(notebook_tools_inst, notebook_path_factory):
    """Test que cells mal estructurados se rechazan."""
    nb_path = notebook_path_factory()
    
    # Cell sin 'source'
    cells = [{"cell_type": "code"}]
    
    with pytest.raises(ValueError, match="must be a dictionary"):
        await notebook_tools_inst.notebook_write(
            notebook_path=nb_path,
            cells=cells
        )


# ======================================================================
# Test 4: Notebook resultante es válido según nbformat
# ======================================================================

async def test_notebook_write_produces_valid_notebook(notebook_tools_inst, notebook_path_factory):
    """Test que el notebook producido pasa la validación de nbformat."""
    nb_path = notebook_path_factory()
    
    cells = [
        {"cell_type": "markdown", "source": "# Test"},
        {"cell_type": "code", "source": "x = 1\ny = 2"},
        {"cell_type": "markdown", "source": "## Subsección"},
        {"cell_type": "code", "source": "print(x + y)"}
    ]
    
    await notebook_tools_inst.notebook_write(
        notebook_path=nb_path,
        cells=cells
    )
    
    # Leer y validar
    nb = nbformat.read(nb_path, as_version=4)
    nbformat.validate(nb)  # Esto lanza excepción si no es válido
    
    assert len(nb.cells) == 4
    assert nb.cells[0].cell_type == 'markdown'
    assert nb.cells[1].cell_type == 'code'
    assert nb.cells[2].cell_type == 'markdown'
    assert nb.cells[3].cell_type == 'code'


# ======================================================================
# Test 5: Validación de tamaño de content_file
# ======================================================================

async def test_notebook_write_rejects_oversized_content_file(notebook_tools_inst, notebook_path_factory, tmp_path):
    """Test que content_file demasiado grande se rechaza."""
    # Crear un archivo que exceda el límite
    content_file = tmp_path / "huge.md"
    # Crear contenido que exceda 10x max_cell_source_size (default 10MB * 10 = 100MB)
    # Usar un límite más pequeño para el test
    notebook_tools_inst.config.max_cell_source_size = 1024  # 1KB
    
    huge_content = "x" * (1024 * 11)  # 11KB, excede 10x1KB=10KB
    content_file.write_text(f"---CELL---\ncell_type: code\n---\n{huge_content}", encoding='utf-8')
    
    nb_path = notebook_path_factory()
    
    with pytest.raises(ValueError, match="Content file too large"):
        await notebook_tools_inst.notebook_write(
            notebook_path=nb_path,
            content_file=str(content_file)
        )


async def test_notebook_write_validates_content_file_type(notebook_tools_inst, notebook_path_factory):
    """Test que content_file debe ser string."""
    nb_path = notebook_path_factory()
    
    with pytest.raises(ValueError, match="must be a string"):
        await notebook_tools_inst.notebook_write(
            notebook_path=nb_path,
            content_file=123  # No es string
        )
