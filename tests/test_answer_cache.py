from backend.api.answer_cache import AnswerCache, make_key


def test_key_ignores_case_and_spacing_but_not_what_changes_the_answer():
    base = make_key("What is a heap?", "technical", 3, None, 0.2, "v1:5")
    assert make_key("  what   IS a heap? ", "technical", 3, None, 0.2, "v1:5") == base
    for other in (
        make_key("What is a heap?", "eli5", 3, None, 0.2, "v1:5"),
        make_key("What is a heap?", "technical", 5, None, 0.2, "v1:5"),
        make_key("What is a heap?", "technical", 3, "gemini-3.7-flash", 0.2, "v1:5"),
        make_key("What is a heap?", "technical", 3, None, 0.9, "v1:5"),
        make_key("What is a heap?", "technical", 3, None, 0.2, "v1:6"),  # the index changed
    ):
        assert other != base


def test_get_put_and_hit_counts():
    c = AnswerCache()
    k = make_key("q", None, 3, None, 0.2, "v")
    assert c.get(k) is None
    c.put(k, {"answer": "a"})
    assert c.get(k) == {"answer": "a"}
    assert (c.hits, c.misses, len(c)) == (1, 1, 1)


def test_least_recently_used_entry_is_evicted():
    c = AnswerCache(max_entries=2)
    keys = [make_key(f"q{i}", None, 3, None, 0.2, "v") for i in range(3)]
    c.put(keys[0], {"n": 0})
    c.put(keys[1], {"n": 1})
    c.get(keys[0])  # keys[1] is now the oldest
    c.put(keys[2], {"n": 2})
    assert c.get(keys[1]) is None and c.get(keys[0]) and c.get(keys[2])


def test_clear():
    c = AnswerCache()
    c.put(make_key("q", None, 3, None, 0.2, "v"), {"a": 1})
    c.clear()
    assert len(c) == 0
