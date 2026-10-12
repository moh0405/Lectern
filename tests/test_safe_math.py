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
