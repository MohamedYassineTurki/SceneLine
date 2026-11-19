"""Tests de l'empreinte qui relie une décision à sa révision."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from producer_review.revision_digest import (  # noqa: E402
    REVISION_DIGEST_VERSION,
    decision_matches_revision,
    digest,
)


def revision():
    return {
        "n": 2,
        "product_id": "product-1",
        "start_ms": 30_000,
        "end_ms": 40_000,
        "mode": "objet_pose",
        "scale": 0.7,
        "surface": "Comptoir en inox",
        "region": {"x": 0.58, "y": 0.62, "width": 0.22, "height": 0.14},
        "starts_on_cut": True,
        "ends_on_cut": True,
        "reference_frame": "win-12-1.jpg",
    }


class RevisionDigestTests(unittest.TestCase):
    def test_v2_is_a_complete_sha256(self):
        value = digest(revision())
        self.assertEqual(len(value), 64)
        self.assertTrue(all(character in "0123456789abcdef" for character in value))

    def test_moving_the_region_changes_the_digest(self):
        original = revision()
        moved = deepcopy(original)
        moved["region"]["x"] = 0.18
        self.assertNotEqual(digest(original), digest(moved))

    def test_changing_the_surface_changes_the_digest(self):
        original = revision()
        changed = dict(original, surface="Étagère murale")
        self.assertNotEqual(digest(original), digest(changed))

    def test_region_key_order_does_not_change_the_digest(self):
        original = revision()
        reordered = deepcopy(original)
        reordered["region"] = {"height": 0.14, "width": 0.22, "y": 0.62, "x": 0.58}
        self.assertEqual(digest(original), digest(reordered))

    def test_v2_decision_stops_matching_after_a_position_change(self):
        original = revision()
        decision = {
            "proposal_id": "p-12-1",
            "revision": 2,
            "action": "accepter",
            "revision_digest_version": REVISION_DIGEST_VERSION,
            "revision_digest": digest(original),
        }
        self.assertTrue(decision_matches_revision(decision, original))
        moved = deepcopy(original)
        moved["region"]["x"] = 0.18
        self.assertFalse(decision_matches_revision(decision, moved))

    def test_legacy_decisions_remain_readable(self):
        original = revision()
        self.assertEqual(digest(original, version=1), "f2aedfff15204b8f")
        decision = {
            "proposal_id": "p-12-1",
            "revision": 2,
            "action": "accepter",
            "revision_digest": digest(original, version=1),
        }
        self.assertTrue(decision_matches_revision(decision, original))


if __name__ == "__main__":
    unittest.main()
