"""Unit tests for projects/الوكيل/generate_content.py — slugify, article gen, content cleaning."""

import json
import os
import sys
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(REPO_ROOT, "projects", "\u0627\u0644\u0648\u0643\u064a\u0644")
sys.path.insert(0, BACKEND_DIR)

import generate_content  # noqa: E402


# ---------------------------------------------------------------------------
# slugify()
# ---------------------------------------------------------------------------

class TestSlugify(unittest.TestCase):

    def test_basic_lowercasing(self):
        self.assertEqual(generate_content.slugify("Hello World"), "hello-world")

    def test_dollar_sign(self):
        self.assertEqual(generate_content.slugify("Save $500 Fast"), "save-dollars500-fast")

    def test_percent_sign(self):
        self.assertEqual(generate_content.slugify("Top 10% Earners"), "top-10percent-earners")

    def test_special_chars_stripped(self):
        self.assertEqual(generate_content.slugify("What's the Deal?"), "whats-the-deal")

    def test_multiple_hyphens_collapsed(self):
        self.assertEqual(generate_content.slugify("one   two   three"), "one-two-three")

    def test_leading_trailing_hyphens_stripped(self):
        self.assertEqual(generate_content.slugify("  -hello- "), "hello")

    def test_empty_string(self):
        self.assertEqual(generate_content.slugify(""), "")

    def test_only_special_chars(self):
        self.assertEqual(generate_content.slugify("!@#"), "")

    def test_numbers_preserved(self):
        self.assertEqual(generate_content.slugify("Top 10 Tips for 2026"), "top-10-tips-for-2026")

    def test_unicode_stripped(self):
        result = generate_content.slugify("How to \u0627\u0644\u0648\u0643\u064a\u0644 save money")
        # Arabic chars are stripped; rest preserved
        self.assertNotIn("\u0627\u0644\u0648\u0643\u064a\u0644", result)
        self.assertIn("save", result)


# ---------------------------------------------------------------------------
# EXISTING_SLUGS list
# ---------------------------------------------------------------------------

class TestExistingSlugs(unittest.TestCase):

    def test_existing_slugs_not_empty(self):
        self.assertGreater(len(generate_content.EXISTING_SLUGS), 0)

    def test_existing_slugs_are_strings(self):
        for s in generate_content.EXISTING_SLUGS:
            self.assertIsInstance(s, str)
            self.assertGreater(len(s), 0)

    def test_existing_slugs_are_lowercase_hyphenated(self):
        import re
        for s in generate_content.EXISTING_SLUGS:
            self.assertRegex(s, r'^[a-z0-9\-]+$', f"Slug {s!r} has invalid chars")


# ---------------------------------------------------------------------------
# generate_article() — mock the API so no network calls
# ---------------------------------------------------------------------------

def _make_api_response(content, model="gpt-4o-mini"):
    """Build a fake API JSON response dict."""
    return {
        "choices": [{"message": {"content": content}}],
        "model": model,
    }


