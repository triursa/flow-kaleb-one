#!/usr/bin/env python3
"""
flow.kaleb.one — Static Site Generator

Reads multiple domains from second-brain-vault (health, household, finance,
projects, ai-tooling) and generates a Liquid Glass morning dashboard.

Output: a single index.html with all data embedded as JSON for client-side rendering.
"""

import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

VAULT_DIR = os.environ.get("VAULT_DIR", "/tmp/second-brain-vault/domains")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/tmp/flow-site")

# ── Helpers ──────────────────────────────────────────────────────────────

def read_file(path):
    """Read file, return content or empty string."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (FileNotFoundError, UnicodeDecodeError):
        return ""


def parse_frontmatter(text):
    """Extract YAML frontmatter and body from markdown."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    fm_text = text[3:end].strip()
    body = text[end + 3:].strip()
    fm = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            # Handle YAML lists
            if val.startswith("[") and val.endswith("]"):
                val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",") if v.strip()]
            fm[key] = val
    return fm, body


def parse_md_table(content):
    """Parse a markdown table into (headers, rows)."""
    lines = content.split("\n")
    headers = None
    rows = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        # Protect wiki-link pipes
        protected = stripped
        while True:
            m = re.search(r"\[\[([^\]]*?)\|([^\]]*?)\]\]", protected)
            if not m:
                break
            protected = protected[:m.start()] + "[[" + m.group(1) + "§" + m.group(2) + "]]" + protected[m.end():]
        cells = [c.strip() for c in protected.split("|")[1:-1]]
        cells = [c.replace("§", "|") for c in cells]
        if headers is None:
            headers = cells
            continue
        if all(re.match(r"^[-:]+$", c) for c in cells):
            continue
        if headers and len(cells) >= len(headers):
            row = {}
            for i, h in enumerate(headers):
                row[h] = cells[i] if i < len(cells) else ""
            rows.append(row)
    return headers, rows


# ── Domain Parsers ────────────────────────────────────────────────────────

def parse_health(vault_path):
    """Parse health domain — vitals log + goals."""
    health_dir = Path(vault_path) / "health"
    data = {"weight": [], "conditions": [], "goals": []}

    # Vitals log
    vitals = read_file(health_dir / "vitals-log.md")
    if vitals:
        fm, body = parse_frontmatter(vitals)
        headers, rows = parse_md_table(body)
        if headers and "Weight (lbs)" in headers:
            for row in rows:
                date_str = row.get("Date", "").strip()
                weight_str = row.get("Weight (lbs)", "").strip()
                notes = row.get("Notes", "").strip()
                if date_str and weight_str and weight_str != "[log it]":
                    try:
                        weight = float(re.sub(r'[^\d.]', '', weight_str))
                        data["weight"].append({"date": date_str, "weight": weight, "notes": notes})
                    except ValueError:
                        pass

    # Goals
    goals = read_file(health_dir / "GOALS.md")
    if goals:
        fm, body = parse_frontmatter(goals)
        # Extract weight goal
        m = re.search(r"Target weight.*?(\d+)\s*lbs", goals)
        if m:
            data["goals"].append({"type": "weight_target", "value": int(m.group(1)), "unit": "lbs"})
        m = re.search(r"Current weight.*?(\d+)", goals)
        if m:
            data["goals"].append({"type": "weight_current", "value": int(m.group(1)), "unit": "lbs"})

    return data


def parse_household(vault_path):
    """Parse household domain — context, contacts, reminders."""
    household_dir = Path(vault_path) / "household"
    data = {"family": [], "home": {}, "reminders": []}

    context = read_file(household_dir / "CONTEXT.md")
    if context:
        headers, rows = parse_md_table(context)
        # Family table
        family_section = re.search(r"## Family\s*\n((?:\|[^\n]+\n?)+)", context)
        if family_section:
            h, r = parse_md_table(family_section.group(1))
            for row in r:
                person = row.get("Person", "").strip()
                notes = row.get("Notes", "").strip()
                if person:
                    data["family"].append({"name": person, "notes": notes})

        # Home section
        m = re.search(r"\*\*Address:\*\*\s*(.+)", context)
        if m:
            data["home"]["address"] = m.group(1).strip()

    return data


def parse_finance(vault_path):
    """Parse finance domain — key figures."""
    finance_dir = Path(vault_path) / "finance"
    data = {"highlights": []}

    content = read_file(finance_dir / "finance-home.md")
    if content:
        fm, body = parse_frontmatter(content)
        # Extract property research highlights
        m = re.search(r"Target:.*?~?\$?([\d,]+)", body)
        if m:
            data["highlights"].append({"label": "Property Target", "value": m.group(1)})
        m = re.search(r"Mortgage rate.*?([\d.]+)%", body)
        if m:
            data["highlights"].append({"label": "Mortgage Rate", "value": f"{m.group(1)}%"})

    return data


