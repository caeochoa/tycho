"""Jinja2 → LaTeX → PDF compilation."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from tycho.models import TailoredProfile


def _latex_escape(text: str) -> str:
    """Escape special LaTeX characters."""
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    # Don't escape backslashes that are already LaTeX commands
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


def render_latex(
    profile: TailoredProfile,
    template_dir: str | Path,
    language: str = "en",
    country: str = "Spain",
    template: str = "ats_resume",
) -> str:
    """Render a LaTeX document from the tailored profile using Jinja2."""
    template_dir = Path(template_dir)

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        block_start_string="<%",
        block_end_string="%>",
        variable_start_string="{{",
        variable_end_string="}}",
        comment_start_string="<#",
        comment_end_string="#>",
    )

    # Don't auto-escape — we handle LaTeX escaping ourselves
    template_name = f"{template}_es.tex.j2" if language == "es" else f"{template}.tex.j2"
    tmpl = env.get_template(template_name)

    # Select phone based on country
    phone = profile.personal.phone_es if country == "Spain" else profile.personal.phone_uk

    return tmpl.render(p=profile, phone=phone, language=language)


def build_pdf(
    profile: TailoredProfile,
    template_dir: str | Path,
    output_path: str | Path,
    language: str = "en",
    country: str = "Spain",
    template: str = "ats_resume",
) -> Path:
    """Build a PDF from the tailored profile.

    Returns the path to the generated PDF.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Render LaTeX
    latex_content = render_latex(profile, template_dir, language, country, template=template)

    # Compile in a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "resume.tex"
        tex_path.write_text(latex_content, encoding="utf-8")

        # Try latexmk first, then pdflatex
        compiled = _compile_latex(tmpdir, tex_path)

        if compiled:
            pdf_source = Path(tmpdir) / "resume.pdf"
            if pdf_source.exists():
                shutil.copy2(pdf_source, output_path)
                return output_path

    raise RuntimeError(
        f"PDF compilation failed. Check that pdflatex or latexmk is installed. "
        f"LaTeX source saved for debugging."
    )


def build_tex(
    profile: TailoredProfile,
    template_dir: str | Path,
    output_path: str | Path,
    language: str = "en",
    country: str = "Spain",
    template: str = "ats_resume",
) -> Path:
    """Build just the .tex file (no compilation) for debugging."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    latex_content = render_latex(profile, template_dir, language, country, template=template)
    output_path.write_text(latex_content, encoding="utf-8")
    return output_path


def _compile_latex(tmpdir: str, tex_path: Path) -> bool:
    """Compile LaTeX to PDF. Returns True on success."""
    # Common LaTeX paths to check if not in PATH (especially for macOS)
    extra_paths = ["/Library/TeX/texbin", "/usr/texbin", "/usr/local/bin"]
    env = os.environ.copy()
    search_path = env.get("PATH", "")
    for p in extra_paths:
        if os.path.exists(p) and p not in search_path:
            search_path = f"{search_path}{os.pathsep}{p}"
    env["PATH"] = search_path

    # Try latexmk first
    latexmk_bin = shutil.which("latexmk", path=search_path)
    if latexmk_bin:
        result = subprocess.run(
            [latexmk_bin, "-pdf", "-interaction=nonstopmode", "-output-directory=" + tmpdir, str(tex_path)],
            capture_output=True,
            text=True,
            cwd=tmpdir,
            timeout=60,
            env=env,
        )
        if result.returncode == 0:
            return True

    # Fallback to pdflatex (run twice for references)
    pdflatex_bin = shutil.which("pdflatex", path=search_path)
    if pdflatex_bin:
        for _ in range(2):
            result = subprocess.run(
                [pdflatex_bin, "-interaction=nonstopmode", "-output-directory=" + tmpdir, str(tex_path)],
                capture_output=True,
                text=True,
                cwd=tmpdir,
                timeout=60,
                env=env,
            )
        return result.returncode == 0

    raise RuntimeError("Neither latexmk nor pdflatex found. Install a LaTeX distribution (TeX Live or MacTeX).")
