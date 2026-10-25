"""Zugangsdaten je Quelle (API-Schlüssel, Benutzername, Passwort) für die Desktop-App.

Zweck:     Die Quellenübersicht der App nimmt Zugangsdaten entgegen und legt sie lokal ab. Die Sammler lesen sie wie bisher aus
           Umgebungsvariablen; die App reicht sie nur an ihre Kindprozesse weiter.
Ablage:    <Datenordner>/zugang.json, Rechte 600 (nur der Nutzer), atomar geschrieben. Klartext in einer Datei, nicht im Schlüsselbund
           des Betriebssystems. Die Datei gehört nicht ins Repository (liegt im Datenordner, nicht im Projekt).
Regeln:    * Nur Variablen, die im Quellenregister (`zugang` je Quelle) stehen, werden angenommen: keine beliebigen Umgebungsvariablen.
           * Werte werden nie zurückgegeben, nie geloggt. Die Oberfläche erfährt nur "gesetzt" oder "nicht gesetzt".
           * Einzeilig, ohne Steuerzeichen, höchstens 256 Zeichen.
Beispiel:  store = ZugangStore(Path("zugang.json"), registry.entries); store.set("TANKERKOENIG_API_KEY", "…"); store.env()
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger("landblick.zugang")
MAX_LEN = 256


class ZugangError(ValueError):
    """Eingabe abgelehnt (unbekannte Variable, ungültiger Wert). Die Meldung enthält nie den Wert."""


NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")


def env_from_file(path: Path) -> dict[str, str]:
    """Liest eine zugang.json für Sammler, die ohne die App laufen (Zeitplan, Kommandozeile). Nur gültige Variablennamen und Texte;
    welche Namen erlaubt sind, hat schon ZugangStore beim Schreiben anhand des Quellenregisters entschieden."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and NAME.match(k) and isinstance(v, str) and v and "\n" not in v}


def handle_post(store: "ZugangStore", raw: bytes) -> tuple[int, dict[str, Any]]:
    """Gemeinsame Annahme für App und lokalen Webserver: {"env": "NAME", "wert": "…"} setzt, {"env": "NAME", "loeschen": true} entfernt.
    Rückgabe (HTTP-Status, Antwort); Antworten enthalten nie den Wert."""
    try:
        body = json.loads(raw[:4096] or b"{}")
        env = body["env"]
        if not isinstance(env, str):
            raise ZugangError("Unbekannte Zugangsvariable")
        if body.get("loeschen") is True:
            store.delete(env)
        else:
            store.set(env, body.get("wert"))
    except ZugangError as err:
        return 400, {"error": str(err)}
    except (ValueError, KeyError, TypeError):
        return 400, {"error": "Eingabe ungültig"}
    except OSError:
        log.exception("Zugangsdatei nicht schreibbar")
        return 500, {"error": "Datei im Datenordner nicht schreibbar"}
    return 200, {"ok": True, "quellen": store.status()}


class ZugangStore:
    def __init__(self, path: Path, entries: list[Any], dotenv: Path | None = None) -> None:
        self.path = path
        self.dotenv = dotenv   # nur für die Anzeige: Variablen, die schon in dieser .env stehen (Werte werden nicht gelesen)
        self._lock = threading.Lock()
        self.allowed: dict[str, tuple[Any, Any]] = {f.env: (e, f) for e in entries for f in getattr(e, "zugang", [])}

    def _read(self) -> dict[str, str]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return {k: v for k, v in data.items() if k in self.allowed and isinstance(v, str) and v} if isinstance(data, dict) else {}

    def _write(self, data: dict[str, str]) -> None:
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    @staticmethod
    def clean(value: object) -> str:
        if not isinstance(value, str):
            raise ZugangError("Wert muss Text sein")
        v = value.strip()
        if not v:
            raise ZugangError("Wert ist leer")
        if len(v) > MAX_LEN:
            raise ZugangError(f"Wert ist länger als {MAX_LEN} Zeichen")
        if any(ord(c) < 32 or ord(c) == 127 for c in v):
            raise ZugangError("Wert enthält Steuerzeichen oder Zeilenumbrüche")
        return v

    def set(self, env: str, value: object) -> None:
        if env not in self.allowed:
            raise ZugangError("Unbekannte Zugangsvariable")
        v = self.clean(value)
        with self._lock:
            data = self._read()
            data[env] = v
            self._write(data)
        log.info("Zugangsdatum %s gesetzt", env)

    def delete(self, env: str) -> None:
        if env not in self.allowed:
            raise ZugangError("Unbekannte Zugangsvariable")
        with self._lock:
            data = self._read()
            if data.pop(env, None) is not None:
                self._write(data)
        log.info("Zugangsdatum %s entfernt", env)

    def env(self) -> dict[str, str]:
        """Für Kindprozesse: Variable → Wert, nur freigegebene Namen."""
        with self._lock:
            return self._read()

    def _extern(self) -> set[str]:
        """Namen, die außerhalb dieser Datei gesetzt sind: Umgebung des Prozesses oder .env. Nur Namen, nie Werte."""
        names = {k for k in self.allowed if os.environ.get(k)}
        if self.dotenv:
            try:
                for line in self.dotenv.read_text(encoding="utf-8").splitlines():
                    k, sep, v = line.strip().partition("=")
                    if sep and k.strip() in self.allowed and v.strip().strip("'\""):
                        names.add(k.strip())
            except OSError:
                pass
        return names

    def status(self) -> list[dict[str, Any]]:
        """Je Quelle mit Zugangsfeldern: Felder samt "gesetzt" (in dieser Datei) und "extern" (.env oder Umgebung). Nie mit Werten."""
        have = self._read()
        extern = self._extern()
        out: dict[str, dict[str, Any]] = {}
        for env, (entry, f) in self.allowed.items():
            src = out.setdefault(entry.id, {"source_id": entry.id, "name": entry.kurzname or entry.name, "hinweis": entry.auth, "url": entry.url, "felder": []})
            src["felder"].append({"env": env, "art": f.art, "bezeichnung": f.bezeichnung, "gesetzt": env in have, "extern": env in extern and env not in have})
        return list(out.values())
