"""CV generation handlers."""

import re
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from tycho.db import get_job_by_prefix, get_session, update_job_paths
from tycho.telegram.db_async import run_sync
from tycho.telegram.keyboards import generate_options_keyboard


def _safe_filename(name: str) -> str:
    """Convert a string to a safe filename."""
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name[:80]


def _get_gen_opts(context: ContextTypes.DEFAULT_TYPE, job8: str) -> dict:
    """Get or initialize generation options for a job."""
    key = f"gen_{job8}"
    if key not in context.user_data:
        config = context.bot_data["config"]
        context.user_data[key] = {
            "lang": config.output.language,
            "fmt": config.output.formats[0] if config.output.formats else "pdf",
            "cl": False,
            "page": 1,
        }
    return context.user_data[key]


async def gen_options_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle gen:{job8}:{page} — show generation options."""
    query = update.callback_query
    parts = query.data.split(":")
    job8 = parts[1]
    page = int(parts[2]) if len(parts) > 2 and parts[2] else 1

    opts = _get_gen_opts(context, job8)
    opts["page"] = page

    engine = context.bot_data["engine"]
    session = await run_sync(get_session, engine)
    try:
        job, error = await run_sync(get_job_by_prefix, session, job8)
    finally:
        await run_sync(session.close)

    if error or not job:
        await query.answer(error or "Job not found.")
        return

    await query.answer()
    text = f"Generate CV \u2014 {job.title} @ {job.company}"
    keyboard = generate_options_keyboard(job8, page, opts["lang"], opts["fmt"], opts["cl"])
    await query.edit_message_text(text, reply_markup=keyboard)


async def gen_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle gen_opt:{job8}:{option} — toggle a generation option."""
    query = update.callback_query
    parts = query.data.split(":")
    job8 = parts[1]
    option = parts[2]

    opts = _get_gen_opts(context, job8)

    if option == "lang":
        opts["lang"] = "es" if opts["lang"] == "en" else "en"
    elif option == "fmt":
        cycle = ["pdf", "docx", "tex"]
        idx = cycle.index(opts["fmt"]) if opts["fmt"] in cycle else 0
        opts["fmt"] = cycle[(idx + 1) % len(cycle)]
    elif option == "cl":
        opts["cl"] = not opts["cl"]

    page = opts.get("page", 1)
    await query.answer()
    keyboard = generate_options_keyboard(job8, page, opts["lang"], opts["fmt"], opts["cl"])

    engine = context.bot_data["engine"]
    session = await run_sync(get_session, engine)
    try:
        job, _ = await run_sync(get_job_by_prefix, session, job8)
    finally:
        await run_sync(session.close)

    title = f"{job.title} @ {job.company}" if job else job8
    await query.edit_message_text(f"Generate CV \u2014 {title}", reply_markup=keyboard)


async def gen_exec_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle gen_exec:{job8}:{lang}:{fmt}:{cl} — execute CV generation."""
    query = update.callback_query
    parts = query.data.split(":")
    job8 = parts[1]
    lang = parts[2]
    fmt = parts[3]
    cl = parts[4] == "1"

    await query.answer()
    await query.edit_message_text("Generating CV... please wait.")

    engine = context.bot_data["engine"]
    config = context.bot_data["config"]

    session = await run_sync(get_session, engine)
    try:
        job, error = await run_sync(get_job_by_prefix, session, job8)
    finally:
        await run_sync(session.close)

    if error or not job:
        await query.edit_message_text(error or "Job not found.")
        return

    try:
        generated_paths = await run_sync(
            _run_generation, config, job, lang, fmt, cl
        )
    except Exception as e:
        await query.edit_message_text(f"Generation failed: {e}")
        return

    # Update DB with paths
    if generated_paths:
        session = await run_sync(get_session, engine)
        try:
            cv_path = next((p for p in generated_paths if Path(p).name.startswith("CV_")), None)
            cl_path = next((p for p in generated_paths if "CoverLetter" in Path(p).name), None)
            if cv_path or cl_path:
                await run_sync(update_job_paths, session, job.id,
                               cv_path=cv_path, cover_letter_path=cl_path)
                await run_sync(session.commit)
        finally:
            await run_sync(session.close)

    # Send files
    chat_id = query.message.chat_id
    for path_str in generated_paths:
        path = Path(path_str)
        if path.exists():
            await context.bot.send_document(chat_id=chat_id, document=path)

    summary = f"Generated {len(generated_paths)} file(s) for {job.title} @ {job.company}"
    await context.bot.send_message(chat_id=chat_id, text=summary)


def _run_generation(config, job, lang: str, fmt: str, cl: bool) -> list[str]:
    """Run CV generation synchronously. Returns list of file paths."""
    from tycho.cv.profile_loader import load_profile
    from tycho.cv.module_selector import select_modules

    profile = load_profile(config.profile_dir)

    llm_client = None
    if config.llm.enabled:
        try:
            from tycho.llm import get_llm_client
            client = get_llm_client(config.llm)
            if client.available:
                llm_client = client
        except Exception:
            pass

    tailored = select_modules(profile, job, language=lang, llm_client=llm_client)

    template_dir = Path(config.profile_dir) / "templates"
    output_dir = Path(config.output_dir) / _safe_filename(f"{job.company}_{job.title}")
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []

    if fmt == "pdf":
        from tycho.cv.latex_builder import build_pdf, build_tex
        pdf_path = output_dir / f"CV_{lang.upper()}.pdf"
        try:
            result = build_pdf(tailored, template_dir, pdf_path, language=lang, country=config.search.country)
            paths.append(str(result))
        except RuntimeError:
            tex_path = output_dir / f"CV_{lang.upper()}.tex"
            result = build_tex(tailored, template_dir, tex_path, language=lang, country=config.search.country)
            paths.append(str(result))
    elif fmt == "tex":
        from tycho.cv.latex_builder import build_tex
        tex_path = output_dir / f"CV_{lang.upper()}.tex"
        result = build_tex(tailored, template_dir, tex_path, language=lang, country=config.search.country)
        paths.append(str(result))
    elif fmt == "docx":
        from tycho.cv.docx_builder import build_docx
        docx_path = output_dir / f"CV_{lang.upper()}.docx"
        result = build_docx(tailored, docx_path, language=lang, country=config.search.country)
        paths.append(str(result))

    if cl and llm_client:
        from tycho.cover_letter.generator import generate_cover_letter, save_cover_letter
        try:
            cover = generate_cover_letter(
                job=job, profile=profile, tailored=tailored,
                llm_client=llm_client, config=config.cover_letter, language=lang,
            )
            txt_path = output_dir / f"CoverLetter_{lang.upper()}.txt"
            save_cover_letter(cover, txt_path, format="txt")
            paths.append(str(txt_path))

            docx_cl_path = output_dir / f"CoverLetter_{lang.upper()}.docx"
            save_cover_letter(cover, docx_cl_path, format="docx")
            paths.append(str(docx_cl_path))
        except Exception:
            pass

    return paths
