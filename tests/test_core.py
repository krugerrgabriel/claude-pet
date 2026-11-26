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

    def test_rest_sits_skin_sits_on_every_pause_on_the_floor(self):
        from claude_pet import skins
        for name, want in (("pato_confuso", "sit"), (skins.ROBOT, "stand")):
            pet = Pet(Config(), Rect(0, 0, 1920, 1080), rng=random.Random(1), skin=skins.load(name))
            pet._attach_floor()
            now = time.monotonic()
            pet.idle_action, pet.action_until, pet.last_activity = "pause", now + 100, now
            self.assertEqual(pet._behave(1 / 30, now, None), (want, 0), name)

    def test_unknown_skin_falls_back_to_robot(self):
        from claude_pet import skins
        self.assertEqual(skins.load("unicornio").name, skins.ROBOT)
        self.assertEqual(skins.available()[0], skins.ROBOT)


class ConfusedTest(unittest.TestCase):
    """De vez em quando, quem tem a animação "confused" larga o que está fazendo e fica confuso."""

    def setUp(self):
        import claude_pet.character as C
        self.C, self.t = C, [1000.0]
        self.orig = C.time.monotonic
        C.time.monotonic = lambda: self.t[0]

    def tearDown(self):
        self.C.time.monotonic = self.orig

    def pet_on_floor(self, name, **cfg):
        from claude_pet import skins
        pet = Pet(Config(**cfg), Rect(0, 0, 1920, 1080), rng=random.Random(1), skin=skins.load(name))
        pet._attach_floor()
        pet.last_activity = self.t[0]
        return pet

    def step(self, pet, status="idle", seconds=0.0):
        """Avança `seconds` em passos de 1/30 s; devolve as animações de cada passo."""
        anims = []
        for _ in range(max(1, round(seconds * 30))):
            self.t[0] += 1 / 30
            anims.append(pet.tick(1 / 30, status, None).anim)
        return anims

    def test_stops_walking_gets_confused_then_goes_back(self):
        pet = self.pet_on_floor("pato_cachecol")
        pet.next_confused = self.t[0] + 100
        pet.idle_action, pet.target_s, pet.action_until = "walk", pet.seg[0] - 1, self.t[0] + 100
        self.assertIn("walk", self.step(pet, seconds=0.5))
        pet.next_confused = self.t[0]
        where = pet.position()
        fps, n = pet.skin.anim_info("confused")
        self.assertEqual(set(self.step(pet, seconds=n / fps - 0.1)), {"confused"})
        self.assertEqual(pet.position(), where)               # parou onde estava
        self.assertEqual(self.step(pet, seconds=0.5)[-1], "walk")   # acabou: volta a andar
        self.assertGreater(pet.next_confused, self.t[0] + 30)       # a próxima já está sorteada

    def test_interrupts_claude_states_too(self):
        pet = self.pet_on_floor("pato_cachecol")
        pet.next_confused = self.t[0]
        self.assertEqual(set(self.step(pet, "working", 0.5)), {"confused"})

    def test_never_while_sleeping(self):
        pet = self.pet_on_floor("pato_cachecol")
        pet.sleep_now()                                       # "botar pra dormir"
        pet.next_confused = self.t[0]
        self.assertNotIn("confused", self.step(pet, seconds=1.0))
        pet = self.pet_on_floor("pato_cachecol", sleep_after=1.0)
        pet.next_confused = self.t[0] + 100
        self.assertEqual(self.step(pet, seconds=2.0)[-1], "sleep")   # cochilou sozinho
        pet.next_confused = self.t[0]
        self.assertNotIn("confused", self.step(pet, seconds=1.0))

    def test_only_who_has_the_animation_and_can_be_turned_off(self):
        for name, cfg in (("robo", {}), ("pato", {}), ("pato_cachecol", {"confused_every": 0})):
            pet = self.pet_on_floor(name, **cfg)
            pet.next_confused = self.t[0]
            self.assertNotIn("confused", self.step(pet, seconds=1.0), name)


