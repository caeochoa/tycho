"""Tests for template discovery and param merging in latex_builder.py."""

from pathlib import Path

import pytest
import yaml

from tycho.cv.latex_builder import TemplateMetadata, discover_templates, load_template, render_latex


class TestDiscoverTemplates:
    def test_discovers_new_format(self, tmp_path):
        """New-format template (subdir with template.yaml + cv.tex.j2) is found."""
        tpl_dir = tmp_path / "my_template"
        tpl_dir.mkdir()
        (tpl_dir / "template.yaml").write_text(
            yaml.dump({
                "name": "My Template",
                "ats_friendly": False,
                "languages": ["en"],
                "params": {"accent_color": {"type": "color", "default": "#0e76a8", "label": "Accent"}},
            })
        )
        (tpl_dir / "cv.tex.j2").write_text("Hello {{ params.accent_color }}")

        result = discover_templates(tmp_path)

        assert "my_template" in result
        meta = result["my_template"]
        assert meta.is_legacy is False
        assert meta.ats_friendly is False
        assert meta.languages == ["en"]
        assert "accent_color" in meta.params
        assert meta.params["accent_color"]["default"] == "#0e76a8"

    def test_discovers_legacy(self, tmp_path):
        """Flat *.tex.j2 files are discovered as legacy templates with empty params."""
        (tmp_path / "my_legacy.tex.j2").write_text(r"\documentclass{article}")

        result = discover_templates(tmp_path)

        assert "my_legacy" in result
        meta = result["my_legacy"]
        assert meta.is_legacy is True
        assert meta.params == {}

    def test_skips_es_variants(self, tmp_path):
        """*_es.tex.j2 files are not returned as separate templates."""
        (tmp_path / "my_legacy.tex.j2").write_text(r"\documentclass{article}")
        (tmp_path / "my_legacy_es.tex.j2").write_text(r"\documentclass{article}")

        result = discover_templates(tmp_path)

        assert "my_legacy" in result
        assert "my_legacy_es" not in result

    def test_empty_dir(self, tmp_path):
        """Nonexistent directory returns empty dict without error."""
        nonexistent = tmp_path / "does_not_exist"
        result = discover_templates(nonexistent)
        assert result == {}

    def test_empty_existing_dir(self, tmp_path):
        """Empty directory returns empty dict."""
        result = discover_templates(tmp_path)
        assert result == {}

    def test_new_format_takes_precedence_over_legacy(self, tmp_path):
        """If a subdirectory and a flat file share the same name, new format wins."""
        # Create new-format template named "shared"
        subdir = tmp_path / "shared"
        subdir.mkdir()
        (subdir / "template.yaml").write_text(yaml.dump({"name": "Shared New"}))
        (subdir / "cv.tex.j2").write_text("new format")

        # Create legacy flat file with same stem
        (tmp_path / "shared.tex.j2").write_text("legacy format")

        result = discover_templates(tmp_path)

        assert "shared" in result
        assert result["shared"].is_legacy is False


