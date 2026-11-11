#!/usr/bin/env python3
"""
update_projects.py

Dieses Skript holt die zuletzt aktualisierten öffentlichen Repositories
von GitHub und aktualisiert den "Featured Projects"-Bereich im
Profil-README automatisch.

Es ersetzt den Inhalt zwischen den Markierungen:
    <!-- PROJECTS:START -->
    <!-- PROJECTS:END -->

Repositories in PINNED_REPOS stehen immer zuoberst, der Rest folgt
nach letztem Update sortiert.

Konfiguration über Umgebungsvariablen:
    GH_USERNAME  GitHub-Benutzername (Standard: maliswiss)
    GH_TOKEN     GitHub-Token für API-Zugriff (optional, aber empfohlen)
    MAX_REPOS    Maximale Anzahl angezeigter Repos (Standard: 8)
"""

import os
import re
import sys
from pathlib import Path

import requests

# --- Konfiguration --------------------------------------------------------

USERNAME = os.environ.get("GH_USERNAME", "maliswiss")
TOKEN = os.environ.get("GH_TOKEN", "")
MAX_REPOS = int(os.environ.get("MAX_REPOS", "8"))
README_PATH = Path("README.md")

# Repos, die immer angezeigt werden (in dieser Reihenfolge, zuoberst)
PINNED_REPOS = [
    "digital-forensics-hacking-case-analysis",
]

# Repos, die nie im Profil angezeigt werden sollen
EXCLUDED_REPOS = {
    USERNAME,           # Profil-Repository selbst
    "OS-HF",
    "The_days_spent_with_Python",
    "Flask_03_04_If_Handling_Routes_and_Get_Post_Methods",
    "Flask-01-02",
    "aws-django-app",
    "Digitaler-forensischer-Analysebericht",
}

# Schlüsselwörter → Icons für eine konsistente visuelle Sprache
ICON_MAP = [
    (("forensics", "security", "pentest", "hacking"), "🛡️"),
    (("kubernetes", "k8s"),                 "☸️"),
    (("jenkins",),                          "🔄"),
    (("ansible",),                          "🔧"),
    (("terraform", "iac"),                  "🏗️"),
    (("docker", "container", "compose"),    "🐳"),
    (("azure",),                            "☁️"),
    (("aws", "cloud"),                      "☁️"),
    (("ci-cd", "ci/cd", "github-actions"),  "🔄"),
    (("network", "vyos", "opnsense"),       "🌐"),
    (("windows-server", "active-directory"),"🖥️"),
    (("linux",),                            "🐧"),
    (("react", "vue", "weather"),           "⚛️"),
    (("csharp", "winforms", "dotnet"),      "💠"),
    (("iot", "esp32"),                      "📡"),
]
DEFAULT_ICON = "📦"


# --- Helfer ---------------------------------------------------------------

def pick_icon(name: str, description: str, topics: list[str]) -> str:
    """Wählt ein Icon. Zuerst nach Repo-Name (genauer), dann nach Beschreibung."""
    name_l = name.lower()
    for keywords, icon in ICON_MAP:
        if any(kw in name_l for kw in keywords):
            return icon
    haystack = " ".join([description or "", " ".join(topics)]).lower()
    for keywords, icon in ICON_MAP:
        if any(kw in haystack for kw in keywords):
            return icon
    return DEFAULT_ICON


def short_stack(topics: list[str], language: str | None) -> str:
    """Erstellt eine kurze Stack-Bezeichnung aus Topics und Sprache."""
    if topics:
        return ", ".join(t.replace("-", " ").title() for t in topics[:3])
    return language or "—"


def fetch_repos() -> list[dict]:
    """Holt öffentliche Repos sortiert nach letztem Update."""
    url = f"https://api.github.com/users/{USERNAME}/repos"
    headers = {"Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    params = {"sort": "updated", "direction": "desc", "per_page": 100, "type": "public"}
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def order_repos(repos: list[dict]) -> list[dict]:
    """Stellt angepinnte Repos an den Anfang, Rest bleibt nach Update sortiert."""
    by_name = {r["name"]: r for r in repos}
    pinned = [by_name[n] for n in PINNED_REPOS if n in by_name]
    rest = [r for r in repos if r["name"] not in PINNED_REPOS]
    return pinned + rest


def build_table(repos: list[dict]) -> str:
    """Baut die Markdown-Tabelle für den Projekte-Bereich."""
    lines = [
        "<!-- Dieser Bereich wird automatisch durch GitHub Actions aktualisiert. Nicht manuell bearbeiten. -->",
        "",
        "| Projekt | Stack | Beschreibung |",
        "| :--- | :--- | :--- |",
    ]

    count = 0
    for repo in order_repos(repos):
        name = repo["name"]
        if name in EXCLUDED_REPOS or repo.get("fork") or repo.get("archived"):
            continue
        if count >= MAX_REPOS:
            break

        description = repo.get("description") or "Keine Beschreibung verfügbar."
        if len(description) > 80:
            description = description[:77].rstrip() + "…"

        topics = repo.get("topics", [])
        language = repo.get("language")
        icon = pick_icon(name, description, topics)
        stack = short_stack(topics, language)
        url = repo["html_url"]

        # Pipe-Zeichen in der Beschreibung escapen, damit die Tabelle nicht bricht
        description = description.replace("|", "\\|")

        lines.append(f"| {icon} **[{name}]({url})** | {stack} | {description} |")
        count += 1

    return "\n".join(lines) + "\n"


def update_readme(new_section: str) -> bool:
    """Ersetzt den Bereich zwischen den Markierungen. Gibt True zurück bei Änderungen."""
    if not README_PATH.exists():
        print(f"Fehler: {README_PATH} nicht gefunden.", file=sys.stderr)
        sys.exit(1)

    original = README_PATH.read_text(encoding="utf-8")

    pattern = re.compile(
        r"(<!-- PROJECTS:START -->)(.*?)(<!-- PROJECTS:END -->)",
        re.DOTALL,
    )

    if not pattern.search(original):
        print("Fehler: PROJECTS:START / PROJECTS:END Markierungen nicht gefunden.",
              file=sys.stderr)
        sys.exit(1)

    replacement = f"<!-- PROJECTS:START -->\n{new_section}<!-- PROJECTS:END -->"
    updated = pattern.sub(lambda _m: replacement, original)

    if updated == original:
        return False

    README_PATH.write_text(updated, encoding="utf-8")
    return True


# --- Hauptprogramm --------------------------------------------------------

def main() -> None:
    print(f"Hole Repositories für {USERNAME}…")
    try:
        repos = fetch_repos()
    except requests.HTTPError as exc:
        print(f"GitHub-API-Fehler: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"  {len(repos)} Repositories empfangen.")
    table = build_table(repos)
    changed = update_readme(table)

    if changed:
        print("README.md wurde aktualisiert.")
    else:
        print("Keine Änderungen — README ist bereits aktuell.")


if __name__ == "__main__":
    main()
