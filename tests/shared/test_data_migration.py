"""Tests for the one-time data-directory migration.

Real directories under tmp_path throughout; the only doubles are
hand-written stand-ins for `os.rename` and `shutil.copytree` injected to
force the cross-volume fallback and a corrupt copy, per the no-mock rule.
"""

import shutil

import pytest

from clear_budget.shared import data_migration
from clear_budget.shared.data_migration import migrate_legacy_data


def _seed(root):
    """A legacy tree shaped like real data: nested dirs and several files."""
    root.mkdir(parents=True)
    (root / "users.db").write_bytes(b"users")
    (root / "budget_jdoe.db").write_bytes(b"budget")
    (root / "ui_settings.json").write_text("{}", encoding="utf-8")
    (root / "logs").mkdir()
    (root / "logs" / "app.log").write_bytes(b"log line")
    (root / "arrows").mkdir()
    (root / "arrows" / "up.png").write_bytes(b"\x89PNG")
    return root


def _failing_rename(source, destination):
    raise OSError("cross-device link")


class TestNothingToDo:
    def test_no_legacy_directory_moves_nothing(self, tmp_path):
        target = tmp_path / "new"
        assert migrate_legacy_data(legacy=tmp_path / "old", target=target) is False
        assert not target.exists()

    def test_legacy_equal_to_target_is_left_alone(self, tmp_path):
        both = _seed(tmp_path / "data")
        assert migrate_legacy_data(legacy=both, target=both) is False
        assert (both / "users.db").exists()

    def test_a_populated_target_is_a_conflict_and_nothing_moves(self, tmp_path):
        legacy = _seed(tmp_path / "old")
        target = tmp_path / "new"
        target.mkdir()
        (target / "users.db").write_bytes(b"other users")
        assert migrate_legacy_data(legacy=legacy, target=target) is False
        assert (legacy / "users.db").read_bytes() == b"users"
        assert (target / "users.db").read_bytes() == b"other users"


class TestRenameFastPath:
    def test_the_whole_tree_moves_and_legacy_disappears(self, tmp_path):
        legacy = _seed(tmp_path / "old")
        target = tmp_path / "somewhere" / "new"
        assert migrate_legacy_data(legacy=legacy, target=target) is True
        assert not legacy.exists()
        assert (target / "users.db").read_bytes() == b"users"
        assert (target / "logs" / "app.log").read_bytes() == b"log line"

    def test_an_empty_target_left_by_a_crash_is_replaced(self, tmp_path):
        legacy = _seed(tmp_path / "old")
        target = tmp_path / "new"
        target.mkdir()
        assert migrate_legacy_data(legacy=legacy, target=target) is True
        assert (target / "users.db").exists()
        assert not legacy.exists()


