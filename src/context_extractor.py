import ast

from .models import CandidateSecret


class EnclosingBlockVisitor(ast.NodeVisitor):
    def __init__(self, target_line: int):
        self.target_line = target_line
        self.enclosing_node = None
        self.best_distance = float("inf")

    def visit_FunctionDef(self, node):
        self._check_node(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self._check_node(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self._check_node(node)
        self.generic_visit(node)

    def _check_node(self, node):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            if node.lineno <= self.target_line <= node.end_lineno:
                # Find the tightest enclosing block if nested
                distance = (self.target_line - node.lineno) + (node.end_lineno - self.target_line)
                if distance < self.best_distance:
                    self.best_distance = distance
                    self.enclosing_node = node


def extract_fixed_window_context(candidate: CandidateSecret, radius: int = 5) -> CandidateSecret:
    """Extract an exact context window centered on the offending line (default: 11 lines)."""
    try:
        lines = candidate.file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        candidate.sanitized_context = "ERROR_EXTRACTING_CONTEXT"
        candidate.variable_name = "UNKNOWN"
        return candidate

    line_index = max(candidate.line_number - 1, 0)
    start = max(0, line_index - radius)
    end = min(len(lines), line_index + radius + 1)
    context_lines = lines[start:end]
    candidate.sanitized_context = "\n".join(context_lines)
    candidate.variable_name = "UNKNOWN"

    if 0 <= line_index < len(lines):
        target_line = lines[line_index]
        if "=" in target_line:
            candidate.variable_name = target_line.split("=")[0].strip()

    return candidate


def extract_and_redact_context(candidate: CandidateSecret) -> CandidateSecret:
    """Extracts AST context and redacts the raw secret."""

    # Fallback for non-Python files (just grab lines around it)
    if candidate.file_path.suffix != ".py":
        return _fallback_windowing(candidate)

    try:
        source_code = candidate.file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source_code)

        visitor = EnclosingBlockVisitor(candidate.line_number)
        visitor.visit(tree)

        lines = source_code.splitlines()

        if visitor.enclosing_node:
            start_line = visitor.enclosing_node.lineno - 1
            end_line = visitor.enclosing_node.end_lineno
            block_lines = lines[start_line:end_line]

            # Windowing logic: > 40 lines requires truncation
            if len(block_lines) > 40:
                secret_idx = candidate.line_number - 1 - start_line
                window_start = max(1, secret_idx - 15)  # Keep index 0 (signature)
                window_end = min(len(block_lines), secret_idx + 16)

                context_lines = [block_lines[0]]
                if window_start > 1:
                    context_lines.append("    # ... [TRUNCATED] ...")
                context_lines.extend(block_lines[window_start:window_end])
                if window_end < len(block_lines):
                    context_lines.append("    # ... [TRUNCATED] ...")
            else:
                context_lines = block_lines
        else:
            return _fallback_windowing(candidate)

        raw_context = "\n".join(context_lines)

    except Exception:
        # If AST parsing fails (e.g., syntax error in the file), use fallback
        return _fallback_windowing(candidate)

    return _apply_redaction(candidate, raw_context, context_lines)


def _fallback_windowing(candidate: CandidateSecret) -> CandidateSecret:
    """Simple ±15 line windowing without AST for non-Python or broken files."""
    try:
        lines = candidate.file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        start = max(0, candidate.line_number - 16)
        end = min(len(lines), candidate.line_number + 15)
        raw_context = "\n".join(lines[start:end])
        return _apply_redaction(candidate, raw_context, lines[start:end])
    except Exception:
        candidate.sanitized_context = "ERROR_EXTRACTING_CONTEXT"
        candidate.variable_name = "UNKNOWN"
        return candidate


def _apply_redaction(
    candidate: CandidateSecret, raw_context: str, context_lines: list[str]
) -> CandidateSecret:
    """Applies the strict redaction string and attempts to extract variable name."""
    redaction_string = (
        f"<REDACTED_SECRET_LENGTH_{len(candidate.raw_secret)}_ENTROPY_{candidate.entropy:.2f}>"
    )
    candidate.sanitized_context = raw_context.replace(candidate.raw_secret, redaction_string)

    candidate.variable_name = "UNKNOWN"
    for line in context_lines:
        if candidate.raw_secret in line and "=" in line:
            candidate.variable_name = line.split("=")[0].strip()
            break

    return candidate
