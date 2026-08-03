"""FastAPI 中间件层。

``RequestContextMiddleware`` 负责：
  * 解析或生成 ``X-Request-ID``，写入 :class:`starlette.requests.Request` 与
    :data:`logs.config.request_id_context`；
  * 输出统一安全响应头（``X-Content-Type-Options``、``X-Frame-Options`` 等）；
  * 失败/成功日志接入 JSON 日志通道。

此处直接 re-export ``middleware`` 包中的实现，避免业务代码修改。后续若需新增
中间件（如限流、审计），在此模块新增 ``xxx_middleware.py`` 后在
``__init__.py`` 暴露即可。
"""

from __future__ import annotations

from middleware import RequestContextMiddleware

__all__ = ["RequestContextMiddleware"]
