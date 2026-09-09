"""Validate supplied assets and their object bindings."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def test_display_assets_match():
    objects = [
        json.loads(line)
        for line in (ROOT / "examples/openhasp/pages.jsonl").read_text().splitlines()
    ]
    ids = {f"p{o['page']}b{o['id']}" for o in objects}
    package = yaml.safe_load((ROOT / "examples/openhasp/package.yaml").read_text())
    assert len(ids) == len(objects)
    for binding in package["openhasp"]["fahrerhaus"]["objects"]:
        assert binding["obj"] in ids
    for obj in objects:
        assert obj["x"] + obj["w"] <= 320
        assert obj["y"] + obj["h"] <= 480
    assert package["script"]["travellog_display_save"]["mode"] == "single"


def test_json_and_yaml_parse():
    for path in ROOT.rglob("*.json"):
        if any(p.startswith(".") for p in path.relative_to(ROOT).parts):
            continue
        json.loads(path.read_text(encoding="utf-8"))
    for path in (ROOT / "examples").rglob("*.yaml"):
        yaml.safe_load(path.read_text(encoding="utf-8"))


def test_480_geometry_and_bindings():
    base = ROOT / "examples/openhasp/480x480"
    rows = [json.loads(line) for line in (base / "travellog-pages.jsonl").read_text().splitlines()]
    objects = [row for row in rows if row["id"] != 0]
    ids = {f"p{o['page']}b{o['id']}" for o in objects}
    assert len(ids) == len(objects)
    assert {o["page"] for o in objects} == {6, 7, 8}
    for obj in objects:
        assert 0 <= obj["x"] < obj["x"] + obj["w"] <= 480
        assert 55 <= obj["y"] < obj["y"] + obj["h"] <= 420
    bindings = yaml.safe_load((base / "objects.yaml").read_text())
    assert len({b["obj"] for b in bindings}) == len(bindings)
    for binding in bindings:
        assert binding["obj"] in ids
    bound_events = {b["obj"] for b in bindings if "event" in b}
    for obj in objects:
        if obj["obj"] in ("btn", "btnmatrix", "checkbox"):
            assert f"p{obj['page']}b{obj['id']}" in bound_events or "action" in obj
    nav = {row["page"]: row for row in rows if row["id"] == 0}
    assert nav[1]["prev"] == 6 and nav[5]["next"] == 6
    assert nav[6]["prev"] == 5 and nav[6]["next"] == 1
