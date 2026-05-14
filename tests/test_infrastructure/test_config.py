import os
import tempfile
from pathlib import Path
from src.infrastructure.config import Config


def test_config_loads_yaml():
    with tempfile.TemporaryDirectory() as tmp:
        yaml_path = Path(tmp) / "test.yaml"
        yaml_path.write_text("key1: value1\nnested:\n  key2: value2\n", encoding="utf-8")
        cfg = Config(config_dir=tmp)
        assert cfg.get("test.key1") == "value1"
        assert cfg.get("test.nested.key2") == "value2"


def test_config_get_with_default():
    cfg = Config(config_dir="/nonexistent_dir")
    assert cfg.get("missing.key") is None
    assert cfg.get("missing.key", "fallback") == "fallback"


def test_config_env_access():
    cfg = Config(config_dir="/nonexistent_dir")
    # env should be accessible
    assert cfg.get("env") is not None
    assert isinstance(cfg.get("env"), dict)


def test_config_reload():
    with tempfile.TemporaryDirectory() as tmp:
        yaml_path = Path(tmp) / "reload.yaml"
        yaml_path.write_text("version: 1\n", encoding="utf-8")
        cfg = Config(config_dir=tmp)
        assert cfg.get("reload.version") == 1
        yaml_path.write_text("version: 2\n", encoding="utf-8")
        cfg.reload()
        assert cfg.get("reload.version") == 2


def test_config_empty_dir():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Config(config_dir=tmp)
        assert cfg.get("anything") is None
