#!/usr/bin/env python3
"""
update_projects.py

Dieses Skript holt die zuletzt aktualisierten öffentlichen Repositories
von GitHub und aktualisiert den "Featured Projects"-Bereich im
Profil-README automatisch.

Es ersetzt den Inhalt zwischen den Markierungen:
    <!-- PROJECTS:START -->
    <!-- PROJECTS:END -->

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

# Repos, die nie im Profil angezeigt werden sollen
EXCLUDED_REPOS = {
    USERNAME,           # Profil-Repository selbst
    "OS-HF",
    "The_days_spent_with_Python",
    "Flask_03_04_If_Handling_Routes_and_Methods",
    "Flask-01-02",
    "aws-django-app",
}

# Schlüsselwörter → Icons für eine konsistente visuelle Sprache
ICON_MAP = [
    (("kubernetes", "k8s"),                 "☸️"),
    (("docker", "container", "compose"),    "🐳"),
    (("azure",),                            "☁️"),
    (("aws", "cloud"),                      "☁️"),
    (("ci-cd", "ci/cd", "github-actions"),  "🔄"),
    (("network", "vyos", "opnsense"),       "🌐"),
    (("windows-server", "active-directory"),"🖥️"),
    (("linux",),                            "🐧"),
    (("react", "vue", "weather"),           "⚛️"),
    (("csharp", "winforms", "dotnet"),      "💠"),
    (("security", "pentest", "forensics"),  "🛡️"),
    (("iot", "esp32"),                      "📡"),
]
DEFAULT_ICON = "📦"


# --- Helfer ---------------------------------------------------------------

def pick_icon(name: str, description: str, topics: list[str]) -> str:
    """Wählt ein Icon anhand von Name, Beschreibung und Topics."""
    haystack = " ".join([name, description or "", " ".join(topics)]).lower()
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


def build_table(repos: list[dict]) -> str:
    """Baut die Markdown-Tabelle für den Projekte-Bereich."""
    lines = [
        "<!-- Dieser Bereich wird automatisch durch GitHub Actions aktualisiert. Nicht manuell bearbeiten. -->",
        "",
        "| Projekt | Stack | Beschreibung |",
        "| :--- | :--- | :--- |",
    ]

    count = 0
    for repo in repos:
        name = repo["name"]
        if name in EXCLUDED_REPOS or repo.get("fork") or repo.get("archived"):
            continue
        if count >= MAX_REPOS:
            break

        description = repo.get("description") or "Keine Beschreibung verfügbar."
        # Beschreibung auf eine sinnvolle Länge kürzen
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
    updated = pattern.sub(replacement, original)

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
