"""Marca no pack.json as regiões de pés e braços de cada pose (para as animações de membros).

    python3 tools/auto_parts.py pato [--feet 0.2] [--arm-top 0.42] [--arm-bottom 0.78] [--arm-width 0.2]

Pés: faixa de baixo do desenho, dividida ao meio. Braços: faixas laterais na altura do tronco.
Os valores podem ser ajustados por pose depois, editando o pack.json.
"""
import argparse
import json
from pathlib import Path

PACKS = Path(__file__).resolve().parents[1] / "claude_pet" / "packs"

# ajuste fino por personagem/pose: braço = (topo, base, largura) em fração do desenho; None = sem braço
PRESETS = {
    "pato": {"alert": (0.05, 0.6, 0.24), "done": (0.05, 0.6, 0.24), "working": (0.45, 0.85, 0.2)},
    "capivara": {"*": None, "alert": (0.45, 0.72, 0.2), "grabbed": (0.45, 0.72, 0.2)},
    "slime": {"*": (0.5, 0.92, 0.18), "done": None},
}


def parts_for(bbox, feet, arm):
    bx, by, bw, bh = bbox
    fh = max(3, round(bh * feet))
    half = bw // 2
    parts = {
        "footL": [bx, by + bh - fh, half, fh],
        "footR": [bx + half, by + bh - fh, bw - half, fh],
    }
    if arm:
        arm_top, arm_bottom, arm_width = arm
        aw = max(3, round(bw * arm_width))
        ay0, ay1 = by + round(bh * arm_top), by + round(bh * arm_bottom)
        parts["armL"] = [bx, ay0, aw, ay1 - ay0]
        parts["armR"] = [bx + bw - aw, ay0, aw, ay1 - ay0]
    return parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--feet", type=float, default=0.2)
    ap.add_argument("--arm-top", type=float, default=0.42)
    ap.add_argument("--arm-bottom", type=float, default=0.78)
    ap.add_argument("--arm-width", type=float, default=0.2)
    a = ap.parse_args()
    path = PACKS / a.name / "pack.json"
    meta = json.loads(path.read_text())
    preset = PRESETS.get(a.name, {})
    default = preset.get("*", (a.arm_top, a.arm_bottom, a.arm_width))
    for pose, info in meta["frames"].items():
        info["parts"] = parts_for(info["bbox"], a.feet, preset.get(pose, default))
    path.write_text(json.dumps(meta, indent=1))
    print(path)


if __name__ == "__main__":
    main()
