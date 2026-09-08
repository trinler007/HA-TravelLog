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
