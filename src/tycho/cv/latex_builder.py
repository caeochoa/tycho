"""Jinja2 → LaTeX → PDF compilation."""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jinja2 import BaseLoader, Environment

from tycho.models import TailoredProfile


@dataclass
class TemplateMetadata:
    name: str
    folder: Path
    template_file: Path   # path to cv.tex.j2 (new format) or flat .tex.j2 (legacy)
    is_legacy: bool
    params: dict[str, dict]  # param_name → {type, default, label?, options?}
    ats_friendly: bool = True
    languages: list[str] = field(default_factory=lambda: ["en", "es"])


def discover_templates(templates_dir: Path) -> dict[str, TemplateMetadata]:
    """Scan templates_dir for available templates.

    Supports two formats:
    - New format: subdirectory with template.yaml + cv.tex.j2
    - Legacy format: flat *.tex.j2 files (excluding *_es.tex.j2 variants)

    Returns a dict keyed by folder name (new) or filename stem (legacy).
    """
    if not templates_dir.exists():
        return {}

    result: dict[str, TemplateMetadata] = {}

    # Scan subdirectories for new-format templates
    for subdir in sorted(templates_dir.iterdir()):
        if not subdir.is_dir():
            continue
        template_yaml = subdir / "template.yaml"
        cv_tex = subdir / "cv.tex.j2"
        if template_yaml.exists() and cv_tex.exists():
            with open(template_yaml) as f:
                meta = yaml.safe_load(f) or {}
            result[subdir.name] = TemplateMetadata(
                name=meta.get("name", subdir.name),
                folder=subdir,
                template_file=cv_tex,
                is_legacy=False,
                params=meta.get("params", {}),
                ats_friendly=meta.get("ats_friendly", True),
                languages=meta.get("languages", ["en", "es"]),
            )

    # Scan flat *.tex.j2 files for legacy templates (skip *_es.tex.j2 variants)
    for tex_file in sorted(templates_dir.glob("*.tex.j2")):
        if tex_file.name.endswith("_es.tex.j2"):
            continue
        stem = tex_file.stem  # e.g. "ats_resume" from "ats_resume.tex.j2"
        # Remove the extra .tex suffix that remains after .stem strips .j2
        if stem.endswith(".tex"):
            stem = stem[:-4]
        if stem not in result:  # new-format takes precedence
            result[stem] = TemplateMetadata(
                name=stem,
                folder=templates_dir,
                template_file=tex_file,
                is_legacy=True,
                params={},
                ats_friendly=True,
                languages=["en", "es"],
            )

    return result


def load_template(
    name: str,
    config_params: dict,
    cli_params: dict,
    templates_dir: Path,
    language: str = "en",
) -> tuple[str, list[Path], "TemplateMetadata | None"]:
    """Load a template by name and return (template_string, cls_files, metadata).

    Merges params: template defaults → config_params → cli_params.
    For legacy templates, selects the _es variant when language == "es".
    Returns the raw Jinja2 template string (not yet rendered) plus the metadata
    object so callers avoid a second discover_templates() scan.
    """
    templates = discover_templates(templates_dir)

    if name not in templates:
        available = ", ".join(sorted(templates.keys())) if templates else "(none found)"
        raise ValueError(f"Template '{name}' not found. Available: {available}")

    meta = templates[name]

    if not meta.is_legacy:
        # New format: single cv.tex.j2 handles language internally
        template_string = meta.template_file.read_text(encoding="utf-8")
        cls_files = list(meta.folder.glob("*.cls"))
        return template_string, cls_files, meta
    else:
        # Legacy format: select _es variant if available
        if language == "es":
            es_file = meta.folder / f"{name}_es.tex.j2"
            template_file = es_file if es_file.exists() else meta.template_file
        else:
            template_file = meta.template_file
        template_string = template_file.read_text(encoding="utf-8")
        return template_string, [], meta


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


def _make_jinja_env(template_string: str) -> tuple[Environment, str]:
    """Create a Jinja2 environment for LaTeX rendering from a template string."""
    env = Environment(
        loader=BaseLoader(),
        block_start_string="<%",
        block_end_string="%>",
        variable_start_string="{{",
        variable_end_string="}}",
        comment_start_string="<#",
        comment_end_string="#>",
    )
    return env, template_string


