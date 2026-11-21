import pytest

pytest.importorskip("sympy")

from backend.advanced_ai import math_solve  # noqa: E402
from backend import safe_math  # noqa: E402


@pytest.mark.parametrize(
    ("text", "kind", "needle"),
    [
        ("differentiate sin(x)", "differentiate", "cos"),
        ("derivative x^3", "differentiate", "3 x^{2}"),
        ("integrate x^2", "integrate", "+ C"),
        ("simplify (x^2 + 2x + 1)", "simplify", "x"),
        ("expand (x+1)^3", "expand", "x^{3}"),
        ("factor x^2 - 1", "factor", "x - 1"),
        ("solve x^2 = 4 for x", "solve", "2"),
        ("solve 2x + 3 = 11", "solve", "4"),
        ("differentiate y^2 wrt y", "differentiate", "2 y"),
        ("x^2 + 1", "expr", "x^{2}"),
    ],
)
def test_supported_commands(text, kind, needle):
    res = math_solve(text)
    assert res["ok"], res
    assert res["kind"] == kind and needle in res["latex"]
    assert res["steps"]


@pytest.mark.parametrize(
    "text",
    [
        "__import__('os').system('echo pwned')",
        "open('/etc/passwd')",
        "().__class__.__bases__",
        "x.__class__",
        "differentiate lambda: 1",
        "eval('1+1')",
        "solve x = 1 for os",
        "integrate [1,2,3]",
        "1; import os",
        "",
        "   ",
        "x" * 500,
    ],
)
def test_malicious_or_invalid_input_is_rejected(text):
    res = math_solve(text)
    assert res["ok"] is False and res["error"]


def test_rejection_happens_before_any_evaluation():
    with pytest.raises(safe_math.MathInputError):
        safe_math.validate("__import__('os')")
    with pytest.raises(safe_math.MathInputError):
        safe_math.parse("os.system(1)")


def test_expensive_expression_times_out_and_worker_recovers():
    res = safe_math.solve_request("9^9^9^9", timeout=2)
    assert res["ok"] is False and "timed out" in res["error"]
    # the pool was replaced, so normal requests still work
    assert math_solve("integrate x")["ok"]


def test_subprocess_fallback_when_the_pool_cannot_start(monkeypatch):
    """AWS Lambda has no shared memory, so the process pool raises OSError; math must still work."""
    import backend.safe_math as m

    def broken():
        raise OSError(30, "Read-only file system")

    monkeypatch.setattr(m, "_get_pool", broken)
    monkeypatch.setattr(m, "_use_subprocess", False)
    assert m.solve_request("2+3*4")["ok"] is True
    assert m._use_subprocess is True
    assert m.solve_request("differentiate sin(x)")["ok"] is True
    slow = m._compute_in_subprocess("9**9**9**9", 1.0)
    assert slow["ok"] is False and "timed out" in slow["error"]


@pytest.mark.parametrize(
    ("text", "needle", "position"),
    [
        ("integrate(((", "Unbalanced parentheses", 11),
        ("x^2 + (3", "never closed", 6),
        ("x)", "no matching '('", 1),
        ("2 +", "ends with '+'", 2),
        ("x */ 2", "Two operators in a row", 3),
        ("sin()", "Empty parentheses", 3),
        ("x = 2", "only used with solve", 2),
        ("solve x = 1 = 2", "one '='", 12),
        ("x + integrate(x)", "is a command", 4),
        ("integrate", "Add an expression after 'integrate'", 9),
        ("differentiate foo(x)", "'foo' is not a function or variable", 14),
        ("2 # 3", "('#')", 2),
    ],
)
def test_parse_errors_are_friendly_and_point_at_the_problem(text, needle, position):
    res = safe_math.solve_request(text)
    assert res["ok"] is False
    assert needle in res["error"]
    assert res["position"] == position
    # never SymPy's tokenizer internals
    for leak in ("EOF", "<string>", "multi-line", "invalid syntax"):
        assert leak not in res["error"]


def test_allowed_function_called_with_bad_syntax_is_not_called_a_bad_name():
    res = safe_math.solve_request("integrate(((")
    assert "not an allowed name" not in res["error"] and "integrate" not in res["error"]


@pytest.mark.parametrize("text", ["integrate(x^2)", "factorial(5)", "x**2", "2*-3", "(x+1)(x-1)", "solve x^2 = 4 for x"])
def test_commands_without_a_space_and_tricky_operators_still_work(text):
    assert safe_math.solve_request(text)["ok"], text


def test_sympy_parse_failure_is_reported_without_internals():
    with pytest.raises(safe_math.MathInputError) as e:
        safe_math.parse("2 3 (")
    assert "EOF" not in str(e.value) and "<string>" not in str(e.value)