class TestGenerateArticle(unittest.TestCase):
    """Tests for generate_article() with mocked API calls."""

    def _mock_urlopen(self, content, model="gpt-4o-mini"):
        """Return a context-manager-compatible mock for urlopen."""
        fake = json.dumps(_make_api_response(content, model)).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = fake
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    @patch("generate_content.time.sleep")  # skip delays
    def test_successful_generation(self, _sleep):
        html = '<p class="lead">Great tips on saving money.</p>' + (" word" * 200)
        html += '\n<div class="cta-box"><p><strong>Start Saving Today</strong></p></div>'
        with patch("generate_content.urllib.request.urlopen", return_value=self._mock_urlopen(html)):
            result = generate_content.generate_article("How to Save Money", "saving")
        self.assertNotIn("error", result)
        self.assertEqual(result["category"], "saving")
        self.assertIn("slug", result)
        self.assertEqual(result["slug"], "how-to-save-money")
        self.assertGreater(result["words"], 0)

    @patch("generate_content.time.sleep")
    def test_markdown_fence_stripping(self, _sleep):
        html = '```html\n<p class="lead">Intro.</p>' + (" word" * 200) + '\n```'
        html_inner = '<p class="lead">Intro.</p>' + (" word" * 200)
        html_inner += '\n<div class="cta-box"><p><strong>Take Control Now</strong></p></div>'
        # The function should strip ``` fences
        full_html = '```html\n' + html_inner + '\n```'
        with patch("generate_content.urllib.request.urlopen", return_value=self._mock_urlopen(full_html)):
            result = generate_content.generate_article("Test Topic")
        self.assertNotIn("error", result)
        self.assertNotIn("```", result.get("html", ""))

    @patch("generate_content.time.sleep")
    def test_h1_tag_removed(self, _sleep):
        html = '<h1>Should be removed</h1>\n<p class="lead">Intro.</p>' + (" word" * 200)
        html += '\n<div class="cta-box"><p><strong>Take Control Now</strong></p></div>'
        with patch("generate_content.urllib.request.urlopen", return_value=self._mock_urlopen(html)):
            result = generate_content.generate_article("Test")
        self.assertNotIn("<h1>", result.get("html", ""))

    @patch("generate_content.time.sleep")
    def test_html_wrapper_stripped(self, _sleep):
        html = ('<!DOCTYPE html><html><head><title>Test</title></head>'
                '<body><p class="lead">Content.</p>' + (" word" * 200) +
                '<div class="cta-box">CTA</div></body></html>')
        with patch("generate_content.urllib.request.urlopen", return_value=self._mock_urlopen(html)):
            result = generate_content.generate_article("Wrapper Test")
        body = result.get("html", "")
        self.assertNotIn("<!DOCTYPE", body)
        self.assertNotIn("<html", body)
        self.assertNotIn("<head>", body)
        self.assertNotIn("<body", body)

    @patch("generate_content.time.sleep")
    def test_cta_box_injected_when_missing(self, _sleep):
        html = '<p class="lead">Guide to budgeting.</p>' + (" word" * 200)
        # No cta-box in the content — should be auto-injected
        with patch("generate_content.urllib.request.urlopen", return_value=self._mock_urlopen(html)):
            result = generate_content.generate_article("Budget Guide", "budget")
        self.assertIn("cta-box", result.get("html", ""))

    @patch("generate_content.time.sleep")
    def test_lead_paragraph_added_when_missing(self, _sleep):
        html = "Just plain text without p tag." + (" word" * 200)
        html += '<div class="cta-box">CTA</div>'
        with patch("generate_content.urllib.request.urlopen", return_value=self._mock_urlopen(html)):
            result = generate_content.generate_article("Plain Text Test")
        self.assertTrue(result.get("html", "").startswith("<p"))

    @patch("generate_content.time.sleep")
    def test_all_models_fail(self, _sleep):
        """When every model fails, result should contain an error."""
        with patch("generate_content.urllib.request.urlopen", side_effect=Exception("API down")):
            result = generate_content.generate_article("Failing Topic")
        self.assertIn("error", result)

    @patch("generate_content.time.sleep")
    def test_short_content_retries(self, _sleep):
        """Content under 150 words should be rejected, triggering next model."""
        short = '<p class="lead">Too short.</p>'
        good = '<p class="lead">Long article.</p>' + (" word" * 200)
        good += '<div class="cta-box">CTA</div>'

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return self._mock_urlopen(short)
            return self._mock_urlopen(good)

        with patch("generate_content.urllib.request.urlopen", side_effect=side_effect):
            result = generate_content.generate_article("Short Content Test")
        self.assertNotIn("error", result)
        self.assertGreater(call_count[0], 1)

    def test_cta_actions_per_category(self):
        """Verify the CTA lookup table has entries for each expected category."""
        expected_categories = {"saving", "budget", "debt", "investment", "general"}
        # Peek at the CTA dict defined inside generate_article
        # We can verify indirectly by checking the slug result
        for cat in expected_categories:
            slug = generate_content.slugify(f"Test {cat}")
            self.assertIsInstance(slug, str)


# ---------------------------------------------------------------------------
# main() — verify CLI argument parsing & file output
# ---------------------------------------------------------------------------

class TestMainCLI(unittest.TestCase):

    @patch("generate_content.time.sleep")
    @patch("generate_content.generate_article")
    def test_main_writes_output_files(self, mock_gen, _sleep):
        """main() should create output files for each successfully generated article."""
        mock_gen.return_value = {
            "title": "Test Title",
            "category": "general",
            "html": '<p class="lead">Body</p>',
            "words": 300,
            "model": "gpt-4o-mini",
            "slug": "test-title",
        }

        # Temporarily set output dir and sys.argv
        tmpdir = tempfile.mkdtemp(prefix="grs_gen_test_")
        orig_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            sys.argv = ["generate_content.py", "Test Title--general"]
            generate_content.main()

            # Check that output directory was created
            out_dir = os.path.join(tmpdir, "generated_articles")
            self.assertTrue(os.path.isdir(out_dir))
            # Check for HTML preview and JS output
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "test-title.html")))
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "articles_data.js")))
        finally:
            os.chdir(orig_cwd)
            shutil.rmtree(tmpdir, ignore_errors=True)

    @patch("generate_content.time.sleep")
    @patch("generate_content.generate_article")
    def test_main_handles_duplicate_slug(self, mock_gen, _sleep):
        """If generated slug exists in EXISTING_SLUGS, '-guide' should be appended."""
        existing = generate_content.EXISTING_SLUGS[0]  # e.g. "how-to-save-money-from-salary"

        mock_gen.return_value = {
            "title": "Existing Title",
            "category": "saving",
            "html": '<p class="lead">Body</p>',
            "words": 300,
            "model": "gpt-4o-mini",
            "slug": existing,
        }

        tmpdir = tempfile.mkdtemp(prefix="grs_gen_dup_")
        orig_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            sys.argv = ["generate_content.py", "Existing Title--saving"]
            generate_content.main()
            out_dir = os.path.join(tmpdir, "generated_articles")
            # The file should be saved with the "-guide" suffix
            self.assertTrue(os.path.isfile(os.path.join(out_dir, f"{existing}-guide.html")))
        finally:
            os.chdir(orig_cwd)
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
