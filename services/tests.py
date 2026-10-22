from django.test import SimpleTestCase

from services.sanitize import sanitize_html


class SanitizeHtmlTest(SimpleTestCase):
    def test_keeps_basic_formatting(self):
        self.assertEqual(sanitize_html('<p>Hi <b>there</b></p>'), '<p>Hi <b>there</b></p>')

    def test_strips_script_and_its_content(self):
        out = sanitize_html('<p>ok</p><script>alert(1)</script>')
        self.assertEqual(out, '<p>ok</p>')

    def test_strips_event_handlers_and_unknown_tags(self):
        out = sanitize_html('<img src="/a.png" onerror="alert(1)"><blink>x</blink>')
        self.assertNotIn('onerror', out)
        self.assertNotIn('blink', out)
        self.assertIn('src="/a.png"', out)

    def test_blocks_javascript_urls(self):
        out = sanitize_html('<a href="javascript:alert(1)">x</a><a href="https://e.com">y</a>')
        self.assertNotIn('javascript', out)
        self.assertIn('href="https://e.com"', out)
        self.assertIn('rel="noopener noreferrer"', out)

    def test_filters_dangerous_css(self):
        out = sanitize_html('<p style="color: red; background-image: url(x); position: fixed">x</p>')
        self.assertIn('color: red', out)
        self.assertNotIn('url(', out)
        self.assertNotIn('position', out)

    def test_escapes_text_and_closes_tags(self):
        self.assertEqual(sanitize_html('a < b <b>bold'), 'a &lt; b <b>bold</b>')

    def test_drops_iframes_and_svg(self):
        self.assertEqual(sanitize_html('<iframe src="x"></iframe><svg onload=alert(1)></svg>z'), 'z')

    def test_empty_input(self):
        self.assertEqual(sanitize_html(None), '')
        self.assertEqual(sanitize_html(''), '')
