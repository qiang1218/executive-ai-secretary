"""Hermes Worker 包（新架构）。

被 ``main.py`` 中 ``uvicorn.run("worker.app:app", ...)`` 字符串引用，
因此必须保证本包可被 import，且子模块 ``worker.app`` 暴露 ``app`` 符号。
"""
