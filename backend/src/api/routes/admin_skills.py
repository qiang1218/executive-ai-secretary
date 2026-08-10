"""Skill 管理路由（admin only）。

挂载在 ``/admin/skills`` 前缀下。admin 创建/编辑/启停/删除 skill，
启用时文件自动落盘到共享目录供 worker 读取。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from api.deps import SkillServiceDep
from schemas.skill import (
    SkillCreate,
    SkillListOut,
    SkillOut,
    SkillUpdate,
)
from services.authz import Principal, require_roles

router = APIRouter(prefix="/admin/skills", tags=["admin-skills"])

# 仅企业管理员可操作 skill
AdminPrincipal = Annotated[Principal, Depends(require_roles("enterprise_admin"))]


@router.get("", response_model=SkillListOut)
async def list_skills(
    principal: AdminPrincipal,  # noqa: ARG001 — 权限校验
    service: SkillServiceDep,
) -> SkillListOut:
    """列出所有 skill（不含文件内容）。"""
    return await service.list_skills()


@router.post("", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
async def create_skill(
    payload: SkillCreate,
    principal: AdminPrincipal,
    service: SkillServiceDep,
) -> SkillOut:
    """新建 skill。"""
    return await service.create_skill(payload, principal)


@router.get("/{skill_id}", response_model=SkillOut)
async def get_skill(
    skill_id: str,
    principal: AdminPrincipal,  # noqa: ARG001
    service: SkillServiceDep,
) -> SkillOut:
    """获取 skill 详情（含文件内容）。"""
    result = await service.get_skill(skill_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return result


@router.put("/{skill_id}", response_model=SkillOut)
async def update_skill(
    skill_id: str,
    payload: SkillUpdate,
    principal: AdminPrincipal,  # noqa: ARG001
    service: SkillServiceDep,
) -> SkillOut:
    """编辑 skill（含启用/停用）。"""
    result = await service.update_skill(skill_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return result


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: str,
    principal: AdminPrincipal,  # noqa: ARG001
    service: SkillServiceDep,
) -> JSONResponse:
    """删除 skill。"""
    deleted = await service.delete_skill(skill_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return JSONResponse(status_code=204, content=None)
