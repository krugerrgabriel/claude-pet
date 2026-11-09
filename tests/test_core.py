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

    def age_work(self, seconds=60):
        """Finge que a última ferramenta começou há `seconds` (passa do debounce)."""
        f = next((Path(self.tmp.name) / "sessions").glob("*.json"))
        d = json.loads(f.read_text())
        d["work_ts"] = time.time() - seconds
        f.write_text(json.dumps(d))
        os.utime(f, (time.time() + 1, time.time() + 1))

    def raw(self):
        return json.loads(next((Path(self.tmp.name) / "sessions").glob("*.json")).read_text())

    def test_working_is_held_for_a_few_seconds(self):
        self.fire("UserPromptSubmit")
        self.fire("PreToolUse", tool_name="Read")
        self.fire("PostToolUse", tool_name="Read")
        self.assertEqual(self.status(), "working")
        self.age_work(self.store.cfg.work_hold - 1)
        self.assertEqual(self.status(), "working")
        self.age_work(self.store.cfg.work_hold + 0.5)
        self.assertEqual(self.status(), "thinking")
        self.fire("Stop")                             # terminar não espera o debounce
        self.assertEqual(self.status(), "done")

    def test_background_subagents_do_not_flicker_done(self):
        """Conversa dispara subagentes em segundo plano e para; só termina de verdade no fim."""
        self.fire("UserPromptSubmit", prompt="faz X")
        self.fire("PreToolUse", tool_name="Agent")
        self.fire("PostToolUse", tool_name="Agent")
        self.fire("SubagentStart", agent_id="a1", agent_type="fork")
        self.fire("SubagentStart", agent_id="a2", agent_type="fork")
        self.fire("Stop")                             # a conversa parou, mas os subagentes seguem
        self.assertEqual(self.status(), "working")
        self.fire("PreToolUse", agent_id="a1", tool_name="Bash")
        self.fire("PostToolUse", agent_id="a1", tool_name="Bash")
        self.fire("SubagentStop", agent_id="a1")
        self.assertEqual(self.status(), "working")     # a2 ainda trabalhando
        self.fire("UserPromptSubmit", prompt="<task-notification>a1 terminou</task-notification>")
        self.fire("Stop")                             # revisou o a1 e parou de novo: ainda não terminou
        self.assertEqual(self.status(), "working")
        self.fire("SubagentStop", agent_id="a2")
        self.assertNotEqual(self.status(), "done")     # vai ser acordado pelo aviso do a2
        self.fire("UserPromptSubmit", prompt="<task-notification>a2 terminou</task-notification>")
        self.fire("Stop")
        self.assertEqual(self.status(), "done")        # agora sim
        self.assertEqual(self.raw()["agents"], {})

    def test_late_subagent_stop_does_not_leave_it_thinking(self):
        """Corrida: o aviso do subagente chega e a conversa termina ANTES do SubagentStop dele."""
        self.fire("UserPromptSubmit", prompt="faz X")
        self.fire("SubagentStart", agent_id="a1")
        self.fire("UserPromptSubmit", prompt='<agent-message from="a1">ok')
        self.fire("Stop")
        self.fire("SubagentStop", agent_id="a1")        # chega atrasado
        self.assertEqual(self.status(), "thinking")     # por uns segundos espera o Claude ser acordado...
        f = next((Path(self.tmp.name) / "sessions").glob("*.json"))
        d = json.loads(f.read_text())
        d["waking_until"] = time.time() - 1             # ...ninguém acordou
        f.write_text(json.dumps(d))
        os.utime(f, (time.time() + 1, time.time() + 1))
        self.assertEqual(self.status(), "done")         # então terminou mesmo, não fica "pensando"

    def test_seen_done_stays_seen_after_late_events(self):
        self.fire("Stop")
        self.store.acknowledge(self.store.top())
        self.fire("SubagentStart", agent_id="a1")
        self.fire("SubagentStop", agent_id="a1")
        f = next((Path(self.tmp.name) / "sessions").glob("*.json"))
        d = json.loads(f.read_text())
        d["waking_until"] = time.time() - 1
        f.write_text(json.dumps(d))
        os.utime(f, (time.time() + 1, time.time() + 1))
        self.assertEqual(self.status(), "idle")          # o "terminou" que você já viu não volta

    def test_active_chat_still_shows_thinking_while_subagent_runs(self):
        self.fire("UserPromptSubmit")
        self.fire("SubagentStart", agent_id="a1")
        self.fire("PreToolUse", agent_id="a1", tool_name="Bash")
        self.age_work()
        self.assertEqual(self.status(), "thinking")    # a conversa está pensando; o subagente não esconde isso

    def test_subagent_permission_request_is_attention(self):
        self.fire("UserPromptSubmit")
        self.fire("SubagentStart", agent_id="a1")
        self.fire("Notification", agent_id="a1", message="Claude needs your permission to use Bash",
                  notification_type="permission_prompt")
        self.assertEqual(self.status(), "attention")
        self.fire("PreToolUse", agent_id="a1", tool_name="Bash")   # você aprovou
        self.assertEqual(self.status(), "working")

    def test_task_notification_is_not_your_prompt(self):
        self.fire("UserPromptSubmit", prompt="oi")
        ts = self.raw()["prompt_ts"]
        self.fire("Stop")
        self.fire("UserPromptSubmit", prompt="<task-notification>\n<task-id>x</task-id>")
        self.fire("UserPromptSubmit", prompt='<agent-message from="a1">\n[Subagent hand-back]')
        self.assertEqual(self.raw()["prompt_ts"], ts)   # não acorda o pet do "botar pra dormir"

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
        self.assertEqual(self.status(), "working")   # debounce: segura "trabalhando" logo depois da ferramenta
        self.age_work()
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

    def test_prompt_ts_only_moves_on_prompt(self):
        self.fire("SessionStart")
        self.assertEqual(self.store.top().prompt_ts, 0)
        self.fire("UserPromptSubmit")
        ts = self.store.top().prompt_ts
        self.assertGreater(ts, 0)
        self.fire("PreToolUse", tool_name="Bash")
        self.fire("Stop")
        self.assertEqual(self.store.top().prompt_ts, ts)

    def test_ack_survives_pet_restart(self):
        self.fire("Stop")
        self.store.acknowledge(self.store.top())
        fresh = StateStore(Config(), Path(self.tmp.name) / "sessions")
        self.assertEqual(fresh.top().status, "idle")
        self.fire("Stop")  # terminou de novo: aparece outra vez
        self.assertEqual(fresh.top().status, "done")

    def test_ack_is_pruned_after_session_end(self):
        self.fire("Stop")
        self.store.acknowledge(self.store.top())
        self.fire("SessionEnd")
        self.store.sessions()
        self.assertEqual(json.loads((Path(self.tmp.name) / "acked.json").read_text()), {})


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



