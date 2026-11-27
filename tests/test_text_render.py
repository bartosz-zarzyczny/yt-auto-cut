import unittest

from additional_texts import FONT_PATH
from system_settings import BUNDLED_FONT, choose_font
from text_render import load_font, render_text, text_clip, wrap_text


class TextRenderTests(unittest.TestCase):
    def test_image_is_rgba_with_transparent_background_and_visible_text(self):
        image = render_text("STAGE 1 | Czas: 12.3s", choose_font(), 55, "white", "black", 2.5)
        self.assertEqual(image.ndim, 3)
        self.assertEqual(image.shape[2], 4)
        alpha = image[:, :, 3]
        self.assertEqual(alpha[0, 0], 0)          # róg przezroczysty
        self.assertGreater((alpha == 255).sum(), 100)  # tekst widoczny

    def test_multiline_text_is_taller(self):
        one = render_text("Czas: 12.3s", BUNDLED_FONT, 55)
        two = render_text("STAGE 1\nCzas: 12.3s", BUNDLED_FONT, 55)
        self.assertGreater(two.shape[0], one.shape[0] * 1.6)

    def test_caption_wraps_to_max_width(self):
        text = "Pierwszy tor - szybkie wejście i zmiana magazynka w biegu"
        font = load_font(FONT_PATH, 60)
        self.assertIn("\n", wrap_text(text, font, 960, 2))
        image = render_text(text, FONT_PATH, 60, "#00F0FF", "#1A0536", 2, max_width=960)
        self.assertEqual(image.shape[1], 960)

    def test_polish_characters_render(self):
        image = render_text("ąćęłńóśźż ĄĆĘŁŃÓŚŹŻ", FONT_PATH, 60)
        self.assertGreater((image[:, :, 3] > 0).sum(), 100)

    def test_clip_has_mask_and_duration(self):
        clip = text_clip("Tor 3", 4.0, font_path=BUNDLED_FONT, font_size=40, color="white")
        self.assertEqual(clip.duration, 4.0)
        self.assertIsNotNone(clip.mask)


if __name__ == "__main__":
    unittest.main()
