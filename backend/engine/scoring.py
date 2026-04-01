"""
Weighted layer scoring for match_mode='scored' schemes.
"""
from collections import defaultdict

LAYER_WEIGHTS = {2: 0.30, 3: 0.25, 4: 0.25, 5: 0.20}


def compute_scored_results(
    merged: dict,
    enabled_rules: list,
    top_n: int,
) -> list[tuple]:
    """
    merged:        {ts_code: {rule_id: bool}}
    enabled_rules: Rule objects with .id and .params ({"layer": N})
    top_n:         how many stocks to return

    Returns: [(ts_code, score), ...] sorted by score desc, capped at top_n.
    Layer 1 rules are hard filters (all must pass).
    Layers 2-5 are scored: layer_score = (matched/total) × layer_weight.
    """
    layer_rules: dict[int, list] = defaultdict(list)
    for r in enabled_rules:
        layer = int((r.params or {}).get("layer", 2))
        layer_rules[layer].append(r)

    layer1 = layer_rules.get(1, [])
    scored = []

    for ts, rule_res in merged.items():
        # Hard filter: all layer-1 rules must pass
        if layer1 and not all(rule_res.get(r.id, False) for r in layer1):
            continue

        score = 0.0
        for lnum, weight in LAYER_WEIGHTS.items():
            rules = layer_rules.get(lnum, [])
            if not rules:
                continue
            matched = sum(1 for r in rules if rule_res.get(r.id, False))
            score += (matched / len(rules)) * weight

        scored.append((ts, score))

    scored.sort(key=lambda x: -x[1])
    return scored[:top_n]
