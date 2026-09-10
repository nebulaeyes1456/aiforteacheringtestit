"""兼容入口：实际配置已迁至 tutor/config.py。

保留此文件仅为兼容可能存在的 `import config` 旧引用，新代码请用 `from tutor import config`。
"""
from tutor.config import *  # noqa: F401,F403