class SkinTest(unittest.TestCase):
    def test_every_skin_has_every_animation(self):
        from claude_pet import skins
        import cairo
        for name in skins.available():
            skin = skins.load(name)
            self.assertEqual(skin.canvas, 30, name)  # todos no mesmo canvas: paredes/teto/balão dependem disso
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, skin.canvas * 3, skin.canvas * 3)
            for anim in skins.ANIM_NAMES:
                _fps, n = skin.anim_info(anim)
                self.assertGreater(n, 0, (name, anim))
                for i in range(n):
                    for facing in (1, -1):
                        for look in (-1, 0, 1):
                            skin.draw(cairo.Context(surf), anim, i, look, "attention", 3, "#5ec4b6",
                                      0.3 if anim == "dangle" else 0.0, facing)

    def test_unknown_skin_falls_back_to_robot(self):
        from claude_pet import skins
        self.assertEqual(skins.load("dragao").name, skins.ROBOT)
        self.assertEqual(skins.available()[0], skins.ROBOT)


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


class ForcedSleepTest(unittest.TestCase):
    def test_sleeps_through_activity_until_woken(self):
        pet = Pet(Config(), Rect(0, 0, 1920, 1080), rng=random.Random(1))
        pet.mode, pet.s = "edge", pet.seg[0] + 200   # na parede
        pet.sleep_now()
        for _ in range(200):
            f = pet.tick(1 / 30, "idle", (pet.position()[0] + 30, pet.position()[1] + 30))
        self.assertTrue(pet.on_floor)                # desceu da parede
        self.assertEqual((f.anim, f.status), ("sleep", "sleep"))
        pet.cheer()
        f = pet.tick(1 / 30, "done", None)
        self.assertEqual(f.anim, "sleep")            # nem comemorando acorda
        pet.wake()
        f = pet.tick(1 / 30, "thinking", None)
        self.assertNotEqual(f.anim, "sleep")


