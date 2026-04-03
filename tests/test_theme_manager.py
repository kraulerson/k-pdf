"""Tests for ThemeManager and ThemeMode."""

from __future__ import annotations

from pathlib import Path

from k_pdf.core.theme_manager import ThemeManager, ThemeMode


class TestThemeMode:
    def test_off_value(self) -> None:
        assert ThemeMode.OFF.value == "off"

    def test_dark_original_value(self) -> None:
        assert ThemeMode.DARK_ORIGINAL.value == "dark_original"

    def test_dark_inverted_value(self) -> None:
        assert ThemeMode.DARK_INVERTED.value == "dark_inverted"

    def test_all_members(self) -> None:
        assert set(ThemeMode) == {
            ThemeMode.OFF,
            ThemeMode.DARK_ORIGINAL,
            ThemeMode.DARK_INVERTED,
        }


class TestThemeManager:
    def test_initial_mode_is_off(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        assert mgr.mode is ThemeMode.OFF

    def test_set_mode_dark_original(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        assert mgr.mode is ThemeMode.DARK_ORIGINAL

    def test_set_mode_dark_inverted(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_INVERTED)
        assert mgr.mode is ThemeMode.DARK_INVERTED

    def test_is_dark_false_when_off(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        assert mgr.is_dark is False

    def test_is_dark_true_when_dark_original(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        assert mgr.is_dark is True

    def test_is_dark_true_when_dark_inverted(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_INVERTED)
        assert mgr.is_dark is True

    def test_is_inverted_false_when_off(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        assert mgr.is_inverted is False

    def test_is_inverted_false_when_dark_original(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        assert mgr.is_inverted is False

    def test_is_inverted_true_when_dark_inverted(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_INVERTED)
        assert mgr.is_inverted is True

    def test_toggle_from_off_goes_dark_original_default(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        mgr.toggle()
        assert mgr.mode is ThemeMode.DARK_ORIGINAL

    def test_toggle_from_dark_original_goes_off(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        mgr.toggle()
        assert mgr.mode is ThemeMode.OFF

    def test_toggle_from_dark_inverted_goes_off(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_INVERTED)
        mgr.toggle()
        assert mgr.mode is ThemeMode.OFF

    def test_toggle_remembers_last_dark_mode_inverted(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_INVERTED)
        mgr.toggle()  # -> OFF
        mgr.toggle()  # -> should go back to DARK_INVERTED
        assert mgr.mode is ThemeMode.DARK_INVERTED

    def test_toggle_remembers_last_dark_mode_original(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        mgr.toggle()  # -> OFF
        mgr.toggle()  # -> should go back to DARK_ORIGINAL
        assert mgr.mode is ThemeMode.DARK_ORIGINAL

    def test_theme_changed_signal_emitted(self, qapp, qtbot) -> None:
        mgr = ThemeManager(qapp)
        with qtbot.waitSignal(mgr.theme_changed, timeout=1000):
            mgr.set_mode(ThemeMode.DARK_ORIGINAL)

    def test_theme_changed_signal_value(self, qapp, qtbot) -> None:
        mgr = ThemeManager(qapp)
        signals = []
        mgr.theme_changed.connect(signals.append)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        assert len(signals) == 1
        assert signals[0] == ThemeMode.DARK_ORIGINAL.value

    def test_inversion_changed_signal_emitted(self, qapp, qtbot) -> None:
        mgr = ThemeManager(qapp)
        with qtbot.waitSignal(mgr.inversion_changed, timeout=1000):
            mgr.set_mode(ThemeMode.DARK_INVERTED)

    def test_inversion_changed_signal_true(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        signals: list[bool] = []
        mgr.inversion_changed.connect(signals.append)
        mgr.set_mode(ThemeMode.DARK_INVERTED)
        assert signals == [True]

    def test_inversion_changed_signal_false(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_INVERTED)
        signals: list[bool] = []
        mgr.inversion_changed.connect(signals.append)
        mgr.set_mode(ThemeMode.OFF)
        assert signals == [False]

    def test_no_signal_when_same_mode(self, qapp, qtbot) -> None:
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        with qtbot.assertNotEmitted(mgr.theme_changed):
            mgr.set_mode(ThemeMode.DARK_ORIGINAL)

    def test_no_inversion_signal_when_inversion_unchanged(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        signals: list[bool] = []
        mgr.inversion_changed.connect(signals.append)
        mgr.set_mode(ThemeMode.OFF)  # both have inversion=False
        assert signals == []

    def test_set_mode_off_restores_light(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        mgr.set_mode(ThemeMode.OFF)
        assert mgr.mode is ThemeMode.OFF
        assert mgr.is_dark is False
        assert mgr.is_inverted is False


class TestQssLoading:
    def test_light_qss_exists_and_nonempty(self) -> None:
        path = Path(__file__).parent.parent / "k_pdf" / "resources" / "themes" / "light.qss"
        assert path.exists()
        assert path.stat().st_size > 100

    def test_dark_qss_exists_and_nonempty(self) -> None:
        path = Path(__file__).parent.parent / "k_pdf" / "resources" / "themes" / "dark.qss"
        assert path.exists()
        assert path.stat().st_size > 100

    def test_dark_theme_applies_stylesheet(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        assert qapp.styleSheet() != ""

    def test_light_theme_on_off(self, qapp) -> None:
        mgr = ThemeManager(qapp)
        mgr.set_mode(ThemeMode.DARK_ORIGINAL)
        mgr.set_mode(ThemeMode.OFF)
        # Light theme stylesheet is applied (may be empty string for default)
        assert mgr.mode is ThemeMode.OFF
