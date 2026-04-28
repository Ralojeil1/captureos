"""Tests for CaptureOS writer — markdown inbox file I/O."""
import os
import tempfile
from pathlib import Path
from captureos.writer import (
    write_to_inbox,
    write_batch_to_inbox,
    read_inbox,
    format_capture_line,
    ensure_inbox_dir,
)
from captureos.classifier import Basket, CaptureItem


def make_item(basket=Basket.TASK_REMINDER, title="Test item", **kwargs):
    """Helper to create a CaptureItem quickly."""
    defaults = {"basket": basket, "title": title, "confidence": 1.0, "reasoning": "test"}
    defaults.update(kwargs)
    return CaptureItem(**defaults)


class TestFormatCaptureLine:
    def test_basic(self):
        item = make_item(title="Follow up with Sarah")
        line = format_capture_line(item)
        assert line.startswith("- [ ]")
        assert "Follow up with Sarah" in line

    def test_with_date(self):
        item = make_item(title="Dentist", date="2026-04-29")
        line = format_capture_line(item)
        assert "2026-04-29" in line
        assert "all-day" in line

    def test_with_date_and_time(self):
        item = make_item(title="Meeting", date="2026-04-29", time="15:00", duration_minutes=60)
        line = format_capture_line(item)
        assert "2026-04-29" in line
        assert "15:00" in line
        assert "60min" in line


class TestWriteToInbox:
    def test_write_new_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            filepath = os.path.join(tmp, "test-inbox.md")
            item = make_item(title="Test task")
            written = write_to_inbox(item, filepath)
            assert os.path.exists(written)
            assert os.path.basename(written) == "test-inbox.md"

    def test_write_creates_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            filepath = os.path.join(tmp, "wiki", "inbox.md")
            item = make_item(title="Test task")
            write_to_inbox(item, filepath)
            assert os.path.exists(filepath)

    def test_append_to_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            filepath = os.path.join(tmp, "inbox.md")
            item1 = make_item(title="Task 1")
            item2 = make_item(title="Task 2")
            write_to_inbox(item1, filepath)
            write_to_inbox(item2, filepath)

            items = read_inbox(filepath)
            assert len(items) >= 2
            assert any("Task 1" in i for i in items)
            assert any("Task 2" in i for i in items)

    def test_all_three_baskets(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_item = make_item(Basket.TASK_REMINDER, "Task")
            event_item = make_item(Basket.EVENT_MEETING, "Event")
            idea_item = make_item(Basket.IDEA_NOTE, "Idea")

            write_to_inbox(task_item, os.path.join(tmp, "tasks.md"))
            write_to_inbox(event_item, os.path.join(tmp, "events.md"))
            write_to_inbox(idea_item, os.path.join(tmp, "ideas.md"))

            assert os.path.exists(os.path.join(tmp, "tasks.md"))
            assert os.path.exists(os.path.join(tmp, "events.md"))
            assert os.path.exists(os.path.join(tmp, "ideas.md"))

    def test_no_create_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            filepath = os.path.join(tmp, "nonexistent.md")
            item = make_item()
            with __import__('pytest').raises(FileNotFoundError):
                write_to_inbox(item, filepath, create_if_missing=False)


class TestWriteBatchToInbox:
    def test_batch_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            filepath = os.path.join(tmp, "batch-inbox.md")
            items = [
                make_item(title="Task 1"),
                make_item(title="Task 2"),
                make_item(title="Task 3"),
            ]
            write_batch_to_inbox(items, filepath)

            result = read_inbox(filepath)
            assert len(result) >= 3

    def test_empty_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            filepath = os.path.join(tmp, "empty-inbox.md")
            write_batch_to_inbox([], filepath)
            assert os.path.exists(filepath)


class TestReadInbox:
    def test_read_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            filepath = os.path.join(tmp, "empty.md")
            result = read_inbox(filepath)
            assert result == []

    def test_read_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            filepath = os.path.join(tmp, "inbox.md")
            item = make_item(title="Test task")
            write_to_inbox(item, filepath)

            result = read_inbox(filepath)
            assert len(result) >= 1
            assert any("Test task" in r for r in result)


class TestEnsureInboxDir:
    def test_creates_nested_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            deep_path = os.path.join(tmp, "a", "b", "c", "inbox.md")
            ensure_inbox_dir(deep_path)
            parent = os.path.dirname(deep_path)
            assert os.path.isdir(parent)
