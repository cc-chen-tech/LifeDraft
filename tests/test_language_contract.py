"""Language detection contract tests.

No mocks. Pure logic tests for detect_language_from_state.
"""

from src.utils.language import detect_language_from_state


class TestLanguageContract:
    """Contract tests for language detection."""

    def test_empty_state_defaults_zh(self):
        """Empty state should default to zh."""
        assert detect_language_from_state({}) == "zh"

    def test_no_character_settings_defaults_zh(self):
        """State without character_settings should default to zh."""
        assert detect_language_from_state({"week": 5}) == "zh"

    def test_chinese_era_description_returns_zh(self):
        """Chinese era_description should return zh."""
        state = {"character_settings": {"era": {"era_description": "唐朝盛世"}}}
        assert detect_language_from_state(state) == "zh"

    def test_english_era_description_returns_en(self):
        """English era_description should return en."""
        state = {"character_settings": {"era": {"era_description": "Medieval Europe"}}}
        assert detect_language_from_state(state) == "en"

    def test_mixed_english_chinese_returns_zh(self):
        """Mixed content should return zh (non-ASCII detected)."""
        state = {"character_settings": {"era": {"era_description": "Modern 现代"}}}
        assert detect_language_from_state(state) == "zh"

    def test_era_is_string_not_dict_returns_zh(self):
        """Non-dict era should return zh (default)."""
        state = {"character_settings": {"era": "modern"}}
        assert detect_language_from_state(state) == "zh"

    def test_empty_era_description_returns_zh(self):
        """Empty era_description should return zh."""
        state = {"character_settings": {"era": {"era_description": ""}}}
        assert detect_language_from_state(state) == "zh"

    def test_punctuation_in_english_still_ascii(self):
        """English with punctuation should still be detected as en."""
        state = {
            "character_settings": {"era": {"era_description": "Victorian-era London!"}}
        }
        assert detect_language_from_state(state) == "en"
