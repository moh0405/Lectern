"""Guards for the evaluation harness: the metrics are right, the labels are valid, and the cheap
configurations stay above a floor so retrieval regressions fail CI."""

from pathlib import Path

import pytest

from eval.harness import CONFIGS, CORPORA, evaluate, load_questions
from eval.metrics import (
    QuestionResult,
    auroc,
    evidence_coverage,
    first_relevant_rank,
    is_relevant,
    norm,
    summarize,
)

ROOT = Path(__file__).resolve().parents[1] / "eval"


def chunk(doc, text):
    return {"doc": doc, "text": text}


class TestMetrics:
    def test_relevance_needs_right_document_and_phrase(self):
        ev = {"doc": "a.md", "any": ["hash table"]}
        assert is_relevant(chunk("a.md", "A Hash   Table maps keys"), ev)  # case and whitespace insensitive
        assert not is_relevant(chunk("b.md", "a hash table"), ev)
        assert not is_relevant(chunk("a.md", "a tree"), ev)

    def test_pdf_artifacts_do_not_break_matching(self):
        ev = {"doc": "x.pdf", "any": ["first in first out"]}
        assert is_relevant(chunk("x.pdf", "a ﬁrst in ﬁrst out strategy"), ev)  # ligature
        assert norm("Dijkstra’s") == "dijkstra's"

    def test_rank_and_coverage(self):
        chunks = [chunk("a.md", "x"), chunk("a.md", "needle one"), chunk("b.md", "needle two")]
        expect = [{"doc": "a.md", "any": ["needle one"]}, {"doc": "b.md", "any": ["needle two"]}]
        assert first_relevant_rank(chunks, expect) == 2
        assert first_relevant_rank(chunks[:1], expect) is None
        assert evidence_coverage(chunks, expect) == 1.0
        assert evidence_coverage(chunks[:2], expect) == 0.5

    def test_auroc(self):
        assert auroc([0.9, 0.8], [0.1, 0.2]) == 1.0
        assert auroc([0.1], [0.9]) == 0.0
        assert auroc([0.5], [0.5]) == 0.5
        assert auroc([], [0.5]) is None

    def test_summary(self):
        def r(i, rank, ans=True, score=0.5):
            return QuestionResult(f"q{i}", "direct", "?", ans, rank, score, 1.0 if rank else 0.0)

        s = summarize([r(1, 1), r(2, 3), r(3, None), r(4, None, ans=False, score=0.1)])
        assert (s.n_answerable, s.n_unanswerable) == (3, 1)
        assert s.hit[1] == pytest.approx(1 / 3) and s.hit[3] == pytest.approx(2 / 3)
        assert s.mrr == pytest.approx((1 + 1 / 3) / 3)
        assert s.misses == ["q3"]
        assert s.abstain_auroc == 1.0


def normalized(text):
    return norm(text)


class TestLabels:
    def test_synthetic_evidence_exists_in_the_corpus(self):
        for q in load_questions(ROOT / "synthetic_questions.jsonl"):
            for e in q["expect"]:
                text = normalized((ROOT / "corpus" / e["doc"]).read_text(encoding="utf-8"))
                assert any(normalized(p) in text for p in e["any"]), (q["id"], e)

    @pytest.mark.parametrize("name", ["synthetic", "real"])
    def test_question_files_are_well_formed(self, name):
        qs = load_questions(CORPORA[name].questions)
        ids = [q["id"] for q in qs]
        assert len(ids) == len(set(ids))
        for q in qs:
            assert q["answerable"] == bool(q["expect"]), q["id"]
            assert q["category"] and q["question"].strip().endswith(("?", ".")), q["id"]
            for e in q["expect"]:
                assert e["doc"] and e["any"], q["id"]
        assert any(not q["answerable"] for q in qs)


class TestRegressionFloors:
    """Cheap, deterministic configurations on the committed corpus. Floors sit a little below today's
    results (see eval/reports/synthetic.md) so noise does not fail CI but a real regression does."""

    def test_keyword_retrieval_floor(self):
        res = evaluate(CORPORA["synthetic"], CONFIGS["keyword"])
        s = res["summary"]
        assert s.hit[3] >= 0.90 and s.hit[5] >= 0.90 and s.mrr >= 0.80
        assert s.abstain_auroc >= 0.95  # unanswerable questions score clearly lower

    def test_hashing_dense_is_not_catastrophically_broken(self):
        s = evaluate(CORPORA["synthetic"], CONFIGS["hashing-dense"])["summary"]
        assert s.hit[5] >= 0.70