def render_latex(
    profile: TailoredProfile,
    template_dir: str | Path,
    language: str = "en",
    country: str = "Spain",
    template: str = "ats_resume",
    template_params: dict[str, Any] | None = None,
    config_params: dict[str, Any] | None = None,
    cli_params: dict[str, Any] | None = None,
) -> str:
    """Render a LaTeX document from the tailored profile using Jinja2."""
    template_dir = Path(template_dir)
    _config_params = config_params or {}
    _cli_params = cli_params or {}

    template_string, _cls_files, meta = load_template(
        name=template,
        config_params=_config_params,
        cli_params=_cli_params,
        templates_dir=template_dir,
        language=language,
    )

    # Build merged params for rendering context
    merged_params: dict[str, Any] = {}
    if meta and not meta.is_legacy:
        # Start with template defaults
        for pname, pdef in meta.params.items():
            if "default" in pdef:
                merged_params[pname] = pdef["default"]
        # Override with config params, then CLI params
        merged_params.update(_config_params)
        merged_params.update(_cli_params)
    elif template_params:
        merged_params = dict(template_params)

    env, tpl_str = _make_jinja_env(template_string)
    tmpl = env.from_string(tpl_str)

    # Select phone based on country
    phone = profile.personal.phone_es if country == "Spain" else profile.personal.phone_uk

    return tmpl.render(p=profile, phone=phone, language=language, params=merged_params)


def build_pdf(
    profile: TailoredProfile,
    template_dir: str | Path,
    output_path: str | Path,
    language: str = "en",
    country: str = "Spain",
    template: str = "ats_resume",
    template_params: dict[str, Any] | None = None,
    config_params: dict[str, Any] | None = None,
    cli_params: dict[str, Any] | None = None,
) -> Path:
    """Build a PDF from the tailored profile.

    Returns the path to the generated PDF.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    template_dir = Path(template_dir)
    _config_params = config_params or {}
    _cli_params = cli_params or {}

    # Load template and collect .cls files
    template_string, cls_files, meta = load_template(
        name=template,
        config_params=_config_params,
        cli_params=_cli_params,
        templates_dir=template_dir,
        language=language,
    )

    # Build merged params for rendering context
    merged_params: dict[str, Any] = {}
    if meta and not meta.is_legacy:
        for pname, pdef in meta.params.items():
            if "default" in pdef:
                merged_params[pname] = pdef["default"]
        merged_params.update(_config_params)
        merged_params.update(_cli_params)
    elif template_params:
        merged_params = dict(template_params)

    env, tpl_str = _make_jinja_env(template_string)
    tmpl = env.from_string(tpl_str)
    phone = profile.personal.phone_es if country == "Spain" else profile.personal.phone_uk
    latex_content = tmpl.render(p=profile, phone=phone, language=language, params=merged_params)

    # Compile in a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "resume.tex"
        tex_path.write_text(latex_content, encoding="utf-8")

        # Copy .cls files to tmpdir
        for cls_file in cls_files:
            shutil.copy2(cls_file, Path(tmpdir) / cls_file.name)

        # Copy photo if show_photo param is set and photo_path is provided
        if merged_params.get("show_photo") and profile.personal.photo_path:
            photo_src = Path(profile.personal.photo_path)
            if photo_src.exists():
                shutil.copy2(photo_src, Path(tmpdir) / photo_src.name)

        # Try latexmk first, then pdflatex
        compiled = _compile_latex(tmpdir, tex_path)

        if compiled:
            pdf_source = Path(tmpdir) / "resume.pdf"
            if pdf_source.exists():
                shutil.copy2(pdf_source, output_path)
                return output_path

    raise RuntimeError(
        "PDF compilation failed. Check that pdflatex or latexmk is installed. "
        "Use --format tex to save the LaTeX source for debugging."
    )


def build_tex(
    profile: TailoredProfile,
    template_dir: str | Path,
    output_path: str | Path,
    language: str = "en",
    country: str = "Spain",
    template: str = "ats_resume",
    template_params: dict[str, Any] | None = None,
    config_params: dict[str, Any] | None = None,
    cli_params: dict[str, Any] | None = None,
) -> Path:
    """Build just the .tex file (no compilation) for debugging."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    latex_content = render_latex(
        profile,
        template_dir,
        language,
        country,
        template=template,
        template_params=template_params,
        config_params=config_params,
        cli_params=cli_params,
    )
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
