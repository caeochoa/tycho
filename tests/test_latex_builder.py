"""Tests for LaTeX rendering and PDF building."""

from pathlib import Path
from unittest.mock import patch

import pytest

from tycho.cv.latex_builder import _latex_escape, build_tex, render_latex
from tycho.cv.module_selector import select_modules


class TestLatexEscape:
    def test_ampersand(self):
        assert _latex_escape("A & B") == r"A \& B"

    def test_percent(self):
        assert _latex_escape("100%") == r"100\%"

    def test_dollar(self):
        assert _latex_escape("$100") == r"\$100"

    def test_hash(self):
        assert _latex_escape("#1") == r"\#1"

    def test_underscore(self):
        assert _latex_escape("a_b") == r"a\_b"

    def test_braces(self):
        assert _latex_escape("{test}") == r"\{test\}"

    def test_tilde(self):
        assert _latex_escape("~") == r"\textasciitilde{}"

    def test_caret(self):
        assert _latex_escape("^") == r"\textasciicircum{}"

    def test_plain_text_unchanged(self):
        assert _latex_escape("Hello World") == "Hello World"

    def test_multiple_specials(self):
        result = _latex_escape("A & B $ C")
        assert r"\&" in result
        assert r"\$" in result


class TestRenderLatex:
    def test_render_english(self, sample_profile, ml_job):
        tailored = select_modules(sample_profile, ml_job, language="en")
        template_dir = Path(__file__).parent.parent / "profile" / "templates"
        latex = render_latex(tailored, template_dir, language="en", country="Spain")

        assert r"\documentclass" in latex
        assert "Cesar Ochoa" in latex
        assert r"\section{Work Experience}" in latex
        assert r"\section{Education}" in latex
        assert "AI Engineer" in latex

    def test_render_spanish(self, sample_profile, ml_job):
        tailored = select_modules(sample_profile, ml_job, language="es")
        template_dir = Path(__file__).parent.parent / "profile" / "templates"
        latex = render_latex(tailored, template_dir, language="es", country="Spain")

        assert "César Ochoa Munárriz" in latex
        assert r"\section{Experiencia Laboral}" in latex
        assert r"\section{Formación}" in latex

    def test_phone_spain(self, sample_profile, ml_job):
        tailored = select_modules(sample_profile, ml_job, language="en")
        template_dir = Path(__file__).parent.parent / "profile" / "templates"
        latex = render_latex(tailored, template_dir, language="en", country="Spain")
        assert "+34 636 382 118" in latex

    def test_phone_uk(self, sample_profile, ml_job):
        tailored = select_modules(sample_profile, ml_job, language="en")
        template_dir = Path(__file__).parent.parent / "profile" / "templates"
        latex = render_latex(tailored, template_dir, language="en", country="UK")
        assert "+44 792 393 6908" in latex

    def test_ats_features(self, sample_profile, ml_job):
        tailored = select_modules(sample_profile, ml_job, language="en")
        template_dir = Path(__file__).parent.parent / "profile" / "templates"
        latex = render_latex(tailored, template_dir, language="en")

        # ATS-friendly features
        assert r"\pdfgentounicode=1" in latex
        assert r"\usepackage{lmodern}" in latex
        assert r"\usepackage[hidelinks]{hyperref}" in latex
        assert "fontawesome" not in latex.lower()
        assert "tikzpicture" not in latex.lower()
        assert "minipage" not in latex.lower()

    def test_contains_skills(self, sample_profile, ml_job):
        tailored = select_modules(sample_profile, ml_job, language="en")
        template_dir = Path(__file__).parent.parent / "profile" / "templates"
        latex = render_latex(tailored, template_dir, language="en")
        assert "Python" in latex
        assert "PyTorch" in latex

    def test_contains_linkedin(self, sample_profile, ml_job):
        tailored = select_modules(sample_profile, ml_job, language="en")
        template_dir = Path(__file__).parent.parent / "profile" / "templates"
        latex = render_latex(tailored, template_dir, language="en")
        assert "linkedin.com/in/caeochoa" in latex


class TestBuildTex:
    def test_creates_tex_file(self, sample_profile, ml_job, tmp_path):
        tailored = select_modules(sample_profile, ml_job, language="en")
        template_dir = Path(__file__).parent.parent / "profile" / "templates"
        output_path = tmp_path / "output" / "test.tex"

        result = build_tex(tailored, template_dir, output_path)
        assert result.exists()
        content = result.read_text()
        assert r"\documentclass" in content

    def test_creates_parent_dirs(self, sample_profile, ml_job, tmp_path):
        tailored = select_modules(sample_profile, ml_job, language="en")
        template_dir = Path(__file__).parent.parent / "profile" / "templates"
        output_path = tmp_path / "deep" / "nested" / "dir" / "test.tex"

        result = build_tex(tailored, template_dir, output_path)
        assert result.exists()

    def test_template_not_found(self, sample_profile, ml_job, tmp_path):
        tailored = select_modules(sample_profile, ml_job, language="en")
        with pytest.raises(Exception):
            build_tex(tailored, tmp_path / "nonexistent", tmp_path / "out.tex")
