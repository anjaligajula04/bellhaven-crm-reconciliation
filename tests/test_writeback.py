import ast
from pathlib import Path

import pytest


# Load only the functions we need from writeback_live.py.
# This avoids importing the API configuration or making CRM requests.
source_path = Path(__file__).resolve().parents[1] / "writeback_live.py"
tree = ast.parse(source_path.read_text(encoding="utf-8-sig"))

required_functions = {"same_number", "verify_original_account"}
selected = [
    node for node in tree.body
    if isinstance(node, ast.FunctionDef)
    and node.name in required_functions
]

namespace = {"PARENT_ID": "BELLHAVEN_PARENT"}

exec(
    compile(ast.Module(body=selected, type_ignores=[]), str(source_path), "exec"),
    namespace,
)

verify_original_account = namespace["verify_original_account"]


def make_account(parent_id):
    return {
        "name": "Test Facility",
        "parent_id": parent_id,
        "lifetime_revenue": 100,
        "outstanding_ar": 0,
    }


def make_config(action):
    return {
        "name": "Test Facility",
        "parent_before": "OLD_PARENT",
        "revenue": 100,
        "ar": 0,
        "action": action,
    }


def test_reparent_accepts_original_parent():
    verify_original_account(
        make_account("OLD_PARENT"),
        make_config("REPARENT"),
    )


def test_reparent_accepts_bellhaven_parent():
    verify_original_account(
        make_account("BELLHAVEN_PARENT"),
        make_config("REPARENT"),
    )


def test_reparent_rejects_unexpected_parent():
    with pytest.raises(RuntimeError):
        verify_original_account(
            make_account("OTHER_PARENT"),
            make_config("REPARENT"),
        )


def test_create_and_link_requires_original_parent():
    with pytest.raises(RuntimeError):
        verify_original_account(
            make_account("BELLHAVEN_PARENT"),
            make_config("CREATE_AND_LINK"),
        )