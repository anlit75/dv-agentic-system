# LICENSE HEADER MANAGED BY add-license-header
#
# SPDX-FileCopyrightText: 2026 Ting-An Cheng
# SPDX-License-Identifier: MIT
#

"""Tests for dv_agentic.cli.install_agents private helpers."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dv_agentic.cli.install_agents import (
    _AGENT_META,
    _TARGETS,
    _install_assets,
    _remove_existing_link,
    _symlink_asset,
    _write_agent_file,
)

# ---------------------------------------------------------------------------
# _remove_existing_link
# ---------------------------------------------------------------------------


def test_remove_existing_link_no_link(tmp_path: Path) -> None:
    """Returns False and does nothing when link does not exist."""
    link = tmp_path / "ghost"
    assert _remove_existing_link(link, force=False) is False
    assert _remove_existing_link(link, force=True) is False


def test_remove_existing_link_exists_no_force(tmp_path: Path) -> None:
    """Returns True (skip) when link exists and force is False."""
    link = tmp_path / "existing.txt"
    link.write_text("x", encoding="utf-8")
    assert _remove_existing_link(link, force=False) is True
    assert link.exists()  # untouched


def test_remove_existing_link_file_with_force(tmp_path: Path) -> None:
    """Removes a regular file and returns False when force is True."""
    link = tmp_path / "existing.txt"
    link.write_text("x", encoding="utf-8")
    assert _remove_existing_link(link, force=True) is False
    assert not link.exists()


def test_remove_existing_link_dir_with_force(tmp_path: Path) -> None:
    """Calls rmtree on a real directory (not a symlink) when force is True."""
    link = tmp_path / "existing_dir"
    link.mkdir()
    (link / "child.txt").write_text("data", encoding="utf-8")
    assert _remove_existing_link(link, force=True) is False
    assert not link.exists()


# ---------------------------------------------------------------------------
# _symlink_asset — fallback to copy when symlink raises OSError
# ---------------------------------------------------------------------------


def test_symlink_asset_dir_falls_back_to_copytree(tmp_path: Path) -> None:
    """Falls back to shutil.copytree when symlink_to raises OSError (dir asset)."""
    src = tmp_path / "src_dir"
    src.mkdir()
    (src / "file.md").write_text("content", encoding="utf-8")

    link = tmp_path / "link_dir"

    with patch.object(Path, "symlink_to", side_effect=OSError("no symlink")):
        _symlink_asset(src, link, tmp_path, is_dir=True)

    assert link.is_dir()
    assert (link / "file.md").read_text(encoding="utf-8") == "content"


def test_symlink_asset_file_falls_back_to_copy2(tmp_path: Path) -> None:
    """Falls back to shutil.copy2 when symlink_to raises OSError (file asset)."""
    src = tmp_path / "tool.sh"
    src.write_text("#!/bin/bash", encoding="utf-8")

    link = tmp_path / "link_tool.sh"

    with patch.object(Path, "symlink_to", side_effect=OSError("no symlink")):
        _symlink_asset(src, link, tmp_path, is_dir=False)

    assert link.exists()
    assert link.read_text(encoding="utf-8") == "#!/bin/bash"


# ---------------------------------------------------------------------------
# _install_assets — end-to-end (real filesystem via tmp_path)
# ---------------------------------------------------------------------------


@pytest.fixture()
def skills_src(tmp_path: Path) -> Path:
    src = tmp_path / "skills"
    src.mkdir()
    skill = src / "my-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("# Skill", encoding="utf-8")
    return src


@pytest.fixture()
def tools_src(tmp_path: Path) -> Path:
    src = tmp_path / "tools"
    src.mkdir()
    (src / "my-tool.sh").write_text("#!/bin/bash", encoding="utf-8")
    return src


def _skill_link(project_root: Path) -> Path:
    return project_root / _TARGETS["skills"][0] / "my-skill"


def _tool_link(project_root: Path) -> Path:
    return project_root / _TARGETS["tools"][0] / "my-tool.sh"


def test_install_assets_dir_asset_creates_entry(skills_src: Path, tmp_path: Path) -> None:
    """Directory asset results in a symlink or directory copy in the target."""
    _install_assets(skills_src, "skills", tmp_path)
    link = _skill_link(tmp_path)
    assert link.exists(), f"expected {link} to exist"


def test_install_assets_file_asset_creates_entry(tools_src: Path, tmp_path: Path) -> None:
    """File asset results in a symlink or file copy in the target."""
    _install_assets(tools_src, "tools", tmp_path)
    link = _tool_link(tmp_path)
    assert link.exists(), f"expected {link} to exist"


def test_install_assets_no_overwrite_when_force_false(skills_src: Path, tmp_path: Path) -> None:
    """Existing entry is NOT replaced when force=False."""
    _install_assets(skills_src, "skills", tmp_path)
    link = _skill_link(tmp_path)

    # Write a sentinel file inside the existing dir/copy to detect replacement.
    if link.is_dir() and not link.is_symlink():
        sentinel = link / "_sentinel"
        sentinel.write_text("keep", encoding="utf-8")

    _install_assets(skills_src, "skills", tmp_path, force=False)

    if link.is_dir() and not link.is_symlink():
        assert sentinel.exists(), "sentinel should survive a no-force re-install"


def test_install_assets_overwrites_when_force_true(skills_src: Path, tmp_path: Path) -> None:
    """Existing entry IS replaced when force=True."""
    _install_assets(skills_src, "skills", tmp_path)
    link = _skill_link(tmp_path)

    # If the first install produced a real directory, plant a sentinel.
    if link.is_dir() and not link.is_symlink():
        sentinel = link / "_sentinel"
        sentinel.write_text("keep", encoding="utf-8")
        _install_assets(skills_src, "skills", tmp_path, force=True)
        assert not sentinel.exists(), "sentinel should be gone after force re-install"
    else:
        # It's a symlink — just verify it still exists after a force re-install.
        _install_assets(skills_src, "skills", tmp_path, force=True)
        assert link.exists()


def test_install_assets_real_dir_replaced_by_rmtree_on_force(tmp_path: Path) -> None:
    """A pre-existing real directory (not a symlink) is rmtree'd and recreated on force."""
    src = tmp_path / "skills"
    src.mkdir()
    skill = src / "alpha"
    skill.mkdir()
    (skill / "SKILL.md").write_text("# alpha", encoding="utf-8")

    target_dir = tmp_path / _TARGETS["skills"][0] / "alpha"
    target_dir.mkdir(parents=True)
    (target_dir / "stale.txt").write_text("old", encoding="utf-8")

    _install_assets(src, "skills", tmp_path, force=True)

    assert target_dir.exists()
    assert not (target_dir / "stale.txt").exists(), "stale file should be gone"