class CryTest(unittest.TestCase):
    """De vez em quando, com o Claude parado, quem tem "cry" vai pro canto da tela e chora um pouco."""
    setUp, tearDown = ConfusedTest.setUp, ConfusedTest.tearDown
    pet_on_floor, step = ConfusedTest.pet_on_floor, ConfusedTest.step

    def crying_pet(self, s, **cfg):
        pet = self.pet_on_floor("pato_cachecol", **cfg)
        pet.s, pet.next_confused, pet.next_cry = s, self.t[0] + 999, self.t[0]
        return pet

    def test_walks_to_the_nearest_corner_cries_facing_the_wall_then_goes_on(self):
        for s, side in ((300, -1), (1500, 1)):
            pet = self.crying_pet(s)
            corner = 0 if side < 0 else int(pet.seg[0] - 1)
            frames = []
            for _ in range(30 * 30):
                self.t[0] += 1 / 30
                frames.append(pet.tick(1 / 30, "idle", None))
            anims = [f.anim for f in frames]
            first = anims.index("cry")
            self.assertEqual(set(anims[:first]), {"walk"}, s)                  # vai andando até o canto
            crying = [f for f in frames if f.anim == "cry"]
            self.assertNotIn("cry", anims[first + len(crying):], s)            # chora uma vez só, seguido
            self.assertTrue(self.C.CRY_TIME[0] <= len(crying) / 30 <= self.C.CRY_TIME[1] + 0.1, s)
            self.assertEqual({f.x for f in crying}, {corner}, s)              # no canto
            self.assertEqual({f.facing for f in crying}, {side}, s)           # virado pra parede
            self.assertGreater(pet.next_cry, self.t[0] + 30, s)                # o próximo já está sorteado

    def test_also_while_waiting_for_you_but_not_while_claude_works_or_calls_you(self):
        pet = self.crying_pet(5)
        pet.next_cry = self.t[0] + 100
        self.assertEqual(self.step(pet, "done", 4.0)[-1], "waiting")          # comemorou, esperando você
        pet.next_cry = self.t[0]
        self.assertEqual(self.step(pet, "done", 2.0)[-1], "cry")
        for st in ("thinking", "working", "attention"):
            pet = self.crying_pet(5)
            self.assertNotIn("cry", self.step(pet, st, 2.0), st)

    def test_claude_doing_something_ends_it(self):
        pet = self.crying_pet(5)
        self.assertEqual(self.step(pet, seconds=1.0)[-1], "cry")
        self.assertEqual(set(self.step(pet, "working", 0.5)), {"work"})
        self.assertNotIn("cry", self.step(pet, seconds=3.0))

    def test_petting_consoles_him(self):
        pet = self.crying_pet(5)
        self.assertEqual(self.step(pet, seconds=1.0)[-1], "cry")
        pet.cheer()
        anims = self.step(pet, seconds=4.0)
        self.assertEqual(anims[0], "happy")
        self.assertNotIn("cry", anims)

    def test_never_asleep_nor_for_who_lacks_it_or_turned_off(self):
        pet = self.crying_pet(300)
        pet.sleep_now()                                                        # "botar pra dormir"
        self.assertNotIn("cry", self.step(pet, seconds=2.0))
        pet = self.crying_pet(300, sleep_after=1.0)
        pet.next_cry = self.t[0] + 100
        self.assertEqual(self.step(pet, seconds=2.0)[-1], "sleep")            # cochilou sozinho
        pet.next_cry = self.t[0]
        self.assertNotIn("cry", self.step(pet, seconds=2.0))
        for name, cfg in (("robo", {}), ("pato", {}), ("pato_cachecol", {"cry_every": 0})):
            pet = self.pet_on_floor(name, **cfg)
            pet.s, pet.next_confused, pet.next_cry = 5, self.t[0] + 999, self.t[0]
            self.assertNotIn("cry", self.step(pet, seconds=2.0), name)


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


class MultiMonitorTest(unittest.TestCase):
    """Dois monitores lado a lado: arremessado na borda que encosta no outro, atravessa; na borda de fora, volta."""
    LEFT, RIGHT = Rect(0, 0, 1920, 1080), Rect(1920, 0, 1920, 1080)

    def _at(self, x, y):
        for r in (self.LEFT, self.RIGHT):
            if r.x <= x < r.x + r.w and r.y <= y < r.y + r.h:
                return r
        return None

    def make(self, x, vx):
        def neighbor(area, side, y):
            other = self._at(area.x - 1 if side < 0 else area.x + area.w, y)
            return other if other != area else None
        pet = Pet(Config(), self.LEFT, lambda x, y: self._at(x, y) or self.LEFT, rng=random.Random(1),
                  neighbor=neighbor)
        pet.mode, pet.x, pet.y, pet.vx, pet.vy = "free", x, 300.0, vx, -300.0
        return pet

    def _fly(self, pet):
        for _ in range(200):
            pet.tick(0.016, "idle", None)
            if pet.mode == "edge":
                break

    def test_thrown_into_shared_edge_crosses(self):
        pet = self.make(1800.0, 1500.0)
        self._fly(pet)
        self.assertGreaterEqual(pet.position()[0], 1920)
        self.assertEqual(pet.area, self.RIGHT)

    def test_crosses_back_to_the_left(self):
        pet = self.make(1980.0, -1500.0)
        pet.area = self.RIGHT
        self._fly(pet)
        self.assertLess(pet.position()[0], 1920)
        self.assertEqual(pet.area, self.LEFT)

    def test_outer_edge_still_bounces(self):
        pet = self.make(100.0, -1500.0)
        self._fly(pet)
        self.assertGreaterEqual(pet.position()[0], 0)
        self.assertEqual(pet.area, self.LEFT)


