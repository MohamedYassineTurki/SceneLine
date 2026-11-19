"""Garanties critiques de SceneLine, sans appel à un fournisseur externe."""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Le Python minimal du CI peut ne pas avoir OpenCV. Les fonctions testées ici
# n'en ont pas besoin ; ce module factice permet seulement de charger les
# modules, tandis que le vrai traitement vidéo du dernier test passe par FFmpeg.
try:
    import cv2  # noqa: F401
except ModuleNotFoundError:
    sys.modules["cv2"] = types.ModuleType("cv2")

from generation import pipeline  # noqa: E402
from integration import render  # noqa: E402
from product_matcher.matching import rule_check  # noqa: E402
from producer_review.revision_digest import REVISION_DIGEST_VERSION, digest  # noqa: E402
from video_analyzer.context import build_context  # noqa: E402
from video_analyzer.understand import make_windows  # noqa: E402


def revision():
    return {
        "n": 1,
        "product_id": "eau-1",
        "start_ms": 1_500,
        "end_ms": 3_500,
        "mode": "objet_pose",
        "scale": 0.7,
        "surface": "Comptoir en inox",
        "region": {"x": 0.58, "y": 0.62, "width": 0.22, "height": 0.14},
        "starts_on_cut": True,
        "ends_on_cut": True,
        "reference_frame": "win-1-1.jpg",
    }


def decision_for_revision(item):
    return {
        "id": "d-1",
        "proposal_id": "p-1-1",
        "revision": item["n"],
        "revision_digest": digest(item),
        "revision_digest_version": REVISION_DIGEST_VERSION,
        "action": "accepter",
        "reviewer": "Test technique",
        "comment": "",
        "payload": None,
        "at": "2026-01-01T00:00:00+00:00",
    }


class Form(dict):
    """Petit équivalent du MultiDict Flask pour tester le formulaire."""

    def getlist(self, key):
        value = self.get(key, [])
        return value if isinstance(value, list) else [value]


def valid_form():
    return Form({
        "consent_processing": "on",
        "consent_provider": "on",
        "work_type": "Série",
        "location": "Tunis",
        "period": "Contemporaine",
        "languages": "Français, darija",
        "intention": "Montrer le quotidien du restaurant",
        "transcription": "fr",
        "excluded_categories": [],
    })


def product(category="boisson_sans_alcool", modes=None, size="moyen", era="intemporel"):
    return {
        "id": "eau-1",
        "declared": {
            "category": category,
            "modes": modes or ["objet_pose"],
            "size_class": size,
            "dimensions": "30 cm",
            "exclusions": "",
            "origin": "Tunisie",
            "markets": ["Tunisie"],
        },
        "analysis": {"era_constraint": era, "sensitive_flags": []},
        "corrections": {},
    }


def executable_works(name):
    path = shutil.which(name)
    if not path:
        return False
    return subprocess.run([path, "-version"], capture_output=True).returncode == 0


class ProtectedSceneTests(unittest.TestCase):
    def test_protected_scenes_never_create_windows(self):
        shots = [
            {"id": 1, "start_ms": 0, "end_ms": 8_000},
            {"id": 2, "start_ms": 8_000, "end_ms": 16_000},
        ]
        scenes = [
            {"id": 1, "shot_ids": [1], "protection": "protected"},
            {"id": 2, "shot_ids": [2], "protection": "clear"},
        ]
        windows, skipped = make_windows(shots, scenes)
        self.assertEqual([window["shot_id"] for window in windows], [2])
        self.assertEqual(skipped, 1)

    def test_creator_excluded_interval_is_not_reviewed(self):
        shots = [{"id": 1, "start_ms": 0, "end_ms": 8_000}]
        scenes = [{"id": 1, "shot_ids": [1], "protection": "clear"}]
        windows, skipped = make_windows(shots, scenes, [{"start_ms": 1_000, "end_ms": 2_000}])
        self.assertEqual(windows, [])
        self.assertEqual(skipped, 1)


class MatchingRuleTests(unittest.TestCase):
    def setUp(self):
        self.opp = {"start_ms": 1_000, "end_ms": 8_000, "placement_mode": "objet_pose",
                    "avoid_categories": []}
        self.scene = {"period": "Contemporaine"}

    def test_creator_excluded_category_is_rejected_before_gemini(self):
        reason = rule_check(self.opp, self.scene, product(), {"excluded_categories": ["boisson_sans_alcool"]})
        self.assertIn("Catégorie exclue", reason)

    def test_incompatible_mode_is_rejected(self):
        reason = rule_check(self.opp, self.scene, product(modes=["affiche_murale"]), {})
        self.assertIn("n'admet pas le mode", reason)

    def test_large_object_on_surface_is_rejected(self):
        reason = rule_check(self.opp, self.scene, product(size="grand"), {})
        self.assertIn("trop grand", reason)

    def test_contemporary_only_product_is_rejected_in_historical_scene(self):
        scene = {"period": "Paris, années 1950"}
        reason = rule_check(self.opp, scene, product(era="contemporain_seulement"), {})
        self.assertIn("scène d'époque", reason)

    def test_compatible_pair_passes_the_written_rules(self):
        self.assertIsNone(rule_check(self.opp, self.scene, product(), {}))


