"""Testes do que não depende de GTK: hook → arquivo → StateStore → Pet."""
import json
import os
import random
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from claude_pet.character import Pet, Rect  # noqa: E402
from claude_pet.config import Config  # noqa: E402
from claude_pet.state import StateStore  # noqa: E402

HOOK = ROOT / "hooks" / "claude_pet_hook.py"


class HookAndStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = dict(os.environ, CLAUDE_PET_HOME=self.tmp.name)
        self.store = StateStore(Config(), Path(self.tmp.name) / "sessions")

    def tearDown(self):
        self.tmp.cleanup()

    def fire(self, event, sid="s1", **extra):
        payload = dict(hook_event_name=event, session_id=sid, cwd="/home/x/meu-projeto", **extra)
        r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), text=True,
                           capture_output=True, env=self.env, timeout=5)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "")  # hook não pode falar no stdout (vira contexto do Claude)

    def status(self):
        top = self.store.top()
        return top.status if top else None

    def test_lifecycle(self):
        self.fire("SessionStart")
        self.assertEqual(self.status(), "idle")
        self.fire("UserPromptSubmit")
        self.assertEqual(self.status(), "thinking")
        self.fire("PreToolUse", tool_name="Bash")
        top = self.store.top()
        self.assertEqual((top.status, top.tool, top.project), ("working", "Bash", "meu-projeto"))
        self.fire("PostToolUse", tool_name="Bash")
        self.assertEqual(self.status(), "thinking")
        self.fire("Notification", message="Claude needs your permission", notification_type="permission_prompt")
        self.assertEqual(self.status(), "attention")
        self.fire("Stop")
        self.assertEqual(self.status(), "done")
        self.store.acknowledge(self.store.top())
        self.assertEqual(self.status(), "idle")
        self.fire("SessionEnd")
        self.assertIsNone(self.store.top())

    def test_idle_prompt_is_not_attention(self):
        self.fire("Stop")
        self.fire("Notification", message="waiting for input", notification_type="idle_prompt")
        self.assertEqual(self.status(), "done")

    def test_priority_across_sessions(self):
        self.fire("PreToolUse", sid="a", tool_name="Edit")
        self.fire("Notification", sid="b", message="perm", notification_type="permission_prompt")
        self.assertEqual(self.store.top().session_id, "b")

    def test_garbage_input_never_fails(self):
        r = subprocess.run([sys.executable, str(HOOK)], input="não é json", text=True,
                           capture_output=True, env=self.env, timeout=5)
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_thinking_times_out(self):
        self.fire("UserPromptSubmit")
        f = next((Path(self.tmp.name) / "sessions").glob("*.json"))
        d = json.loads(f.read_text())
        d["ts"] = time.time() - 10_000
        f.write_text(json.dumps(d))
        os.utime(f, (time.time() + 1, time.time() + 1))
        self.assertEqual(self.status(), "idle")


class PetTest(unittest.TestCase):
    def make(self):
        return Pet(Config(), Rect(0, 0, 1920, 1080), rng=random.Random(1))

    def test_falls_and_lands_on_floor(self):
        pet = self.make()
        for _ in range(200):
            f = pet.tick(1 / 30, "idle", None)
        self.assertEqual(pet.mode, "edge")
        self.assertEqual(f.y + pet.size, 1080)

    def test_perimeter_rotations(self):
        pet = self.make()
        w, h = pet.seg
        self.assertEqual(pet.edge_pos(10)[2], 0)
        self.assertEqual(pet.edge_pos(w + 10)[2], 270)
        self.assertEqual(pet.edge_pos(w + h + 10)[2], 180)
        self.assertEqual(pet.edge_pos(2 * w + h + 10)[2], 90)

    def test_drops_from_wall_when_claude_starts_working(self):
        pet = self.make()
        pet.mode, pet.s = "edge", pet.seg[0] + 200  # na parede direita
        for _ in range(200):
            f = pet.tick(1 / 30, "working", None)
        self.assertTrue(pet.on_floor)
        self.assertEqual(f.anim, "work")

    def test_click_vs_drag(self):
        pet = self.make()
        for _ in range(200):
            pet.tick(1 / 30, "idle", None)
        x, y = pet.position()
        pet.press(x + 40, y + 40)
        self.assertTrue(pet.release())          # clique
        pet.press(x + 40, y + 40)
        pet.motion(x + 300, y - 300)
        self.assertFalse(pet.release())         # arrastou
        self.assertEqual(pet.mode, "free")


if __name__ == "__main__":
    unittest.main()


class SkinTest(unittest.TestCase):
    def test_every_skin_has_every_animation(self):
        from claude_pet import skins
        from claude_pet.sprites import ANIMATIONS
        import cairo
        for name in skins.available():
            skin = skins.load(name)
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, skin.canvas * 2, skin.canvas * 2)
            for anim in ANIMATIONS:
                _fps, n = skin.anim_info(anim)
                for i in range(n):
                    skin.draw(cairo.Context(surf), anim, i, -1, "attention", 2, "#5ec4b6")


class SwingTest(unittest.TestCase):
    def test_dragging_right_leans_body_left_then_settles(self):
        from claude_pet import skins
        import claude_pet.character as C
        t = [0.0]
        orig = C.time.monotonic
        C.time.monotonic = lambda: t[0]
        try:
            pet = Pet(Config(), Rect(0, 0, 1920, 1080), rng=random.Random(1), skin=skins.load())
            pet.press(500, 500)
            for k in range(20):
                t[0] += 1 / 30
                pet.motion(500 + 25 * k, 500)
                f = pet.tick(1 / 30, "idle", None)
            self.assertLess(f.lean, -0.1)          # corpo ficou pra trás
            for _ in range(60):
                t[0] += 1 / 30
                pet.motion(500 + 25 * 19, 500)    # parou de mexer
                f = pet.tick(1 / 30, "idle", None)
            self.assertLess(abs(f.lean), 0.05)    # e voltou a ficar reto
        finally:
            C.time.monotonic = orig


class DragStopTest(unittest.TestCase):
    def test_stop_then_release_does_not_throw_or_lean(self):
        import claude_pet.character as C
        t = [0.0]
        orig = C.time.monotonic
        C.time.monotonic = lambda: t[0]
        try:
            pet = Pet(Config(), Rect(0, 0, 1920, 1080), rng=random.Random(1))
            pet.press(500, 500)
            for k in range(10):                      # puxa rápido
                t[0] += 1 / 60
                pet.motion(500 + 60 * k, 500)
                pet.tick(1 / 60, "idle", None)
            for _ in range(60):                      # para, segurando, sem eventos de movimento
                t[0] += 1 / 30
                f = pet.tick(1 / 30, "idle", None)
            self.assertLess(abs(f.lean), 0.05)
            self.assertFalse(pet.release())          # foi arraste, não clique
            self.assertEqual((pet.vx, pet.vy), (0.0, 0.0))
        finally:
            C.time.monotonic = orig
