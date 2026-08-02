import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memory.store import MemoryStore


def test_recall_finds_matching_fact():
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(storage_path=Path(d) / "memory.json")
        store.add_fact("用户喜欢用飞书管理团队")
        results = store.recall("团队用什么工具管理")
        assert any("飞书" in r for r in results)


def test_recall_finds_correction_with_higher_priority_than_fact():
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(storage_path=Path(d) / "memory.json")
        store.add_fact("用户在深圳")
        store.add_correction("用户已经搬到杭州了，不是深圳")
        results = store.recall("用户在哪个城市")
        assert results[0].find("杭州") != -1


def test_recall_returns_empty_when_nothing_relevant():
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(storage_path=Path(d) / "memory.json")
        store.add_fact("用户喜欢用飞书管理团队")
        assert store.recall("今天天气怎么样") == []


def test_persists_across_instances():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "memory.json"
        MemoryStore(storage_path=path).add_fact("用户喜欢用飞书管理团队")
        store2 = MemoryStore(storage_path=path)
        assert any("飞书" in r for r in store2.recall("团队管理工具"))


def test_recall_matches_mixed_script_text():
    # 回归测试：_WORD_RE 曾经在中英文/数字混排且无分隔符时（如"GPT4很强"）把整段贪婪吞成
    # 一个token，导致召回失效。修好之后中英文各自独立分词，互不吞并。
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(storage_path=Path(d) / "memory.json")
        store.add_fact("用户常用GPT4写代码")
        results = store.recall("GPT4好用吗")
        assert any("GPT4" in r for r in results)


def test_recall_short_term_only_from_current_session():
    # 2026-07-28真机验收发现：recall()完全不看session_id，在全部历史短期对话记录里做
    # 关键词联想，不同session、完全不相关的话题只要字面重合就可能被一起召回。short_term
    # 层是"这一轮对话的原始上下文"，语义上就该按session隔离；facts/corrections是提炼过的
    # 持久知识，本来就该跨session可查，不受此限制。
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(storage_path=Path(d) / "memory.json")
        store.add_short_term("session-old", "user", "帮我查一下杭州的天气预报")
        store.add_short_term("session-new", "user", "帮我查一下上海的天气预报")
        results = store.recall("天气预报", session_id="session-new")
        assert any("上海" in r for r in results)
        assert not any("杭州" in r for r in results)


def test_recall_facts_still_global_across_sessions():
    # facts/corrections 层不受 session_id 限制——这是它们存在的意义：跨会话持久知识。
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(storage_path=Path(d) / "memory.json")
        store.add_fact("用户喜欢用飞书管理团队")
        results = store.recall("团队用什么工具管理", session_id="a-brand-new-session")
        assert any("飞书" in r for r in results)