class ConsentTests(unittest.TestCase):
    def test_processing_consent_is_required(self):
        form = valid_form()
        form.pop("consent_processing")
        with self.assertRaisesRegex(ValueError, "autorisé à traiter"):
            build_context(form)

    def test_provider_consent_is_required(self):
        form = valid_form()
        form.pop("consent_provider")
        with self.assertRaisesRegex(ValueError, "envoi d'images"):
            build_context(form)

    def test_valid_consents_are_recorded_with_a_timestamp(self):
        context = build_context(valid_form())
        self.assertTrue(context["consent"]["processing"])
        self.assertTrue(context["consent"]["provider"])
        self.assertIn("Google Gemini", context["consent"]["provider_name"])
        self.assertTrue(context["consent"]["at"].endswith("+00:00"))

    def test_generation_pipeline_requires_placement_consent(self):
        with self.assertRaisesRegex(pipeline.PipelineError, "autorisation"):
            pipeline.start(Path("unused"), "p-1-1", False)


class ApprovedRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.item = revision()
        (self.folder / "proposals.json").write_text(json.dumps({
            "proposals": {"p-1-1": {"id": "p-1-1", "revisions": [self.item]}}
        }), encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def write_decisions(self, decisions):
        (self.folder / "decisions.json").write_text(
            json.dumps({"decisions": decisions}), encoding="utf-8")

    def test_revision_without_acceptance_cannot_be_rendered(self):
        self.write_decisions([])
        with self.assertRaisesRegex(render.RenderError, "révision approuvée"):
            render.approved_revision(self.folder, "p-1-1")

    def test_matching_acceptance_unlocks_the_exact_revision(self):
        self.write_decisions([decision_for_revision(self.item)])
        _, approved, decision = render.approved_revision(self.folder, "p-1-1")
        self.assertEqual(approved, self.item)
        self.assertEqual(decision["reviewer"], "Test technique")

    def test_moving_the_product_invalidates_the_acceptance(self):
        self.write_decisions([decision_for_revision(self.item)])
        moved = deepcopy(self.item)
        moved["region"]["x"] = 0.18
        (self.folder / "proposals.json").write_text(json.dumps({
            "proposals": {"p-1-1": {"id": "p-1-1", "revisions": [moved]}}
        }), encoding="utf-8")
        with self.assertRaisesRegex(render.RenderError, "révision approuvée"):
            render.approved_revision(self.folder, "p-1-1")


class OriginalAndAudioTests(unittest.TestCase):
    def test_assembly_never_rewrites_source_and_maps_its_audio(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / "source.mp4"
            generated = folder / "generated.mp4"
            source.write_bytes(b"original-intact")
            generated.write_bytes(b"generated-plan")
            source_before = hashlib.sha256(source.read_bytes()).hexdigest()
            item = revision()
            approval = decision_for_revision(item)

            def fake_probe(path):
                return {"width": 320, "height": 240,
                        "duration": 5.0 if Path(path).name == "source.mp4" else 2.0,
                        "has_audio": Path(path).name == "source.mp4"}

            with patch.object(render, "approved_revision", return_value=({"id": "p-1-1"}, item, approval)), \
                    patch.object(render, "product_of", return_value={"id": "eau-1", "name": "Bouteille d'eau"}), \
                    patch.object(render, "probe", side_effect=fake_probe), \
                    patch.object(render, "bar_crop", return_value=None), \
                    patch.object(render, "ffmpeg") as ffmpeg_call:
                record = render.assemble(folder, "p-1-1", generated, "Test", "", lead_ms=1_000)

            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_before)
            self.assertEqual(record["audio"], "audio de la source conservé")
            self.assertEqual(ffmpeg_call.call_count, 2)
            edited_command = ffmpeg_call.call_args_list[1].args
            audio_map = edited_command.index("-map", edited_command.index("-map") + 1)
            self.assertEqual(edited_command[audio_map + 1], "0:a:0?")
            self.assertTrue(all(Path(call.args[-1]) != source for call in ffmpeg_call.call_args_list))


@unittest.skipUnless(executable_works("ffmpeg") and executable_works("ffprobe"),
                     "FFmpeg/FFprobe absents ou non exécutables")
class OriginalAndAudioFFmpegIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.source = self.folder / "source.mp4"
        self.generated = self.folder / "generated.mp4"
        subprocess.run([
            "ffmpeg", "-nostdin", "-v", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
            "-t", "5", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(self.source),
        ], check=True)
        subprocess.run([
            "ffmpeg", "-nostdin", "-v", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25",
            "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(self.generated),
        ], check=True)

    def tearDown(self):
        self.temporary.cleanup()

    def test_assembly_keeps_source_unchanged_and_uses_source_audio(self):
        source_before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        item = revision()
        approval = decision_for_revision(item)
        with patch.object(render, "approved_revision", return_value=({"id": "p-1-1"}, item, approval)), \
                patch.object(render, "product_of", return_value={"id": "eau-1", "name": "Bouteille d'eau"}):
            record = render.assemble(self.folder, "p-1-1", self.generated, "Test", "", lead_ms=1_000)

        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), source_before)
        self.assertEqual(record["audio"], "audio de la source conservé")
        self.assertTrue(render.probe(self.folder / record["original"])["has_audio"])
        self.assertTrue(render.probe(self.folder / record["edited"])["has_audio"])
        self.assertEqual(record["source_interval"], {"start_ms": 1_500, "end_ms": 3_500})


if __name__ == "__main__":
    unittest.main()
