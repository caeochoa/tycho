"""Interactive builder for experience/education/other profile entries."""

import json
from pathlib import Path

import yaml
import typer

from tycho.cv.profile_loader import _slugify


def wizard(profile_dir: Path, entry_type: str = "experience") -> dict:
    """Interactive CLI prompt loop to collect entry data.

    Returns a dict ready to be serialized to YAML.
    """
    entry: dict = {"type": entry_type}

    # Collect the primary name field based on type
    if entry_type == "experience":
        entry["company"] = typer.prompt("Company")
    elif entry_type == "education":
        entry["institution"] = typer.prompt("Institution")
    else:
        entry["organization"] = typer.prompt("Organization")

    # Title or degree
    if entry_type == "education":
        entry["degree"] = typer.prompt("Degree")
    else:
        entry["title"] = typer.prompt("Title")

    entry["dates"] = typer.prompt("Dates (e.g. 2024 - Present)")

    # Optional location
    location_raw = typer.prompt("Location (optional, press Enter to skip)", default="")
    if location_raw.strip():
        entry["location"] = location_raw.strip()

    # Tags
    tags_raw = typer.prompt("Tags (comma-separated, e.g. python,ml,backend)")
    entry["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]

    # Priority
    entry["priority"] = typer.prompt("Priority (default 1)", default="1")
    try:
        entry["priority"] = int(entry["priority"])
    except ValueError:
        entry["priority"] = 1

    # Bullets
    typer.echo("\nAdd bullets (press Enter with empty text to finish):")
    bullets = []
    while True:
        text = typer.prompt("  Bullet text", default="")
        if not text.strip():
            break

        bullet_tags_raw = typer.prompt(
            "  Bullet tags (enter to inherit entry tags)",
            default="",
        )
        if bullet_tags_raw.strip():
            bullet_tags = [t.strip() for t in bullet_tags_raw.split(",") if t.strip()]
        else:
            bullet_tags = list(entry["tags"])

        bullets.append({"text": text.strip(), "tags": bullet_tags})

    entry["bullets"] = bullets

    return entry


def draft_from_description(description: str, existing_tags: list[str], llm_client) -> dict:
    """Use the LLM to draft an experience entry from a free-text description.

    Returns a dict in the same format as wizard().
    Raises ValueError if LLM returns invalid JSON.
    """
    prompt = f"""You are helping create a CV entry from a description.

Existing tag vocabulary (use these where relevant): {', '.join(existing_tags[:30])}

Draft a structured CV entry from the following description. Return a JSON object with these fields:
- company (or institution/organization as appropriate)
- title (or degree)
- dates (e.g. "2023 - 2024")
- location (optional, string or null)
- tags (list of relevant strings from the vocabulary above, or new ones if needed)
- priority (1, 2, or 3)
- bullets: list of objects with "text" (string) and "tags" (list of strings)

Description:
{description}"""

    response = llm_client.invoke(prompt)

    # Extract JSON from response (may be wrapped in markdown code fences)
    raw = response.strip()
    if "```" in raw:
        # Strip markdown code fences
        lines = raw.splitlines()
        json_lines = []
        inside = False
        for line in lines:
            if line.startswith("```"):
                inside = not inside
                continue
            if inside:
                json_lines.append(line)
        raw = "\n".join(json_lines).strip()

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        raise ValueError("LLM returned invalid JSON")

    # Ensure type field is present (default experience)
    if "type" not in data:
        data["type"] = "experience"

    # Ensure bullets is a list of dicts with text + tags
    bullets = data.get("bullets", [])
    normalized_bullets = []
    for b in bullets:
        if isinstance(b, dict):
            normalized_bullets.append({
                "text": b.get("text", ""),
                "tags": b.get("tags", []),
            })
        elif isinstance(b, str):
            normalized_bullets.append({"text": b, "tags": []})
    data["bullets"] = normalized_bullets

    # Remove null location
    if data.get("location") is None:
        data.pop("location", None)

    return data


def save_entry(entry_dict: dict, profile_dir: Path) -> Path:
    """Slugify and write the entry dict to the correct subdirectory as YAML.

    Returns the path written.
    """
    entry_type = entry_dict.get("type", "experience")

    # Determine the name components based on type
    if entry_type == "education":
        part1 = entry_dict.get("institution", "")
        part2 = entry_dict.get("degree", "")
    elif entry_type == "other":
        part1 = entry_dict.get("organization", "")
        part2 = entry_dict.get("title", "")
    else:  # experience
        part1 = entry_dict.get("company", "")
        part2 = entry_dict.get("title", "")

    slug = _slugify(f"{part1}_{part2}")
    if not slug:
        slug = "entry"

    subdir_map = {
        "experience": "experience",
        "education": "education",
        "other": "other",
    }
    subdir = subdir_map.get(entry_type, "experience")
    target_dir = profile_dir / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    output_path = target_dir / f"{slug}.yaml"
    with open(output_path, "w") as f:
        yaml.dump(entry_dict, f, allow_unicode=True, sort_keys=False)

    return output_path
