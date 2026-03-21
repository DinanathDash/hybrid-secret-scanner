import os
import asyncio
from pathlib import Path
from typing import AsyncGenerator
import pathspec

# Layer 2: Global Shield - Constants for exclusion
GLOBAL_EXCLUDE_DIRS = {".git", "node_modules", "venv", "__pycache__", ".pytest_cache"}
BINARY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".exe", ".bin", ".pyc", ".pdf", ".zip"}
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_LINE_LENGTH = 1000

async def yield_scannable_files(root_dir: Path) -> AsyncGenerator[Path, None]:
    """
    Asynchronously yields files that pass Git-aware, Global, and Heuristic filters.
    """
    root_dir = root_dir.resolve()
    
    # Layer 1: Load Git-Aware filters
    gitignore_path = root_dir / ".gitignore"
    spec = None
    if gitignore_path.exists():
        with open(gitignore_path, "r") as f:
            spec = pathspec.PathSpec.from_lines("gitwildmatch", f.readlines())

    # Walk the directory
    for current_root, dirs, files in os.walk(root_dir):
        current_path = Path(current_root)
        
        # Prune excluded directories to prevent deep walking
        dirs[:] = [d for d in dirs if d not in GLOBAL_EXCLUDE_DIRS]
        
        for file in files:
            file_path = current_path / file
            relative_path = file_path.relative_to(root_dir)

            # Layer 1 & 2 Check: Gitignore and Extensions
            if spec and spec.match_file(str(relative_path)):
                continue
            if file_path.suffix.lower() in BINARY_EXTENSIONS:
                continue

            # Layer 3: Heuristic Blocks
            try:
                stats = file_path.stat()
                if stats.st_size > MAX_FILE_SIZE_BYTES:
                    continue

                # Check for line length heuristic
                is_valid = True
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if len(line) > MAX_LINE_LENGTH:
                            is_valid = False
                            break
                
                if is_valid:
                    yield file_path
                    # Small sleep to ensure we don't hog the event loop if walking massive dirs
                    await asyncio.sleep(0)

            except (PermissionError, OSError):
                continue