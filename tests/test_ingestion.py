import pytest
from pathlib import Path
from src.ingestion import yield_scannable_files

@pytest.mark.asyncio
async def test_ingestion_filters(tmp_path):
    # Setup: Create a mock directory structure
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules/secret.txt").write_text("should_be_ignored")
    
    (tmp_path / ".gitignore").write_text("ignored_file.txt")
    (tmp_path / "ignored_file.txt").write_text("should_be_ignored")
    
    valid_file = tmp_path / "app.py"
    valid_file.write_text("print('hello world')")
    
    large_file = tmp_path / "large.txt"
    with open(large_file, "wb") as f:
        f.seek(3 * 1024 * 1024) # 3MB
        f.write(b"0")
        
    long_line_file = tmp_path / "long_line.txt"
    long_line_file.write_text("a" * 1001)

    # Execute
    found_files = []
    async for f in yield_scannable_files(tmp_path):
        found_files.append(f.name)

    # Assertions
    assert "app.py" in found_files
    assert ".gitignore" in found_files           # The scanner correctly picks this up!
    assert "secret.txt" not in found_files       # Layer 2 check
    assert "ignored_file.txt" not in found_files # Layer 1 check
    assert "large.txt" not in found_files        # Layer 3 size check
    assert "long_line.txt" not in found_files    # Layer 3 length check
    assert len(found_files) == 2                 # Expecting exactly 2 valid files now