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
   worker is killed and replaced.
"""

from __future__ import annotations

import re
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
    """The input is not a valid or permitted math expression."""


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
        raise MathInputError("Only numbers, letters, + - * / ^ ( ) , = and spaces are allowed")
    if re.search(r"\.[A-Za-z_]|[A-Za-z_]\.", text):
        raise MathInputError("Attribute access is not allowed")
    for name in _IDENT.findall(text):
        if name in FUNCTIONS or name in CONSTANTS or _is_variable(name):
            continue
        raise MathInputError(f"'{name}' is not an allowed name")
    return text


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
        raise MathInputError(f"Could not parse expression: {e}") from e


def _split_command(user_input: str) -> Tuple[str, str]:
    s = user_input.strip()
    first = s.split(None, 1)[0].lower() if s else ""
    if first in COMMANDS:
        return first, s[len(first):].strip()
    return "expr", s


def _compute(user_input: str) -> Dict[str, Any]:
    """Pure computation; runs inside the worker process."""
    if sp is None:
        return {"ok": False, "error": "sympy not installed", "steps": ["Install sympy for full math features."]}
    try:
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
        return {"ok": False, "error": str(e), "steps": ["Could not parse expression."]}
    except Exception as e:
        return {"ok": False, "error": f"Could not compute: {e}", "steps": ["Computation failed."]}


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


def solve_request(user_input: str, timeout: float = TIMEOUT_SECONDS) -> Dict[str, Any]:
    """Validate and compute `user_input` in a worker process, with a timeout."""
    if sp is None:
        return _compute(user_input)
    # Cheap checks first, in-process, so obviously bad input never reaches the worker.
    try:
        cmd, body = _split_command(user_input)
        for part in re.split(r"\s+(?:wrt|for|with respect to)\s+", body, maxsplit=1):
            validate(part)
    except MathInputError as e:
        return {"ok": False, "error": str(e), "steps": ["Could not parse expression."]}
    try:
        return _get_pool().submit(_compute, user_input).result(timeout=timeout)
    except FutureTimeout:
        _kill_pool()
        return {"ok": False, "error": f"Computation timed out after {timeout:g}s", "steps": ["Expression too expensive."]}
    except Exception as e:  # broken pool, etc.
        _kill_pool()
        return {"ok": False, "error": f"Math worker failed: {e}", "steps": ["Computation failed."]}