class TestLoadTemplate:
    def _make_new_template(self, base: Path, name: str = "my_tpl", params: dict | None = None) -> Path:
        tpl_dir = base / name
        tpl_dir.mkdir(parents=True, exist_ok=True)
        meta = {"name": name, "params": params or {}}
        (tpl_dir / "template.yaml").write_text(yaml.dump(meta))
        (tpl_dir / "cv.tex.j2").write_text("color={{ params.accent_color }}")
        return base

    def test_returns_three_tuple(self, tmp_path):
        """load_template returns (str, list, TemplateMetadata | None)."""
        self._make_new_template(tmp_path, params={"accent_color": {"type": "color", "default": "#abc"}})
        template_str, cls_files, meta = load_template(
            "my_tpl", config_params={}, cli_params={}, templates_dir=tmp_path
        )
        assert isinstance(template_str, str)
        assert isinstance(cls_files, list)
        assert isinstance(meta, TemplateMetadata)

    def test_raises_on_missing_template(self, tmp_path):
        """ValueError with 'not found' is raised for unknown template names."""
        with pytest.raises(ValueError, match="not found"):
            load_template("nonexistent", config_params={}, cli_params={}, templates_dir=tmp_path)

    def test_loads_params_from_metadata(self, tmp_path):
        """load_template returns metadata with params loaded from template.yaml."""
        self._make_new_template(
            tmp_path,
            params={"accent_color": {"type": "color", "default": "#0e76a8"}},
        )
        _, _, meta = load_template(
            "my_tpl", config_params={"accent_color": "#ff0000"}, cli_params={}, templates_dir=tmp_path
        )
        assert meta is not None
        assert "accent_color" in meta.params
        assert meta.params["accent_color"]["default"] == "#0e76a8"

    def test_legacy_es_variant_selected(self, tmp_path):
        """For legacy templates, _es variant is used when language='es'."""
        (tmp_path / "my_legacy.tex.j2").write_text("english content")
        (tmp_path / "my_legacy_es.tex.j2").write_text("spanish content")

        template_str, _, _ = load_template(
            "my_legacy", config_params={}, cli_params={}, templates_dir=tmp_path, language="es"
        )
        assert "spanish content" in template_str

    def test_legacy_falls_back_to_en_when_no_es_file(self, tmp_path):
        """For legacy templates without _es variant, English template is used."""
        (tmp_path / "my_legacy.tex.j2").write_text("english only")

        template_str, _, _ = load_template(
            "my_legacy", config_params={}, cli_params={}, templates_dir=tmp_path, language="es"
        )
        assert "english only" in template_str


class TestRenderLatexParamMerging:
    """Test that render_latex correctly merges template defaults → config → cli params."""

    def _make_color_template(self, base: Path, default_color: str = "#0e76a8") -> Path:
        """Create a minimal new-format template that renders the accent_color param."""
        tpl_dir = base / "color_tpl"
        tpl_dir.mkdir(parents=True, exist_ok=True)
        params_spec = {"accent_color": {"type": "color", "default": default_color}}
        (tpl_dir / "template.yaml").write_text(yaml.dump({"name": "Color Tpl", "params": params_spec}))
        # Template outputs the color without the '#' prefix for easy assertion
        (tpl_dir / "cv.tex.j2").write_text("{{ params.accent_color | replace('#', '') }}")
        return base

    def _minimal_profile(self):
        """Return a minimal TailoredProfile for rendering tests."""
        from tycho.models import PersonalInfo, TailoredProfile

        personal = PersonalInfo(name="Test User", email="test@example.com")
        return TailoredProfile(personal=personal)

    def test_template_default_used_when_no_overrides(self, tmp_path):
        self._make_color_template(tmp_path, default_color="#0e76a8")
        profile = self._minimal_profile()

        output = render_latex(
            profile,
            template_dir=tmp_path,
            template="color_tpl",
            config_params={},
            cli_params={},
        )
        assert "0e76a8" in output

    def test_config_params_override_template_default(self, tmp_path):
        self._make_color_template(tmp_path, default_color="#0e76a8")
        profile = self._minimal_profile()

        output = render_latex(
            profile,
            template_dir=tmp_path,
            template="color_tpl",
            config_params={"accent_color": "#ff0000"},
            cli_params={},
        )
        assert "ff0000" in output
        assert "0e76a8" not in output

    def test_cli_params_override_config_params(self, tmp_path):
        self._make_color_template(tmp_path, default_color="#0e76a8")
        profile = self._minimal_profile()

        output = render_latex(
            profile,
            template_dir=tmp_path,
            template="color_tpl",
            config_params={"accent_color": "#ff0000"},
            cli_params={"accent_color": "#00ff00"},
        )
        assert "00ff00" in output
        assert "ff0000" not in output
        assert "0e76a8" not in output
