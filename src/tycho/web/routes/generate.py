"""CV generation routes."""

import re
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from tycho.config import TychoConfig
from tycho.db import get_job_by_prefix, update_job_paths
from tycho.web.deps import get_config, get_db, get_llm_client, get_templates

router = APIRouter(prefix="/generate", tags=["generate"])


def _safe_filename(name: str) -> str:
    """Convert a string to a safe filename."""
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name[:80]


@router.get("/{job_id}", response_class=HTMLResponse)
async def generate_preview(
    request: Request,
    job_id: str,
    session: Session = Depends(get_db),
    config: TychoConfig = Depends(get_config),
):
    """Show generation form with job description side-by-side."""
    templates = get_templates(request)
    job, error = get_job_by_prefix(session, job_id)

    if error:
        return templates.TemplateResponse(
            request,
            "generate/preview.html",
            {"request": request, "job": None, "error": error},
            status_code=404,
        )

    return templates.TemplateResponse(
        request,
        "generate/preview.html",
        {
            "request": request,
            "job": job,
            "error": None,
            "config": config,
            "result": None,
        },
    )


@router.post("/{job_id}", response_class=HTMLResponse)
async def generate_cv(
    request: Request,
    job_id: str,
    language: str = Form("en"),
    formats: str = Form("pdf"),
    cover_letter: bool = Form(False),
    no_llm: bool = Form(False),
    session: Session = Depends(get_db),
    config: TychoConfig = Depends(get_config),
):
    """Generate CV and return preview panel partial."""
    templates = get_templates(request)
    job, error = get_job_by_prefix(session, job_id)

    if error:
        return HTMLResponse(f"<p class='error'>{error}</p>", status_code=404)

    # Get LLM client
    llm_client = None
    if not no_llm:
        llm_client = get_llm_client(request)

    # Load profile and tailor
    from tycho.cv.profile_loader import load_profile
    from tycho.cv.module_selector import select_modules

    profile = load_profile(config.profile_dir)
    tailored = select_modules(profile, job, language=language, llm_client=llm_client)

    template_dir = Path(config.profile_dir) / "templates"
    output_dir = Path(config.output_dir) / _safe_filename(f"{job.company}_{job.title}")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_formats = [f.strip() for f in formats.split(",")]
    generated_files = []
    errors = []

    if "pdf" in output_formats:
        from tycho.cv.latex_builder import build_pdf, build_tex

        pdf_path = output_dir / f"CV_{language.upper()}.pdf"
        try:
            result = build_pdf(tailored, template_dir, pdf_path, language=language, country=config.search.country)
            generated_files.append(("PDF", str(result), result.name))
        except RuntimeError:
            tex_path = output_dir / f"CV_{language.upper()}.tex"
            result = build_tex(tailored, template_dir, tex_path, language=language, country=config.search.country)
            generated_files.append(("LaTeX", str(result), result.name))
            errors.append("PDF compilation failed, .tex source saved instead")

    if "tex" in output_formats:
        from tycho.cv.latex_builder import build_tex

        tex_path = output_dir / f"CV_{language.upper()}.tex"
        result = build_tex(tailored, template_dir, tex_path, language=language, country=config.search.country)
        generated_files.append(("LaTeX", str(result), result.name))

    if "docx" in output_formats:
        from tycho.cv.docx_builder import build_docx

        docx_path = output_dir / f"CV_{language.upper()}.docx"
        result = build_docx(tailored, docx_path, language=language, country=config.search.country)
        generated_files.append(("DOCX", str(result), result.name))

    # Cover letter
    cl_path = None
    if cover_letter and llm_client:
        from tycho.cover_letter.generator import generate_cover_letter, save_cover_letter

        try:
            cl = generate_cover_letter(
                job=job,
                profile=profile,
                tailored=tailored,
                llm_client=llm_client,
                config=config.cover_letter,
                language=language,
            )
            txt_path = output_dir / f"CoverLetter_{language.upper()}.txt"
            save_cover_letter(cl, txt_path, format="txt")
            generated_files.append(("Cover Letter (txt)", str(txt_path), txt_path.name))

            docx_cl_path = output_dir / f"CoverLetter_{language.upper()}.docx"
            save_cover_letter(cl, docx_cl_path, format="docx")
            generated_files.append(("Cover Letter (docx)", str(docx_cl_path), docx_cl_path.name))

            cl_path = str(txt_path)
        except Exception as e:
            errors.append(f"Cover letter failed: {e}")
    elif cover_letter and not llm_client:
        errors.append("Cover letter requires LLM. Configure an API key or enable LLM.")

    # Update DB paths
    cv_path_str = generated_files[0][1] if generated_files else None
    if cv_path_str or cl_path:
        update_job_paths(session, job.id, cv_path=cv_path_str, cover_letter_path=cl_path)
        session.commit()

    return templates.TemplateResponse(
        request,
        "generate/_preview_panel.html",
        {
            "request": request,
            "job": job,
            "generated_files": generated_files,
            "errors": errors,
            "output_dir": str(output_dir),
        },
    )


@router.get("/{job_id}/download/{filename}", response_class=FileResponse)
async def download_file(
    job_id: str,
    filename: str,
    session: Session = Depends(get_db),
    config: TychoConfig = Depends(get_config),
):
    """Serve a generated file for download."""
    job, error = get_job_by_prefix(session, job_id)
    if error:
        from fastapi.responses import JSONResponse

        return JSONResponse({"error": error}, status_code=404)

    output_dir = Path(config.output_dir) / _safe_filename(f"{job.company}_{job.title}")
    file_path = output_dir / filename

    if not file_path.exists() or not file_path.is_relative_to(output_dir):
        from fastapi.responses import JSONResponse

        return JSONResponse({"error": "File not found"}, status_code=404)

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )
