"""Textos do pet em português e inglês.

`language` no config.json: "auto" (segue o idioma do sistema), "pt" ou "en".
No automático, qualquer idioma que não seja português cai pro inglês.
"""
from __future__ import annotations

import os
import re

LANGUAGES = ("pt", "en")

STRINGS: dict[str, dict[str, str]] = {
    # status (usados em "{name} está {status}" e "1 chat {status}")
    "status.idle": {"pt": "de boa", "en": "chilling"},
    "status.thinking": {"pt": "pensando…", "en": "thinking…"},
    "status.working": {"pt": "trabalhando", "en": "working"},
    "status.attention": {"pt": "precisando de você", "en": "needs you"},
    "status.done": {"pt": "terminou", "en": "done"},
    # balões
    "bubble.needs_you": {"pt": "Claude Code precisa de você", "en": "Claude Code needs you"},
    "bubble.done": {"pt": "Claude Code terminou", "en": "Claude Code is done"},
    "bubble.click": {"pt": "Clique em mim para abrir", "en": "Click me to open it"},
    "bubble.sleeping": {"pt": "{name} está dormindo até o próximo prompt",
                        "en": "{name} is asleep until your next prompt"},
    "bubble.no_sessions": {"pt": "{name}: nenhuma sessão aberta", "en": "{name}: no open sessions"},
    "bubble.one": {"pt": "{name} está {status}", "en": "{name} is {status}"},
    "bubble.chats_one": {"pt": "{n} chat {status}", "en": "{n} chat {status}"},
    "bubble.chats_many": {"pt": "{n} chats {status}", "en": "{n} chats {status}"},
    # mensagens do Claude Code (chegam em inglês)
    "msg.permission": {"pt": "Quer permissão para usar {tool}", "en": "Wants permission to use {tool}"},
    "msg.waiting": {"pt": "Esperando sua resposta", "en": "Waiting for your answer"},
    # menu
    "menu.no_sessions": {"pt": "Nenhuma sessão aberta", "en": "No open sessions"},
    "menu.character": {"pt": "Personagem", "en": "Character"},
    "menu.rename": {"pt": "Mudar nome…", "en": "Rename…"},
    "menu.language": {"pt": "Idioma", "en": "Language"},
    "menu.lang_auto": {"pt": "Automático (sistema)", "en": "Automatic (system)"},
    "menu.sleep": {"pt": "Botar pra dormir", "en": "Put to sleep"},
    "menu.wake": {"pt": "Acordar", "en": "Wake up"},
    "menu.hide_30": {"pt": "Esconder por 30 min", "en": "Hide for 30 min"},
    "menu.hide_2h": {"pt": "Esconder por 2 h", "en": "Hide for 2 h"},
    "menu.quit": {"pt": "Sair", "en": "Quit"},
    # janelinha de nome
    "rename.title": {"pt": "Nome do pet", "en": "Pet name"},
    "rename.question": {"pt": "Como seu pet se chama?", "en": "What's your pet's name?"},
    "rename.cancel": {"pt": "Cancelar", "en": "Cancel"},
    "rename.save": {"pt": "Salvar", "en": "Save"},
    "default_name": {"pt": "Seu pet", "en": "Your pet"},
    # personagens
    "char.robo": {"pt": "Robô", "en": "Robot"},
    "char.lagartixa": {"pt": "Lagartixa", "en": "Gecko"},
    "char.gosminha": {"pt": "Gosminha", "en": "Slime"},
    "char.capivara": {"pt": "Capivara", "en": "Capybara"},
}

# nomes das línguas sempre no próprio idioma (assim quem não lê o atual acha o seu)
LANGUAGE_NAMES = {"pt": "Português", "en": "English"}

_current = "pt"


def system_language(environ=None) -> str:
    """Idioma das mensagens do sistema, na mesma ordem que o gettext/GTK usam."""
    env = os.environ if environ is None else environ
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = (env.get(var) or "").strip()
        if value and value not in ("C", "POSIX"):
            first = value.split(":")[0].lower()
            return "pt" if first.startswith("pt") else "en"
    return "en"


def resolve(setting: str | None, environ=None) -> str:
    setting = (setting or "auto").lower()
    return setting if setting in LANGUAGES else system_language(environ)


def set_language(setting: str | None) -> str:
    global _current
    _current = resolve(setting)
    return _current


def current() -> str:
    return _current


def t(key: str, **kw) -> str:
    entry = STRINGS.get(key)
    if entry is None:
        return key
    return (entry.get(_current) or entry["en"]).format(**kw)


_PERMISSION = re.compile(r"Claude needs your permission to use (.+)", re.I)


def claude_message(msg: str) -> str:
    """Mensagens do Claude Code vêm em inglês: em português traduz as comuns, em inglês mostra como vieram."""
    if not msg or _current == "en":
        return msg or ""
    m = _PERMISSION.search(msg)
    if m:
        return t("msg.permission", tool=m.group(1))
    if "waiting for your input" in msg.lower():
        return t("msg.waiting")
    return msg
