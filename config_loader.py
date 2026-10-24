"""
\u6570\u5b57\u6c38\u751f\u8ba1\u5212 - \u914d\u7f6e\u52a0\u8f7d\u5668
\u4ece config/ \u76ee\u5f55\u52a0\u8f7d YAML \u914d\u7f6e\uff0c\u5982\u4e0d\u5b58\u5728\u5219\u4f7f\u7528\u6a21\u5757\u5185\u9ed8\u8ba4\u503c
"""
import yaml
from pathlib import Path

CONFIG_DIR = Path(__file__).parent / "config"


def _load_yaml(filename: str):
    """\u52a0\u8f7d YAML \u6587\u4ef6\uff0c\u4e0d\u5b58\u5728\u65f6\u8fd4\u56de None"""
    filepath = CONFIG_DIR / filename
    if not filepath.exists():
        return None
    try:
        return yaml.safe_load(filepath.read_text(encoding="utf-8"))
    except (yaml.YAMLError, IOError) as e:
        print(f"  \u8b66\u544a: \u52a0\u8f7d {filename} \u5931\u8d25: {e}")
        return None


def load_tag_rules() -> dict | None:
    """\u52a0\u8f7d\u6807\u7b7e\u68c0\u6d4b\u89c4\u5219 (TAG_RULES + track_keywords + relation_keywords)"""
    return _load_yaml("tag_rules.yaml")


def load_seed_entities() -> dict | None:
    """\u52a0\u8f7d\u79cd\u5b50\u5b9e\u4f53\u5e93"""
    return _load_yaml("seed_entities.yaml")


def load_business_signals() -> list | None:
    """\u52a0\u8f7d\u5546\u4e1a\u4e3b\u9898\u4fe1\u53f7\u68c0\u6d4b\u89c4\u5219"""
    return _load_yaml("business_signals.yaml")


def load_data_gaps() -> dict | None:
    """\u52a0\u8f7d\u6570\u636e\u8d28\u91cf\u7f3a\u53e3\u914d\u7f6e"""
    return _load_yaml("data_gaps.yaml")
