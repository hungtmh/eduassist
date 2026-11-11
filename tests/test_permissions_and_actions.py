"""Phân quyền theo vai trò, danh sách Cấm của agent, sửa đề xuất, kiểm chứng số liệu LLM viết (không cần DB)."""

import pytest

from eduassist.background.base import numbers_faithful
from eduassist.services.actions import ACTIONS, FORBIDDEN_FOREVER, apply_edits
from eduassist.services.core import AGENT_FORBIDDEN, PERMISSIONS, Actor, Forbidden, RuleViolation, has_perm, require


@pytest.mark.parametrize("perm", sorted(AGENT_FORBIDDEN))
def test_agents_never_get_forbidden_permissions_even_as_manager(perm):
    agent = Actor("agent:x", "manager", is_agent=True)
    assert not has_perm(agent, perm)
    with pytest.raises(Forbidden, match="Agent không bao giờ"):
        require(agent, perm)
    assert has_perm(Actor("quanly", "manager"), perm)  # con người cùng vai trò thì được


@pytest.mark.parametrize(
    ("role", "perm", "ok"),
    [
        ("student", "invoice.read", False),
        ("teacher", "class.read", False),
        ("teacher", "attendance.write", True),
        ("consultant", "payment.record", False),
        ("accountant", "payment.record", True),
        ("academic", "class.write", True),
        ("consultant", "class.write", False),
        ("accountant", "autonomy.write", False),
        ("manager", "autonomy.write", True),
    ],
)
def test_role_permissions(role, perm, ok):
    assert has_perm(Actor("u", role), perm) is ok


def test_student_has_no_staff_permissions():
    assert PERMISSIONS["student"] == {"portal"}


def test_forbidden_actions_have_no_executor():
    assert {"ghi_nhan_thanh_toan", "sua_diem", "xoa_du_lieu", "doi_quyen"} == FORBIDDEN_FOREVER
    assert all(ACTIONS[k].execute is None for k in FORBIDDEN_FOREVER)


def test_every_action_perm_exists_for_some_role():
    all_perms = set().union(*PERMISSIONS.values())
    assert all(a.perm in all_perms for a in ACTIONS.values())


def test_edit_keeps_subset_of_items():
    data = {"items": [{"dot_id": 1}, {"dot_id": 2}, {"dot_id": 3}], "loi_nhan_them": ""}
    new = apply_edits(ACTIONS["nhac_no_tiep"], data, {"keep_items": [1, 3], "loi_nhan_them": "Gọi 1900 0000"})
    assert [i["dot_id"] for i in new["items"]] == [1, 3]
    assert new["loi_nhan_them"] == "Gọi 1900 0000"
    assert len(data["items"]) == 3  # không sửa tại chỗ


def test_edit_cannot_add_items_or_touch_other_fields():
    data = {"items": [{"dot_id": 1}]}
    assert apply_edits(ACTIONS["nhac_no_tiep"], data, {"keep_items": [1, 99]})["items"] == [{"dot_id": 1}]
    with pytest.raises(RuleViolation):
        apply_edits(ACTIONS["nhac_no_tiep"], data, {"keep_items": [99]})
    with pytest.raises(RuleViolation):
        apply_edits(ACTIONS["cap_voucher"], {"hoc_vien_id": 1, "phan_tram": 10}, {"hoc_vien_id": 2})


def test_llm_numbers_must_come_from_input():
    src = "Doanh thu: 12.500.000đ (tuần trước 9.800.000đ)"
    assert numbers_faithful("Doanh thu tăng lên 12.500.000đ.", src)
    assert not numbers_faithful("Doanh thu đạt 12.800.000đ.", src)