def test_install_assets_skips_private_assets(tmp_path: Path) -> None:
    """Assets whose names start with '.' are ignored; '_'-prefixed assets are installed."""
    src = tmp_path / "tools"
    src.mkdir()
    (src / "_run_agent.sh").write_text("helper", encoding="utf-8")
    (src / ".hidden.sh").write_text("hidden", encoding="utf-8")
    (src / "public.sh").write_text("public", encoding="utf-8")

    _install_assets(src, "tools", tmp_path)

    target = tmp_path / _TARGETS["tools"][0]
    assert (target / "_run_agent.sh").exists(), "_run_agent.sh should be installed"
    assert not (target / ".hidden.sh").exists()
    assert (target / "public.sh").exists()


def test_install_assets_noop_when_src_missing(tmp_path: Path) -> None:
    """_install_assets returns silently when the source directory does not exist."""
    missing = tmp_path / "nonexistent"
    _install_assets(missing, "tools", tmp_path)  # should not raise


# ---------------------------------------------------------------------------
# _write_agent_file
# ---------------------------------------------------------------------------


def test_write_agent_file_calls_strip_and_build_front_matter(tmp_path: Path) -> None:
    """_write_agent_file pipes raw content through _strip_front_matter and _build_front_matter."""
    raw = "---\nname: orchestrator\n---\n\nbody text"
    loader = MagicMock()
    loader.load.return_value = raw

    target = tmp_path / "orchestrator.md"

    with (
        patch(
            "dv_agentic.cli.install_agents._strip_front_matter",
            return_value="body text",
        ) as mock_strip,
        patch(
            "dv_agentic.cli.install_agents._build_front_matter",
            return_value="---\nfm\n---\n\n",
        ) as mock_build,
    ):
        _write_agent_file("orchestrator", loader, target, tmp_path)

    mock_strip.assert_called_once_with(raw)
    mock_build.assert_called_once_with("orchestrator", _AGENT_META["orchestrator"])

    content = target.read_text(encoding="utf-8")
    assert content == "---\nfm\n---\n\nbody text\n"


def test_write_agent_file_unknown_agent_uses_default_meta(tmp_path: Path) -> None:
    """An agent not in _AGENT_META gets a minimal default description/tools."""
    loader = MagicMock()
    loader.load.return_value = "body"

    target = tmp_path / "unknown_agent.md"
    _write_agent_file("unknown_agent", loader, target, tmp_path)

    content = target.read_text(encoding="utf-8")
    assert "unknown_agent agent." in content
    assert "Read" in content
