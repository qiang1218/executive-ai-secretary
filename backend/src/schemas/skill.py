"""Skill 管理 Pydantic 模型。"""

from __future__ import annotations

import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


# 允许的文件后缀白名单（纯文本类）
_ALLOWED_EXTENSIONS = frozenset({
    ".md", ".txt", ".py", ".js", ".yaml", ".yml", ".json", ".sh", ".toml",
})


def _validate_file_path(path: str) -> str:
    """校验单个文件相对路径的安全性。"""
    if not path:
        raise ValueError("文件路径不能为空")
    if ".." in path.split("/"):
        raise ValueError(f"文件路径不能包含 '..': {path}")
    if path.startswith("/"):
        raise ValueError(f"文件路径不能以 '/' 开头: {path}")
    if "\x00" in path:
        raise ValueError(f"文件路径不能包含空字节: {path}")
    # 后缀白名单
    lower = path.lower()
    if not any(lower.endswith(ext) for ext in _ALLOWED_EXTENSIONS):
        raise ValueError(
            f"文件后缀不允许: {path}（允许: {', '.join(sorted(_ALLOWED_EXTENSIONS))}）"
        )
    return path


def _validate_slug(slug: str) -> str:
    """校验 slug 格式。"""
    if not slug:
        raise ValueError("slug 不能为空")
    if ".." in slug or "/" in slug or "\\" in slug:
        raise ValueError(f"slug 不能包含 '..' / '/' / '\\': {slug}")
    if "\x00" in slug:
        raise ValueError("slug 不能包含空字节")
    if len(slug) > 128:
        raise ValueError("slug 长度不能超过 128")
    return slug


class SkillCreate(BaseModel):
    """新建 skill 请求体。"""

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, max_length=128, description="唯一标识")
    name: str = Field(min_length=1, max_length=255, description="显示名")
    description: str = Field(default="", description="简短描述")
    root_file: str = Field(default="SKILL.md", max_length=255, description="主入口文件")
    is_enabled: bool = Field(default=False, description="是否启用")
    files: dict[str, str] = Field(
        default_factory=dict, description="文件树 {相对路径: 内容}"
    )

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, v: str) -> str:
        return _validate_slug(v)

    @field_validator("files")
    @classmethod
    def _check_files(cls, v: dict[str, str]) -> dict[str, str]:
        for path in v:
            _validate_file_path(path)
        return v


class SkillUpdate(BaseModel):
    """编辑 skill 请求体（所有字段可选）。"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    root_file: str | None = Field(default=None, max_length=255)
    is_enabled: bool | None = None
    files: dict[str, str] | None = Field(default=None, description="完整文件树（整体替换）")

    @field_validator("files")
    @classmethod
    def _check_files(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if v is not None:
            for path in v:
                _validate_file_path(path)
        return v


class SkillOut(BaseModel):
    """skill 详情输出（含 files 内容）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    description: str
    is_enabled: bool
    root_file: str
    files: dict[str, str]
    created_by_user_id: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class SkillListItem(BaseModel):
    """skill 列表项（不含 files 内容）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    description: str
    is_enabled: bool
    root_file: str
    file_count: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class SkillListOut(BaseModel):
    """skill 列表输出。"""

    skills: list[SkillListItem]
    total: int
    enabled_count: int
