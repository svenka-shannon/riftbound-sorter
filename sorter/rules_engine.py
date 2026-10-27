"""
Rules engine — maps a card's attributes to a bin number.

Loads config/rules.json. Rules are evaluated top-to-bottom; first match wins.
Each rule has a 'match' dict with field:value pairs (all must match).
If a 'default' key is present and True, the rule matches everything.

Usage:
    engine = RulesEngine("config/rules.json")
    bin_num = engine.assign_bin(card_data)
"""

import json
from pathlib import Path


class RulesEngine:
    def __init__(self, rules_path: str | Path = "config/rules.json"):
        self.rules_path = Path(rules_path)
        self.rules: list[dict] = []
        self.bin_count: int = 8
        self.reject_bin: int = 9
        self.load()

    def load(self):
        """Load (or reload) rules from JSON file."""
        config = json.loads(self.rules_path.read_text())
        self.rules      = config.get("rules", [])
        self.bin_count  = config.get("_bin_count", 8)
        self.reject_bin = config.get("_reject_bin", 9)
        print(f"[rules_engine] Loaded {len(self.rules)} rules, {self.bin_count} bins")

    def assign_bin(self, card: dict) -> int:
        """
        Evaluate rules against card attributes.
        Returns bin number (int). Returns reject_bin if no rule matches.

        card dict example:
          {"riftbound_id": "rb_001", "name": "Jinx", "type": "Champion",
           "rarity": "Legendary", "domain": "Noxus", ...}
        """
        for rule in self.rules:
            match = rule.get("match", {})

            if match.get("default"):
                return rule["bin"]

            matched = True
            for field, expected in match.items():
                if field == "default":
                    continue
                actual = card.get(field)
                if isinstance(expected, list):
                    if actual not in expected:
                        matched = False
                        break
                else:
                    if actual != expected:
                        matched = False
                        break

            if matched:
                return rule["bin"]

        return self.reject_bin

    def describe_bin(self, bin_num: int) -> str:
        """Return the rule name for a bin number."""
        for rule in self.rules:
            if rule.get("bin") == bin_num:
                return rule.get("name", f"Bin {bin_num}")
        if bin_num == self.reject_bin:
            return "Reject"
        return f"Bin {bin_num}"