class CrossesTest(unittest.TestCase):
    def test_fast_pass_over_rect_counts(self):
        from claude_pet.window import _crosses
        rect = (100, 100, 60, 60)
        self.assertTrue(_crosses((0, 130), (400, 130), rect))      # atravessou entre dois ticks
        self.assertFalse(_crosses((0, 0), (400, 0), rect))
        self.assertTrue(_crosses(None, (120, 120), rect))
        self.assertFalse(_crosses((0, 0), None, rect))
        self.assertFalse(_crosses((0, 0), (120, 120), None))


class I18nTest(unittest.TestCase):
    def tearDown(self):
        from claude_pet import i18n
        i18n.set_language("pt")

    def test_detects_system_language_like_gtk(self):
        from claude_pet.i18n import system_language
        gabriel = {"LANGUAGE": "en_US:en", "LANG": "en_US.UTF-8", "LC_TIME": "pt_BR.UTF-8"}
        self.assertEqual(system_language(gabriel), "en")        # região pt_BR não é idioma
        self.assertEqual(system_language({"LANG": "pt_BR.UTF-8"}), "pt")
        self.assertEqual(system_language({"LANGUAGE": "pt_PT:pt", "LANG": "en_US.UTF-8"}), "pt")
        self.assertEqual(system_language({"LC_ALL": "C", "LANG": "pt_BR.UTF-8"}), "pt")  # C não decide
        self.assertEqual(system_language({"LANG": "de_DE.UTF-8"}), "en")  # sem tradução: inglês
        self.assertEqual(system_language({}), "en")

    def test_explicit_choice_beats_system(self):
        from claude_pet.i18n import resolve
        self.assertEqual(resolve("pt", {"LANG": "en_US.UTF-8"}), "pt")
        self.assertEqual(resolve("auto", {"LANG": "pt_BR.UTF-8"}), "pt")
        self.assertEqual(resolve("klingon", {"LANG": "en_US.UTF-8"}), "en")

    def test_every_text_exists_in_every_language(self):
        from claude_pet.i18n import LANGUAGES, STRINGS
        import re as _re
        for key, entry in STRINGS.items():
            for lang in LANGUAGES:
                self.assertTrue(entry.get(lang), (key, lang))
            fields = {lang: set(_re.findall(r"{(\w+)}", entry[lang])) for lang in LANGUAGES}
            self.assertEqual(fields["pt"], fields["en"], key)   # mesmos {campos} nas duas

    def test_texts_switch_with_language(self):
        from claude_pet import i18n, skins
        i18n.set_language("en")
        self.assertEqual(Config().display_name, "Your pet")
        self.assertEqual(i18n.t("bubble.one", name="Rex", status=i18n.t("status.idle")), "Rex is chilling")
        self.assertEqual(skins.label("capivara"), "Capybara")
        msg = "Claude needs your permission to use Bash"
        self.assertEqual(i18n.claude_message(msg), msg)          # em inglês, mostra como veio
        i18n.set_language("pt")
        self.assertEqual(Config().display_name, "Seu pet")
        self.assertEqual(i18n.claude_message(msg), "Quer permissão para usar Bash")
        self.assertEqual(skins.label("capivara"), "Capivara")


if __name__ == "__main__":
    unittest.main()
