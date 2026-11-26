import unittest

from test_rag import load_module


class ReusableUtilsTests(unittest.TestCase):


    def test_url_cleaner_accepts_other_sites_without_partner_configuration(self):
        urls = load_module('url_utils_under_test', 'Utils/url_utils.py', {})
        self.assertEqual(urls.clean_url('https://EXAMPLE.COM/#intro'), 'https://example.com/')
        self.assertEqual(urls.clean_url('https://example.com/#intro', keep_fragment=True),
                         'https://example.com/#intro')

    def test_domain_filter_is_supplied_by_caller(self):
        urls = load_module('url_utils_under_test', 'Utils/url_utils.py', {})
        self.assertEqual(urls.clean_url('https://docs.example.com/', allowed_domains=['example.com']),
                         'https://docs.example.com/')
        for url in ['https://example.com.evil.com/', 'file:///secret', 'https://user:pass@example.com/']:
            with self.assertRaises(ValueError):
                urls.clean_url(url, allowed_domains=['example.com'])

    def test_html_cleaner_is_independent_of_services(self):
        html = load_module('html_utils_under_test', 'Utils/html_utils.py', {})
        self.assertEqual(html.html_text('<style>hidden</style><h1>Curso</h1><p>A &amp; B</p><script>secret</script>'),
                         'Curso A & B')

    def test_keyword_filters_are_supplied_by_caller(self):
        text = load_module('text_utils_under_test', 'Utils/text_utils.py', {})
        self.assertEqual(text.keyword_terms('Curso de SI PUC', stopwords={'de'}), ['curso', 'si', 'puc'])


if __name__ == '__main__':
    unittest.main()
