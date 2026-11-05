import ast
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from rapidfuzz import fuzz


ROOT = Path(__file__).resolve().parents[1]
MATCHER_FILE = ROOT / "matcher.py"


@pytest.fixture(scope="module")
def matcher():
    source = ast.parse(MATCHER_FILE.read_text(encoding="utf-8"))

    required_functions = {
        "clean",
        "normalize_text",
        "digits",
        "similarity",
        "parse_website_address",
        "score_candidate",
    }

    selected_nodes = []

    for node in source.body:
        if isinstance(node, ast.FunctionDef):
            if node.name in required_functions:
                selected_nodes.append(node)

        elif isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name)
                and target.id == "STREET_ENDINGS"
                for target in node.targets
            ):
                selected_nodes.append(node)

    namespace = {
        "re": re,
        "fuzz": fuzz,
    }

    module = ast.Module(
        body=selected_nodes,
        type_ignores=[],
    )

    exec(compile(module, str(MATCHER_FILE), "exec"), namespace)

    return SimpleNamespace(**{
        name: namespace[name]
        for name in required_functions
    })


def test_clean_handles_empty_values(matcher):
    assert matcher.clean(None) == ""
    assert matcher.clean("  Lima  ") == "Lima"


def test_normalize_text_standardizes_addresses(matcher):
    assert matcher.normalize_text(
        "1800 North Main Street"
    ) == "1800 n main st"


def test_digits_extracts_phone_numbers(matcher):
    assert matcher.digits("(614) 337-1967") == "6143371967"


def test_similarity_returns_100_for_identical_names(matcher):
    assert matcher.similarity(
        "Bellhaven of Lima",
        "Bellhaven of Lima"
    ) == 100.0


def test_similarity_returns_zero_for_empty_values(matcher):
    assert matcher.similarity("", "Bellhaven of Lima") == 0.0


def test_parse_website_address(matcher):
    result = matcher.parse_website_address(
        "210 Orchard Lane Maplewood, OH 44280"
    )

    assert result == {
        "street": "210 Orchard Lane",
        "city": "Maplewood",
        "state": "OH",
        "zip": "44280",
    }


def test_parse_owosso_address(matcher):
    result = matcher.parse_website_address(
        "1120 W Main St Owosso, MI 48867"
    )

    assert result["street"] == "1120 W Main St"
    assert result["city"] == "Owosso"
    assert result["state"] == "MI"
    assert result["zip"] == "48867"


def test_parse_invalid_address(matcher):
    result = matcher.parse_website_address(
        "Address unavailable"
    )

    assert result["street"] == ""
    assert result["city"] == ""
    assert result["state"] == ""
    assert result["zip"] == ""


def test_score_candidate_exact_location(matcher):
    website = {
        "name": "Bellhaven Crossings of Lima",
        "full_address": "3115 N Cole St Lima, OH 45801",
    }

    account = {
        "name": "Bellhaven Crossings of Lima",
        "billing_street": "3115 N Cole St",
        "billing_city": "Lima",
        "billing_state": "OH",
        "billing_zip": "45801",
    }

    result = matcher.score_candidate(website, account)

    assert result["match_score"] == 100.0
    assert result["name_score"] == 100.0
    assert result["location_match"] is True
    assert result["address_conflicts"] == []


def test_score_candidate_detects_state_mismatch(matcher):
    website = {
        "name": "Bellhaven Crossings of Lima",
        "full_address": "3115 N Cole St Lima, OH 45801",
    }

    account = {
        "name": "Bellhaven Crossings of Lima",
        "billing_street": "3115 N Cole St",
        "billing_city": "Lima",
        "billing_state": "MI",
        "billing_zip": "48867",
    }

    result = matcher.score_candidate(website, account)

    assert result["location_match"] is False
    assert "State mismatch" in result["address_conflicts"]
    assert "ZIP code mismatch" in result["address_conflicts"]