class TestCopyFallback:
    def test_copy_verify_adopt_then_retire(self, tmp_path):
        legacy = _seed(tmp_path / "old")
        target = tmp_path / "new"

        def rename_failing_once(source, destination, _seen=[]):
            if not _seen:
                _seen.append(source)
                raise OSError("cross-device link")
            return shutil.move(str(source), str(destination))

        moved = migrate_legacy_data(
            legacy=legacy, target=target, rename=rename_failing_once
        )
        assert moved is True
        assert (target / "arrows" / "up.png").read_bytes() == b"\x89PNG"
        assert not legacy.exists()
        assert not legacy.with_name(legacy.name + ".migrated").exists()
        assert not target.with_name(target.name + ".migrating").exists()

    def test_an_empty_legacy_copies_cleanly(self, tmp_path):
        legacy = tmp_path / "old"
        legacy.mkdir()
        target = tmp_path / "new"

        def rename_failing_once(source, destination, _seen=[]):
            if not _seen:
                _seen.append(source)
                raise OSError("cross-device link")
            return shutil.move(str(source), str(destination))

        assert (
            migrate_legacy_data(
                legacy=legacy, target=target, rename=rename_failing_once
            )
            is True
        )
        assert target.is_dir()

    def test_a_rename_that_never_works_leaves_legacy_whole(self, tmp_path):
        legacy = _seed(tmp_path / "old")
        target = tmp_path / "new"
        moved = migrate_legacy_data(
            legacy=legacy, target=target, rename=_failing_rename
        )
        assert moved is False
        assert (legacy / "users.db").read_bytes() == b"users"
        assert not target.exists()
        assert not target.with_name(target.name + ".migrating").exists()

    def test_a_stray_file_in_the_target_blocks_adoption_safely(self, tmp_path):
        legacy = _seed(tmp_path / "old")
        target = tmp_path / "new"
        target.mkdir()
        (target / "stray.txt").write_bytes(b"stray")
        moved = migrate_legacy_data(legacy=legacy, target=target)
        assert moved is False
        assert (legacy / "users.db").exists()
        assert (target / "stray.txt").exists()

    def test_a_corrupt_copy_is_discarded_and_legacy_kept(self, tmp_path):
        legacy = _seed(tmp_path / "old")
        target = tmp_path / "new"

        def corrupting_copytree(source, destination):
            shutil.copytree(source, destination)
            (destination / "budget_jdoe.db").write_bytes(b"corrupt")

        moved = migrate_legacy_data(
            legacy=legacy,
            target=target,
            rename=_failing_rename,
            copy_tree=corrupting_copytree,
        )
        assert moved is False
        assert (legacy / "budget_jdoe.db").read_bytes() == b"budget"
        assert not target.exists()
        assert not target.with_name(target.name + ".migrating").exists()

    def test_a_copy_missing_a_file_is_discarded(self, tmp_path):
        legacy = _seed(tmp_path / "old")
        target = tmp_path / "new"

        def dropping_copytree(source, destination):
            shutil.copytree(source, destination)
            (destination / "ui_settings.json").unlink()

        moved = migrate_legacy_data(
            legacy=legacy,
            target=target,
            rename=_failing_rename,
            copy_tree=dropping_copytree,
        )
        assert moved is False
        assert (legacy / "ui_settings.json").exists()

    def test_a_failed_retirement_still_leaves_both_trees_whole(self, tmp_path):
        """The staging adoption works but legacy cannot be renamed aside.

        The target is fully adopted; the legacy directory survives intact, so
        the next launch sees a populated target (the conflict rule) and the
        resolution rule keeps preferring legacy. Nothing is lost either way.
        """
        legacy = _seed(tmp_path / "old")
        target = tmp_path / "new"

        def rename_adopting_only(source, destination, _seen=[]):
            if source == legacy and not _seen:
                _seen.append(source)
                raise OSError("cross-device link")
            if source == legacy:
                raise OSError("legacy is locked")
            return shutil.move(str(source), str(destination))

        moved = migrate_legacy_data(
            legacy=legacy, target=target, rename=rename_adopting_only
        )
        assert moved is False
        assert (legacy / "users.db").exists()
        assert (target / "users.db").exists()


class TestLeftoverSweep:
    def test_stale_staging_and_backup_are_removed(self, tmp_path):
        legacy = tmp_path / "old"
        target = tmp_path / "new"
        staging = target.with_name(target.name + ".migrating")
        backup = legacy.with_name(legacy.name + ".migrated")
        staging.mkdir(parents=True)
        (staging / "half.db").write_bytes(b"half")
        backup.mkdir(parents=True)
        (backup / "done.db").write_bytes(b"done")
        assert migrate_legacy_data(legacy=legacy, target=target) is False
        assert not staging.exists()
        assert not backup.exists()


@pytest.mark.parametrize("nested", [True, False])
def test_trees_match_is_symmetric_about_content(tmp_path, nested):
    source = tmp_path / "source"
    source.mkdir()
    if nested:
        (source / "inner").mkdir()
        (source / "inner" / "file.bin").write_bytes(b"payload")
    else:
        (source / "file.bin").write_bytes(b"payload")
    copy = tmp_path / "copy"
    shutil.copytree(source, copy)
    assert data_migration._trees_match(source, copy) is True
