"""
\u6570\u5b57\u6c38\u751f\u8ba1\u5212 - \u57fa\u7840\u6d4b\u8bd5
\u6d4b\u8bd5\u5171\u4eab\u5de5\u5177\u51fd\u6570\u3001\u914d\u7f6e\u52a0\u8f7d\u3001\u6807\u7b7e\u68c0\u6d4b\u7b49\u6838\u5fc3\u529f\u80fd
\u7528\u6cd5: python test_basic.py
"""
import sys
import os

# \u786e\u4fdd\u53ef\u4ee5\u5bfc\u5165\u540c\u76ee\u5f55\u6a21\u5757
sys.path.insert(0, os.path.dirname(__file__))

from utils import parse_frontmatter, build_frontmatter, read_file_content
from config_loader import load_tag_rules, load_seed_entities, load_business_signals, load_data_gaps


def test_parse_frontmatter_basic():
    """\u6d4b\u8bd5\u57fa\u672c frontmatter \u89e3\u6790"""
    text = "---\ntitle: test\ntags: [a, b]\n---\nHello world"
    fm, body = parse_frontmatter(text)
    assert fm["title"] == "test", f"title should be 'test', got {fm['title']}"
    assert fm["tags"] == ["a", "b"], f"tags mismatch"
    assert body == "Hello world", f"body should be 'Hello world', got '{body}'"
    print("  \u2705 parse_frontmatter basic")


def test_parse_frontmatter_bom():
    """\u6d4b\u8bd5 BOM \u5904\u7406"""
    text = "\ufeff---\ntitle: bom_test\n---\nBody"
    fm, body = parse_frontmatter(text)
    assert fm.get("title") == "bom_test", f"BOM handling failed: {fm}"
    assert body == "Body"
    print("  \u2705 parse_frontmatter BOM handling")


def test_parse_frontmatter_no_fm():
    """\u6d4b\u8bd5\u65e0 frontmatter \u7684\u6587\u672c"""
    text = "Just plain text"
    fm, body = parse_frontmatter(text)
    assert fm == {}, f"should return empty dict, got {fm}"
    assert body == "Just plain text"
    print("  \u2705 parse_frontmatter no frontmatter")


def test_build_frontmatter():
    """\u6d4b\u8bd5 frontmatter \u6784\u5efa"""
    fm = {"title": "Test", "tags": ["a", "b"], "type": "note"}
    result = build_frontmatter(fm)
    assert result.startswith("---"), "should start with ---"
    assert result.endswith("---"), "should end with ---"
    assert "title: Test" in result
    assert "tags: [a, b]" in result
    print("  \u2705 build_frontmatter")


def test_config_loader_yaml():
    """\u6d4b\u8bd5 YAML \u914d\u7f6e\u52a0\u8f7d"""
    rules = load_tag_rules()
    assert rules is not None, "tag_rules.yaml should exist"
    assert "dimension_tags" in rules, "should have dimension_tags"
    assert "track_keywords" in rules, "should have track_keywords"
    print(f"  \u2705 config_loader: tag_rules ({len(rules)} sections)")

    entities = load_seed_entities()
    assert entities is not None, "seed_entities.yaml should exist"
    assert len(entities) > 0, "should have entities"
    print(f"  \u2705 config_loader: seed_entities ({len(entities)} categories)")

    signals = load_business_signals()
    assert signals is not None, "business_signals.yaml should exist"
    assert len(signals) > 0, "should have signals"
    print(f"  \u2705 config_loader: business_signals ({len(signals)} signals)")

    gaps = load_data_gaps()
    assert gaps is not None, "data_gaps.yaml should exist"
    assert len(gaps) > 0, "should have gaps"
    print(f"  \u2705 config_loader: data_gaps ({len(gaps)} gaps)")


def test_tag_diary_imports():
    """\u6d4b\u8bd5 tag_diary \u53ef\u6b63\u5e38\u5bfc\u5165"""
    from tag_diary import detect_tags, find_entities_in_text, SEED_ENTITIES, TAG_RULES
    assert len(SEED_ENTITIES) > 40, f"should have 40+ entities, got {len(SEED_ENTITIES)}"
    assert len(TAG_RULES) > 10, f"should have 10+ rules, got {len(TAG_RULES)}"

    # \u6d4b\u8bd5\u6807\u7b7e\u68c0\u6d4b
    tags = detect_tags("\u6211\u610f\u8bc6\u5230\u4e00\u4ef6\u4e8b\uff0c\u5f00\u59cb\u505a\u4e86\u4e00\u4e2a\u9879\u76ee\uff0c\u51b3\u5b9a\u4ee5\u540e\u8981\u66f4\u52a0\u52aa\u529b")
    assert len(tags) > 0, "should detect some tags"
    print(f"  \u2705 tag_diary imports + detect_tags: {tags}")


def test_interview_schedule():
    """测试访谈日程动态生成"""
    from datetime import datetime, timedelta
    import config as _cfg
    start = datetime.strptime(_cfg.INTERVIEW_START_DATE, "%Y-%m-%d")
    schedule = {}
    for i, topic in enumerate(_cfg.INTERVIEW_TOPICS):
        date = start + timedelta(weeks=i)
        schedule[date.strftime("%Y-%m-%d")] = {"week": i + 1, "topic": topic}
    assert len(schedule) == 8, f"should have 8 weeks, got {len(schedule)}"
    today = datetime.now().strftime("%Y-%m-%d")
    next_date = None
    for d in sorted(schedule):
        if d >= today:
            next_date = d
            break
    if next_date is None:
        next_date = max(schedule)
    assert next_date is not None
    print(f"  ✅ interview schedule: {len(schedule)} weeks, next={next_date}")

def main():
    print("=" * 50)
    print("\u6570\u5b57\u6c38\u751f\u8ba1\u5212 - \u57fa\u7840\u6d4b\u8bd5")
    print("=" * 50)

    tests = [
        test_parse_frontmatter_basic,
        test_parse_frontmatter_bom,
        test_parse_frontmatter_no_fm,
        test_build_frontmatter,
        test_config_loader_yaml,
        test_tag_diary_imports,
        test_interview_schedule,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            print(f"\n\u8fd0\u884c: {test.__name__}")
            test()
            passed += 1
        except Exception as e:
            print(f"  \u274c FAILED: {e}")
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"\u7ed3\u679c: {passed} \u901a\u8fc7, {failed} \u5931\u8d25")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
