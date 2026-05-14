import os
import yaml
from pathlib import Path


class Config:
    def __init__(self, config_dir: str = "config"):
        self._data: dict = {}
        self._config_dir = Path(config_dir)
        self.load()

    def load(self) -> None:
        self._data = {}
        if self._config_dir.exists():
            for yf in self._config_dir.glob("*.yaml"):
                with open(yf, encoding="utf-8") as f:
                    self._data[yf.stem] = yaml.safe_load(f)
        self._data["env"] = dict(os.environ)

    def get(self, key: str, default=None):
        keys = key.split(".")
        val = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
        return val if val is not None else default

    def reload(self) -> None:
        self.load()


config = Config()
