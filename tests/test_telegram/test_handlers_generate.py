"""Tests for CV generation handlers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tycho.telegram.handlers.generate import (
    _get_gen_opts,
    _safe_filename,
    gen_exec_callback,
    gen_options_callback,
    gen_toggle_callback,
)


class TestSafeFilename:
    def test_normal_name(self):
        assert _safe_filename("DeepTech AI_ML Engineer") == "DeepTech_AI_ML_Engineer"

    def test_special_chars(self):
        result = _safe_filename("Corp & Co (US) / Remote")
        assert "&" not in result
        assert "/" not in result
        assert "(" not in result

    def test_truncation(self):
        long_name = "A" * 200
        assert len(_safe_filename(long_name)) <= 80

    def test_whitespace(self):
        assert _safe_filename("  hello   world  ") == "hello_world"


class TestGetGenOpts:
    def test_initializes_defaults(self, make_context):
        ctx = make_context()
        ctx.bot_data["config"].output.language = "en"
        ctx.bot_data["config"].output.formats = ["pdf"]
        opts = _get_gen_opts(ctx, "abc12345")
        assert opts["lang"] == "en"
        assert opts["fmt"] == "pdf"
        assert opts["cl"] is False
        assert opts["tpl"] == "ats_resume"

    def test_returns_existing(self, make_context):
        ctx = make_context(user_data={"gen_abc12345": {"lang": "es", "fmt": "docx", "cl": True, "tpl": "developer_cv", "page": 2}})
        opts = _get_gen_opts(ctx, "abc12345")
        assert opts["lang"] == "es"
        assert opts["fmt"] == "docx"
        assert opts["cl"] is True
        assert opts["tpl"] == "developer_cv"


@pytest.mark.asyncio
class TestGenOptionsCallback:
    async def test_shows_generation_options(self, make_callback_update, make_context):
        update = make_callback_update("gen:aaaaaaaa:1")
        ctx = make_context()
        await gen_options_callback(update, ctx)
        update.callback_query.answer.assert_awaited_once()
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "Generate CV" in text
        assert "ML Engineer" in text

    async def test_job_not_found(self, make_callback_update, make_context):
        update = make_callback_update("gen:zzzzzzzz:1")
        ctx = make_context()
        await gen_options_callback(update, ctx)
        answer_text = update.callback_query.answer.call_args[0][0]
        assert "not found" in answer_text.lower()


@pytest.mark.asyncio
class TestGenToggleCallback:
    async def test_toggle_language(self, make_callback_update, make_context):
        ctx = make_context()
        # Initialize opts
        ctx.user_data["gen_aaaaaaaa"] = {"lang": "en", "fmt": "pdf", "cl": False, "page": 1}

        update = make_callback_update("gen_opt:aaaaaaaa:lang")
        await gen_toggle_callback(update, ctx)
        assert ctx.user_data["gen_aaaaaaaa"]["lang"] == "es"

        # Toggle again
        update2 = make_callback_update("gen_opt:aaaaaaaa:lang")
        await gen_toggle_callback(update2, ctx)
        assert ctx.user_data["gen_aaaaaaaa"]["lang"] == "en"

    async def test_toggle_format(self, make_callback_update, make_context):
        ctx = make_context()
        ctx.user_data["gen_aaaaaaaa"] = {"lang": "en", "fmt": "pdf", "cl": False, "page": 1}

        update = make_callback_update("gen_opt:aaaaaaaa:fmt")
        await gen_toggle_callback(update, ctx)
        assert ctx.user_data["gen_aaaaaaaa"]["fmt"] == "docx"

        update2 = make_callback_update("gen_opt:aaaaaaaa:fmt")
        await gen_toggle_callback(update2, ctx)
        assert ctx.user_data["gen_aaaaaaaa"]["fmt"] == "tex"

        update3 = make_callback_update("gen_opt:aaaaaaaa:fmt")
        await gen_toggle_callback(update3, ctx)
        assert ctx.user_data["gen_aaaaaaaa"]["fmt"] == "pdf"

    async def test_toggle_template(self, make_callback_update, make_context):
        ctx = make_context()
        ctx.user_data["gen_aaaaaaaa"] = {"lang": "en", "fmt": "pdf", "cl": False, "tpl": "ats_resume", "page": 1}

        update = make_callback_update("gen_opt:aaaaaaaa:tpl")
        await gen_toggle_callback(update, ctx)
        assert ctx.user_data["gen_aaaaaaaa"]["tpl"] == "developer_cv"

        update2 = make_callback_update("gen_opt:aaaaaaaa:tpl")
        await gen_toggle_callback(update2, ctx)
        assert ctx.user_data["gen_aaaaaaaa"]["tpl"] == "ats_resume"

    async def test_toggle_cover_letter(self, make_callback_update, make_context):
        ctx = make_context()
        ctx.user_data["gen_aaaaaaaa"] = {"lang": "en", "fmt": "pdf", "cl": False, "page": 1}

        update = make_callback_update("gen_opt:aaaaaaaa:cl")
        await gen_toggle_callback(update, ctx)
        assert ctx.user_data["gen_aaaaaaaa"]["cl"] is True

        update2 = make_callback_update("gen_opt:aaaaaaaa:cl")
        await gen_toggle_callback(update2, ctx)
        assert ctx.user_data["gen_aaaaaaaa"]["cl"] is False


@pytest.mark.asyncio
class TestGenExecCallback:
    async def test_job_not_found(self, make_callback_update, make_context):
        update = make_callback_update("gen_exec:zzzzzzzz:en:pdf:0:ats_resume")
        ctx = make_context()
        await gen_exec_callback(update, ctx)
        # First edit is "Generating...", second is error
        calls = update.callback_query.edit_message_text.call_args_list
        assert any("not found" in str(c).lower() for c in calls)

    async def test_generation_failure(self, make_callback_update, make_context):
        update = make_callback_update("gen_exec:aaaaaaaa:en:pdf:0:ats_resume")
        ctx = make_context()

        with patch(
            "tycho.telegram.handlers.generate._run_generation",
            side_effect=RuntimeError("LaTeX not found"),
        ):
            await gen_exec_callback(update, ctx)

        calls = update.callback_query.edit_message_text.call_args_list
        assert any("failed" in str(c).lower() for c in calls)

    async def test_successful_generation(self, make_callback_update, make_context, tmp_path):
        # Create a fake output file
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_text("fake pdf content")

        update = make_callback_update("gen_exec:aaaaaaaa:en:pdf:0:ats_resume")
        ctx = make_context()

        with patch(
            "tycho.telegram.handlers.generate._run_generation",
            return_value=[str(fake_pdf)],
        ):
            await gen_exec_callback(update, ctx)

        # Should send document
        ctx.bot.send_document.assert_awaited_once()
        # Should send summary
        ctx.bot.send_message.assert_awaited_once()
        summary_text = ctx.bot.send_message.call_args[1]["text"]
        assert "1 file" in summary_text

    async def test_successful_generation_updates_db(self, make_callback_update, make_context, tmp_path):
        from tycho.db import get_job_by_id, get_session
        
        # Create fake output files
        cv_pdf = tmp_path / "CV_EN.pdf"
        cv_pdf.write_text("cv content")
        cl_docx = tmp_path / "CoverLetter_EN.docx"
        cl_docx.write_text("cl content")

        update = make_callback_update("gen_exec:aaaaaaaa:en:pdf:1:ats_resume")
        ctx = make_context()
        engine = ctx.bot_data["engine"]

        with patch(
            "tycho.telegram.handlers.generate._run_generation",
            return_value=[str(cv_pdf), str(cl_docx)],
        ):
            await gen_exec_callback(update, ctx)

        # Verify DB update
        session = get_session(engine)
        try:
            job = get_job_by_id(session, "aaaaaaaa-1111-2222-3333-444444444444")
            assert job.cv_path == str(cv_pdf)
            assert job.cover_letter_path == str(cl_docx)
        finally:
            session.close()
