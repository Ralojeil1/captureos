"""Tests for CaptureOS state — capture mode persistence."""
import os
import tempfile
from captureos.state import (
    is_capture_mode,
    set_capture_mode,
    toggle_capture_mode,
    get_state,
    clear_state,
)


class TestCaptureMode:
    def test_default_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            assert is_capture_mode(tmp) is False

    def test_set_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            set_capture_mode(True, tmp)
            assert is_capture_mode(tmp) is True

    def test_set_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            set_capture_mode(True, tmp)
            set_capture_mode(False, tmp)
            assert is_capture_mode(tmp) is False

    def test_toggle(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Start false
            assert toggle_capture_mode(tmp) is True
            assert is_capture_mode(tmp) is True
            # Toggle back
            assert toggle_capture_mode(tmp) is False
            assert is_capture_mode(tmp) is False

    def test_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            set_capture_mode(True, tmp, {"timezone": "Asia/Dubai", "vault": "~/Vault"})
            state = get_state(tmp)
            assert state["capture_mode"] is True
            assert state["metadata"]["timezone"] == "Asia/Dubai"
            assert state["metadata"]["vault"] == "~/Vault"

    def test_get_state_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = get_state(tmp)
            assert state["capture_mode"] is False
            assert state["metadata"] == {}

    def test_clear_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            set_capture_mode(True, tmp)
            assert is_capture_mode(tmp) is True
            clear_state(tmp)
            assert is_capture_mode(tmp) is False

    def test_state_file_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            set_capture_mode(True, tmp)
            state_file = os.path.join(tmp, "state.json")
            assert os.path.exists(state_file)

    def test_multiple_toggles(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(5):
                set_capture_mode(i % 2 == 0, tmp)
            # Should end on True (0=True, 1=False, 2=True, 3=False, 4=True)
            assert is_capture_mode(tmp) is True
