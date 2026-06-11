"""Tests for experience_builder.py — save_entry, draft_from_description."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from tycho.cv.experience_builder import draft_from_description, save_entry


class TestSaveEntry:
    def test_creates_file(self, tmp_path):
        """save_entry writes a YAML file to profile_dir/experience/acme_engineer.yaml."""
        (tmp_path / "experience").mkdir()
        entry = {"type": "experience", "company": "Acme", "title": "Engineer", "bullets": []}

        path = save_entry(entry, tmp_path)

        assert path.exists()
        assert path.parent == tmp_path / "experience"
        assert path.name == "acme_engineer.yaml"

    def test_slugifies_unicode(self, tmp_path):
        """Unicode characters in company name are stripped when forming the slug."""
        (tmp_path / "experience").mkdir()
        entry = {"type": "experience", "company": "Grupo Oesía", "title": "AI Engineer", "bullets": []}

        path = save_entry(entry, tmp_path)

        # Accent is stripped from slug
        assert path.exists()
        assert "oesia" in path.name or "grupo" in path.name

    def test_avoids_collision(self, tmp_path):
        """Saving twice with the same company+title produces two distinct files."""
        (tmp_path / "experience").mkdir()
        entry = {"type": "experience", "company": "Corp", "title": "Dev", "bullets": []}

        path1 = save_entry(entry, tmp_path)
        path2 = save_entry(entry, tmp_path)

        assert path1.exists()
        assert path2.exists()
        assert path1 != path2
        assert "_2" in path2.name

    def test_preserves_key_order(self, tmp_path):
        """Keys are written in insertion order, not alphabetically sorted."""
        (tmp_path / "experience").mkdir()
        entry = {
            "type": "experience",
            "company": "Keyed Corp",
            "title": "Analyst",
            "dates": "2023 - 2024",
            "bullets": [],
        }

        path = save_entry(entry, tmp_path)
        loaded_text = path.read_text()
        loaded = yaml.safe_load(loaded_text)

        keys = list(loaded.keys())
        # "type" must come before "bullets" (non-alphabetical order preserved)
        assert keys.index("type") < keys.index("bullets")
        # "company" comes before "dates" (insertion order, not alpha)
        assert keys.index("company") < keys.index("dates")

    def test_creates_subdir_if_missing(self, tmp_path):
        """save_entry creates the target subdirectory if it does not exist."""
        entry = {"type": "education", "institution": "MIT", "degree": "BSc", "bullets": []}

        path = save_entry(entry, tmp_path)

        assert (tmp_path / "education").exists()
        assert path.exists()

    def test_other_type_uses_organization(self, tmp_path):
        """save_entry uses organization+title slug for 'other' entries."""
        entry = {"type": "other", "organization": "Hackspace", "title": "Organiser", "bullets": []}

        path = save_entry(entry, tmp_path)

        assert path.parent.name == "other"
        assert "hackspace" in path.name

    def test_round_trips_data(self, tmp_path):
        """Data written by save_entry can be loaded back identically."""
        entry = {
            "type": "experience",
            "company": "RoundTrip Inc",
            "title": "Tester",
            "dates": "2024",
            "tags": ["python", "pytest"],
            "bullets": [{"text": "Did things", "tags": ["python"]}],
        }

        path = save_entry(entry, tmp_path)
        loaded = yaml.safe_load(path.read_text())

        assert loaded["company"] == "RoundTrip Inc"
        assert loaded["tags"] == ["python", "pytest"]
        assert loaded["bullets"][0]["text"] == "Did things"


class TestDraftFromDescription:
    def _make_llm_client(self, return_value=None):
        """Build a MagicMock llm_client with a configurable invoke_structured response."""
        from pydantic import BaseModel

        class FakeDraftBullet(BaseModel):
            text: str
            tags: list[str] = []

        class FakeDraftedEntry(BaseModel):
            type: str = "experience"
            company: str | None = None
            institution: str | None = None
            organization: str | None = None
            title: str | None = None
            degree: str | None = None
            dates: str = ""
            location: str | None = None
            tags: list[str] = []
            priority: int = 1
            bullets: list[FakeDraftBullet] = []

        if return_value is None:
            return_value = FakeDraftedEntry(
                type="experience",
                company="Drafted Corp",
                title="Senior Dev",
                dates="2024",
                tags=["python"],
                bullets=[FakeDraftBullet(text="Built stuff", tags=["python"])],
            )

        client = MagicMock()
        client.available = True
        client.invoke_structured.return_value = return_value
        return client

    def test_calls_invoke_structured_once(self):
        """draft_from_description calls llm_client.invoke_structured exactly once."""
        client = self._make_llm_client()

        result = draft_from_description("I worked at Corp", existing_tags=["python"], llm_client=client)

        client.invoke_structured.assert_called_once()

    def test_returns_dict_with_expected_keys(self):
        """Result is a dict that contains at least 'type', 'bullets', 'tags', 'priority'."""
        client = self._make_llm_client()

        result = draft_from_description("I worked at Corp", existing_tags=["python"], llm_client=client)

        assert isinstance(result, dict)
        assert "type" in result
        assert "bullets" in result
        assert "tags" in result
        assert "priority" in result

    def test_propagates_llm_exception(self):
        """If invoke_structured raises, the exception propagates to the caller."""
        client = MagicMock()
        client.available = True
        client.invoke_structured.side_effect = Exception("LLM error")

        with pytest.raises(Exception, match="LLM error"):
            draft_from_description("Some description", existing_tags=[], llm_client=client)

    def test_bullets_serialized_as_dicts(self):
        """Bullets in the returned dict are plain dicts, not Pydantic models."""
        client = self._make_llm_client()

        result = draft_from_description("description", existing_tags=[], llm_client=client)

        for bullet in result["bullets"]:
            assert isinstance(bullet, dict)
            assert "text" in bullet

    def test_passes_description_in_prompt(self):
        """The description text is included in the prompt sent to the LLM."""
        client = self._make_llm_client()
        description = "unique_marker_xyz"

        draft_from_description(description, existing_tags=[], llm_client=client)

        call_args = client.invoke_structured.call_args
        prompt_arg = call_args[0][0]  # first positional arg is the prompt string
        assert description in prompt_arg

    def test_existing_tags_passed_to_prompt(self):
        """existing_tags are referenced in the prompt sent to the LLM."""
        client = self._make_llm_client()
        tags = ["pytorch", "langchain", "rag"]

        draft_from_description("Some job desc", existing_tags=tags, llm_client=client)

        call_args = client.invoke_structured.call_args
        prompt_arg = call_args[0][0]
        # At least one of the tags should appear in the prompt
        assert any(tag in prompt_arg for tag in tags)