class WindowsPortTest(unittest.TestCase):
    """O que o Windows usa não pode depender de GTK/cairo, e tem que desenhar igual ao Linux."""

    def test_windows_modules_import_without_gtk_or_cairo(self):
        code = ("import sys; sys.modules['gi'] = None; sys.modules['cairo'] = None; "
                "import claude_pet.core, claude_pet.raster, claude_pet.winapp, claude_pet.state, "
                "claude_pet.focus, claude_pet.bubble, claude_pet.skins, claude_pet.chars.pato")
        r = subprocess.run([sys.executable, "-c", code], cwd=str(Path(__file__).resolve().parents[1]),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_raster_matches_cairo(self):
        try:
            import cairo
        except ImportError:
            self.skipTest("sem cairo")
        import math
        from claude_pet import raster, skins
        for name in skins.available():
            skin = skins.load(name)
            extra = tuple((a, 0, 0.0, -1) for a in ("confused", "cry") if skin.has_anim(a))   # opcionais
            for anim, rot, lean, facing in (("walk", 0, 0.0, -1), ("work", 90, 0.0, 1), ("dangle", 0, 0.3, 1)) + extra:
                n = skin.canvas * 2
                surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, n, n)
                cr = cairo.Context(surf)
                cr.translate(n / 2, n / 2)
                cr.rotate(math.radians(rot))
                cr.translate(-n / 2, -n / 2)
                skin.draw(cr, anim, 1, 1, "working", 2, "#5ec4b6", lean, facing)
                data, stride = surf.get_data(), surf.get_stride()
                want = []
                for y in range(n):
                    for x in range(n):
                        b, g, r_, a = data[y * stride + 4 * x:y * stride + 4 * x + 4]
                        want.append(None if a < 128 else "#%02x%02x%02x" % (r_, g, b))
                got = raster.render(skin, anim, 1, 1, "working", 2, "#5ec4b6", lean, facing, rot)
                self.assertEqual(got, want, (name, anim, rot, lean))

    def test_menu_model_has_everything(self):
        from claude_pet.core import PetCore
        from claude_pet import skins

        class Fake(PetCore):
            pass

        f = Fake()
        f._init_core()
        f.cfg = Config()
        f.skin = skins.load("pato")
        f.pet = Pet(Config(), Rect(0, 0, 1920, 1080), rng=random.Random(1))
        model = f.menu_model()
        kinds = [e[0] for e in model]
        self.assertEqual(kinds.count("radio"), 2)   # personagem e idioma
        chars = next(e for e in model if e[0] == "radio")[2]
        self.assertEqual([c[1] for c in chars].count(True), 1)
        self.assertTrue(all(e[2] for e in model if e[0] == "item" and e[3]))

    def test_smooth_animation_can_be_turned_off(self):
        from claude_pet import config as C, raster, skins
        from claude_pet.core import PetCore
        from claude_pet.i18n import t

        class Fake(PetCore):
            def _apply_skin(self):
                pass

        def pixels(i):
            return raster.render(f.skin, "walk", i, 0, "idle", 3, "#5ec4b6", 0.0, 1, 0)

        def anim_menu():
            found = [e[2] for e in f.menu_model() if e[0] == "radio" and e[1] == t("menu.animation")]
            return found[0] if found else None

        orig = C.CONFIG_FILE
        with tempfile.TemporaryDirectory() as tmp:
            C.CONFIG_FILE = Path(tmp) / "config.json"
            try:
                f = Fake()
                f._init_core()
                f.cfg = Config()
                f.skin = skins.load("pato_cachecol", f.cfg.smooth_for("pato_cachecol"))
                f.pet = Pet(Config(), Rect(0, 0, 1920, 1080), rng=random.Random(1), skin=f.skin)
                self.assertEqual([o[1] for o in anim_menu()], [True, False])   # padrão: suave
                self.assertNotEqual(pixels(0), pixels(1))       # quadro misturado com o próximo
                walk = f.skin.anim_info("walk")

                anim_menu()[1][2]()                              # menu: "Quadro a quadro"
                self.assertEqual(json.loads(C.CONFIG_FILE.read_text())["smooth_anim"], {"pato_cachecol": False})
                self.assertEqual([o[1] for o in anim_menu()], [False, True])
                self.assertEqual(f.skin.anim_info("walk"), walk)   # mesmo ritmo
                self.assertEqual(pixels(0), pixels(1))
                self.assertEqual(pixels(1), pixels(2))
                self.assertNotEqual(pixels(2), pixels(3))       # próximo quadro da folha

                cfg = Config.load()                              # reabrindo o pet, continua desligado
                self.assertFalse(cfg.smooth_for("pato_cachecol"))
                f._set_skin("capivara_dev")                      # cada personagem tem a sua escolha
                self.assertEqual([o[1] for o in anim_menu()], [True, False])
                f._set_skin("pato")                              # desenhado em código: sem o menu
                self.assertIsNone(anim_menu())
            finally:
                C.CONFIG_FILE = orig
                skins.load("pato_cachecol")                      # volta o módulo pro padrão


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
