"""Symbolic math on untrusted input.

SymPy's `sympify`/`parse_expr` ultimately call `eval`, so user text must never
reach them unchecked. Three layers here:

1. `validate()` rejects anything outside a small grammar: digits, operators,
   parentheses, and identifiers from a whitelist (single-letter variables and a
   fixed set of functions/constants). No attribute access, brackets, quotes,
   underscores or other names.
2. Parsing uses empty builtins and a local dict containing only whitelisted SymPy objects.
3. `solve_request()` runs the computation in a separate worker process with a
   timeout, so expressions such as `9**9**9**9` cannot hang the server; a stuck
   worker is killed and replaced. Where the process pool cannot run (AWS Lambda has
   no shared memory for its locks) a one-shot subprocess is used instead.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FutureTimeout
from multiprocessing import get_context
from typing import Any, Dict, List, Optional, Tuple

try:
    import sympy as sp
    from sympy.parsing.sympy_parser import (
        convert_xor,
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )
except Exception:  # sympy is an optional extra
    sp = None

MAX_INPUT_CHARS = 200
TIMEOUT_SECONDS = 5.0

_ALLOWED_CHARS = re.compile(r"^[0-9A-Za-z+\-*/^().,\s=]+$")
_IDENT = re.compile(r"[A-Za-z][A-Za-z0-9]*")
FUNCTIONS = {
    "sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh",
    "exp", "log", "ln", "sqrt", "Abs", "abs", "factorial", "floor", "ceiling",
}
CONSTANTS = {"pi", "e", "E", "I", "oo"}
COMMANDS = {"simplify", "differentiate", "derivative", "integrate", "solve", "expand", "factor"}


class MathInputError(ValueError):
    """The input is not a valid or permitted math expression.

    `position` is the 0-based character index of the problem in the text that was checked, when known.
    """

    def __init__(self, message: str, position: Optional[int] = None):
        super().__init__(message)
        self.position = position


def _is_variable(name: str) -> bool:
    return len(name) == 1 and name.isalpha()


def validate(text: str) -> str:
    """Return the cleaned expression text or raise MathInputError."""
    text = (text or "").strip()
    if not text:
        raise MathInputError("Empty expression")
    if len(text) > MAX_INPUT_CHARS:
        raise MathInputError(f"Expression is too long (max {MAX_INPUT_CHARS} characters)")
    if not _ALLOWED_CHARS.match(text):
        bad = next((i for i, ch in enumerate(text) if not _ALLOWED_CHARS.match(ch)), None)
        shown = f" ('{text[bad]}')" if bad is not None else ""
        raise MathInputError(f"Only numbers, letters, + - * / ^ ( ) , = and spaces are allowed{shown}", bad)
    attr = re.search(r"\.[A-Za-z_]|[A-Za-z_]\.", text)
    if attr:
        raise MathInputError("Attribute access is not allowed", attr.start())
    for m in _IDENT.finditer(text):
        name = m.group(0)
        if name in FUNCTIONS or name in CONSTANTS or _is_variable(name):
            continue
        if name.lower() in COMMANDS:
            raise MathInputError(f"'{name}' is a command, so it goes first, as in '{name.lower()} x^2'", m.start())
        raise MathInputError(f"'{name}' is not a function or variable this tool knows", m.start())
    return text


_BINARY = "*/^"
_ANY_OP = "+-*/^"


def check_structure(text: str, offset: int = 0) -> None:
    """Find the common typing mistakes SymPy would only report as an opaque syntax error.

    Positions in the raised MathInputError are `offset` + the index in `text`.
    """
    stack: List[int] = []
    prev = ""  # previous non-space character
    prev_i = -1
    for i, ch in enumerate(text):
        if ch.isspace():
            continue
        at = offset + i
        if ch == "(":
            stack.append(at)
        elif ch == ")":
            if not stack:
                raise MathInputError("Unbalanced parentheses: this ')' has no matching '('", at)
            opened = stack.pop()
            if prev == "(":
                raise MathInputError("Empty parentheses: put an expression inside", opened)
        if ch in _BINARY:
            doubled_star = ch == "*" and prev == "*" and prev_i == i - 1
            if not doubled_star and prev in _ANY_OP and prev:
                raise MathInputError(f"Two operators in a row ('{prev}{ch}'): something is missing between them", at)
            if not doubled_star and (prev == "" or prev in "(,="):
                raise MathInputError(f"'{ch}' needs something before it", at)
        if ch in ",=" and (prev == "" or prev in "(,=" or prev in _ANY_OP):
            raise MathInputError(f"Something is missing before '{ch}'", at)
        if ch == ")" and prev in _ANY_OP + ",=":
            raise MathInputError(f"Something is missing after '{prev}'", offset + prev_i)
        prev, prev_i = ch, i
    if prev and prev in _ANY_OP + ",=":
        raise MathInputError(f"The expression ends with '{prev}': something is missing after it", offset + prev_i)
    if stack:
        raise MathInputError("Unbalanced parentheses: this '(' is never closed", stack[-1])


_COMMAND_RE = re.compile(r"^(" + "|".join(sorted(COMMANDS, key=len, reverse=True)) + r")(?![A-Za-z0-9])", re.IGNORECASE)
_VAR_SPLIT = re.compile(r"\s+(?:wrt|for|with respect to)\s+")


def precheck(user_input: str) -> None:
    """Check the whole request (command, expression, variable) before any parsing.

    Raises MathInputError whose position indexes the stripped input, so a UI can point at it.
    """
    s = (user_input or "").strip()
    if not s:
        raise MathInputError("Empty expression")
    if len(s) > MAX_INPUT_CHARS:
        raise MathInputError(f"Expression is too long (max {MAX_INPUT_CHARS} characters)")
    cmd, body = _split_command(s)
    start = len(s) - len(body) if body else len(s)
    if cmd != "expr" and not body:
        raise MathInputError(f"Add an expression after '{cmd}', as in '{cmd} x^2'", len(s))
    m = _VAR_SPLIT.search(body) if cmd != "expr" else None
    parts = [(body[: m.start()], start), (body[m.end():], start + m.end())] if m else [(body, start)]
    expr_text, expr_at = parts[0]
    for text, at in parts:
        try:
            validate(text)
        except MathInputError as e:
            if e.position is not None:
                lead = len(text) - len(text.lstrip())
                e.position += at + lead
            raise
    if "=" in expr_text and cmd != "solve":
        raise MathInputError("'=' is only used with solve, as in 'solve x^2 = 4'", expr_at + expr_text.index("="))
    if expr_text.count("=") > 1:
        raise MathInputError("An equation has one '='", expr_at + expr_text.index("=", expr_text.index("=") + 1))
    check_structure(expr_text, expr_at)


def _local_dict() -> Dict[str, Any]:
    d: Dict[str, Any] = {}
    for name in FUNCTIONS | CONSTANTS:
        if name == "ln":
            d[name] = sp.log
        elif name == "abs":
            d[name] = sp.Abs
        elif name == "e":
            d[name] = sp.E
        elif name == "oo":
            d[name] = sp.oo
        else:
            d[name] = getattr(sp, name)
    # Names the parser's own transformations emit (e.g. 2 -> Integer(2), x -> Symbol('x')).
    # User text cannot reference these: validate() only lets whitelisted names through.
    for helper in ("Integer", "Float", "Rational", "Symbol", "Function"):
        d[helper] = getattr(sp, helper)
    return d


def parse(text: str):
    """Parse a validated expression into a SymPy object (builtins disabled)."""
    text = validate(text)
    transformations = standard_transformations + (convert_xor, implicit_multiplication_application)
    try:
        return parse_expr(
            text,
            local_dict=_local_dict(),
            global_dict={"__builtins__": {}},
            transformations=transformations,
            evaluate=True,
        )
    except Exception as e:
        # SymPy's messages describe its own tokenizer ("unexpected EOF", "<string>, line 1"), not the user's text.
        raise MathInputError("Couldn't read this expression. Check for a missing operator or parenthesis.") from e


def _split_command(user_input: str) -> Tuple[str, str]:
    """("integrate", "x^2") for "integrate x^2" and also for "integrate(x^2)"; ("expr", text) otherwise."""
    s = user_input.strip()
    m = _COMMAND_RE.match(s)
    if m:
        return m.group(1).lower(), s[m.end():].strip()
    return "expr", s


def _error(e: MathInputError) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "error": str(e), "steps": ["Could not parse expression."]}
    if e.position is not None:
        out["position"] = e.position
    return out


def _compute(user_input: str) -> Dict[str, Any]:
    """Pure computation; runs inside the worker process."""
    if sp is None:
        return {"ok": False, "error": "sympy not installed", "steps": ["Install sympy for full math features."]}
    try:
        precheck(user_input)
        cmd, body = _split_command(user_input)
        var = sp.Symbol("x")
        if cmd in {"differentiate", "derivative", "integrate", "simplify", "expand", "factor"}:
            m = re.split(r"\s+(?:wrt|for|with respect to)\s+", body, maxsplit=1)
            body = m[0]
            if len(m) == 2:
                var_text = validate(m[1])
                if not _is_variable(var_text.strip()):
                    raise MathInputError("The variable must be a single letter")
                var = sp.Symbol(var_text.strip())
            expr = parse(body)
            if cmd in {"differentiate", "derivative"}:
                res, steps, latex = sp.diff(expr, var), ["Parsed expression", f"Differentiated with respect to {var}"], None
                kind = "differentiate"
            elif cmd == "integrate":
                res, steps, latex = sp.integrate(expr, var), ["Parsed expression", f"Integrated with respect to {var}"], None
                kind = "integrate"
                latex = sp.latex(res) + " + C"
            elif cmd == "expand":
                res, steps, latex, kind = sp.expand(expr), ["Parsed expression", "Expanded products and powers"], None, "expand"
            elif cmd == "factor":
                res, steps, latex, kind = sp.factor(expr), ["Parsed expression", "Factored over the rationals"], None, "factor"
            else:
                res, steps, latex, kind = sp.simplify(expr), ["Parsed expression", "Applied algebraic simplification"], None, "simplify"
            return {"ok": True, "kind": kind, "latex": latex or sp.latex(res), "steps": steps}
        if cmd == "solve":
            m = re.split(r"\s+for\s+", body, maxsplit=1)
            eq_text = m[0]
            if len(m) == 2:
                v = validate(m[1]).strip()
                if not _is_variable(v):
                    raise MathInputError("The variable must be a single letter")
                var = sp.Symbol(v)
            if "=" in eq_text:
                left, right = eq_text.split("=", 1)
                sol = sp.solve(sp.Eq(parse(left), parse(right)), var)
            else:
                sol = sp.solve(parse(eq_text), var)
            return {"ok": True, "kind": "solve", "latex": sp.latex(sol), "steps": ["Parsed equation", f"Solved for {var}"]}
        expr = parse(body)
        return {"ok": True, "kind": "expr", "latex": sp.latex(expr), "steps": ["Parsed expression", "Rendered LaTeX"]}
    except MathInputError as e:
        return _error(e)
    except Exception:
        return {"ok": False, "error": "Couldn't compute this. Try a simpler or differently written expression.", "steps": ["Computation failed."]}


# ----------------------------------------------------------------------
# Worker process with timeout
# ----------------------------------------------------------------------
_pool: Optional[ProcessPoolExecutor] = None


def _get_pool() -> ProcessPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ProcessPoolExecutor(max_workers=1, mp_context=get_context("spawn"))
    return _pool


def _kill_pool() -> None:
    global _pool
    pool, _pool = _pool, None
    if pool is None:
        return
    procs: List[Any] = list(getattr(pool, "_processes", {}).values())
    pool.shutdown(wait=False, cancel_futures=True)
    for p in procs:
        try:
            p.kill()
        except Exception:
            pass


def _compute_in_subprocess(user_input: str, timeout: float) -> Dict[str, Any]:
    """Run `_compute` in a fresh interpreter; needs no shared memory, and a timeout kills it."""
    try:
        done = subprocess.run(
            [sys.executable, "-m", "backend.safe_math", "--worker"],
            input=json.dumps(user_input), capture_output=True, text=True, timeout=timeout,
        )
        return json.loads(done.stdout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Computation timed out after {timeout:g}s", "steps": ["Expression too expensive."]}
    except Exception as e:
        return {"ok": False, "error": f"Math worker failed: {e}", "steps": ["Computation failed."]}


_use_subprocess = False


def solve_request(user_input: str, timeout: float = TIMEOUT_SECONDS) -> Dict[str, Any]:
    """Validate and compute `user_input` in a worker process, with a timeout."""
    if sp is None:
        return _compute(user_input)
    # Cheap checks first, in-process, so obviously bad input never reaches the worker.
    try:
        precheck(user_input)
    except MathInputError as e:
        return _error(e)
    global _use_subprocess
    if _use_subprocess:
        return _compute_in_subprocess(user_input, timeout)
    try:
        return _get_pool().submit(_compute, user_input).result(timeout=timeout)
    except OSError:  # no shared memory for the pool's locks (e.g. AWS Lambda)
        _kill_pool()
        _use_subprocess = True
        return _compute_in_subprocess(user_input, timeout)
    except FutureTimeout:
        _kill_pool()
        return {"ok": False, "error": f"Computation timed out after {timeout:g}s", "steps": ["Expression too expensive."]}
    except Exception as e:  # broken pool, etc.
        _kill_pool()
        return {"ok": False, "error": f"Math worker failed: {e}", "steps": ["Computation failed."]}


if __name__ == "__main__" and "--worker" in sys.argv:
    print(json.dumps(_compute(json.loads(sys.stdin.read()))))