def parse_projects(vault_path):
    """Parse projects domain — active projects table."""
    projects_dir = Path(vault_path) / "projects"
    data = {"active": [], "paused": []}

    content = read_file(projects_dir / "PROJECTS.md")
    if content:
        fm, body = parse_frontmatter(content)
        headers, rows = parse_md_table(body)
        for row in rows:
            status = row.get("Status", "").strip().lower()
            entry = {
                "id": row.get("ID", "").strip(),
                "name": row.get("Name", "").strip(),
                "status": status,
                "priority": row.get("Priority", "").strip(),
                "start": row.get("Start", "").strip(),
                "target": row.get("Target", "").strip(),
                "domain": row.get("Domain", "").strip(),
                "tags": row.get("Tags", "").strip(),
            }
            if status == "active":
                data["active"].append(entry)
            elif status == "paused":
                data["paused"].append(entry)
            else:
                data["active"].append(entry)  # default to active

    # Also scan for individual project files for more detail
    for md_file in sorted(projects_dir.glob("P*.md")):
        content = read_file(md_file)
        if content:
            fm, body = parse_frontmatter(content)
            pid = fm.get("id", fm.get("title", md_file.stem))
            # Find this project in our list and add detail URL
            for proj in data["active"] + data["paused"]:
                if proj["id"].lower() == str(pid).lower():
                    proj["detail_file"] = md_file.stem
                    # Extract overview as snippet
                    m = re.search(r"## Overview\s*\n(.+?)(?:\n##|\Z)", body, re.DOTALL)
                    if m:
                        proj["overview"] = m.group(1).strip()[:200]

    return data


def parse_ai_tooling(vault_path):
    """Parse ai-tooling domain — repo index."""
    ai_dir = Path(vault_path) / "ai-tooling"
    data = {"repos": []}

    content = read_file(ai_dir / "repo-index.md")
    if content:
        # Extract repo names from headings or bullet lists
        for m in re.finditer(r"###\s+(.+)|\*\*(.+?)\*\*.*?github\.com/triursa/(\S+)", content):
            name = (m.group(1) or m.group(2) or "").strip()
            repo = m.group(3) if m.group(3) else ""
            if name:
                data["repos"].append({"name": name, "repo": repo})

    return data


# ── Ecosystem Apps (static) ────────────────────────────────────────────────

ECOSYSTEM_APPS = [
    {"name": "Kitchen", "icon": "🍳", "href": "https://kitchen.kaleb.one", "desc": "Recipes, meal plans & grocery lists", "accent": "#f59e0b"},
    {"name": "Read", "icon": "📚", "href": "https://read.kaleb.one", "desc": "Book tracker & reading lists", "accent": "#10b981"},
    {"name": "Watch", "icon": "🎬", "href": "https://watch.kaleb.one", "desc": "Movies & TV watchlist", "accent": "#f59e0b"},
    {"name": "Music", "icon": "🎵", "href": "https://music.kaleb.one", "desc": "Listening history & favorites", "accent": "#8b5cf6"},
    {"name": "Masks", "icon": "🎭", "href": "https://masks.kaleb.one", "desc": "Halden City RPG wiki", "accent": "#8b5cf6"},
    {"name": "Vault", "icon": "🔒", "href": "https://vault.kaleb.one", "desc": "Private media gallery", "accent": "#6366f1"},
    {"name": "Wish", "icon": "🎁", "href": "https://wish.kaleb.one", "desc": "Shared wishlist", "accent": "#ec4899"},
    {"name": "Projects", "icon": "📋", "href": "https://projects.kaleb.one", "desc": "Project tracker & kanban", "accent": "#06b6d4"},
    {"name": "Watchtower", "icon": "📡", "href": "https://watchtower.kaleb.one", "desc": "System monitor dashboard", "accent": "#ef4444"},
    {"name": "Brain", "icon": "🧠", "href": "https://brain.kaleb.one", "desc": "Full second brain vault", "accent": "#3b82f6"},
]


# ── Build ──────────────────────────────────────────────────────────────────

def build():
    """Main build: read vault domains, generate index.html."""
    vault = VAULT_DIR
    out = Path(OUTPUT_DIR)
    out.mkdir(parents=True, exist_ok=True)

    # Parse all domains
    health = parse_health(vault)
    household = parse_household(vault)
    finance = parse_finance(vault)
    projects = parse_projects(vault)
    ai_tooling = parse_ai_tooling(vault)

    # Build data payload for client-side rendering
    page_data = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "today": date.today().isoformat(),
        "health": health,
        "household": household,
        "finance": finance,
        "projects": projects,
        "ai_tooling": ai_tooling,
        "ecosystem": ECOSYSTEM_APPS,
    }

    # Write data as JSON for client to consume
    data_json = json.dumps(page_data, indent=2, ensure_ascii=False)

    # Read template
    script_dir = Path(__file__).parent.parent
    template = read_file(script_dir / "index.html")
    if not template:
        # Fallback: read from same directory as build.py
        template = read_file(Path(__file__).parent.parent / "index.html")

    # Inject data
    html = template.replace("/*__FLOW_DATA__*/", data_json.replace("*/", "*\\/").replace("</", "<\\/"))

    # Find the JSON injection point and replace
    if "/*__FLOW_DATA__*/" not in template and "__FLOW_DATA__" in template:
        html = template.replace('"__FLOW_DATA__"', data_json)

    # Write output
    (out / "index.html").write_text(html, encoding="utf-8")

    print(f"✅ Built flow.kaleb.one → {out}")
    print(f"   Health: {len(health.get('weight', []))} weight entries, {len(health.get('goals', []))} goals")
    print(f"   Household: {len(household.get('family', []))} family members")
    print(f"   Finance: {len(finance.get('highlights', []))} highlights")
    print(f"   Projects: {len(projects.get('active', []))} active, {len(projects.get('paused', []))} paused")
    print(f"   Ecosystem: {len(ECOSYSTEM_APPS)} apps")


if __name__ == "__main__":
    build()