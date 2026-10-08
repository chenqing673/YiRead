import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from core import translator


class FragmentTranslationTests(unittest.TestCase):
    def test_numbered_heading_does_not_call_provider(self):
        with patch.object(translator, 'complete') as complete:
            self.assertEqual(translator.translate('54 2.', {}, 'zh'), '54 2.')
            complete.assert_not_called()

    def test_single_word_response_must_be_translation(self):
        with patch.object(translator, 'complete', return_value='请提供完整的待翻译文本'):
            with self.assertRaises(translator.ProviderError):
                translator.translate('This', {}, 'zh')
        with patch.object(translator, 'complete', return_value='此'):
            self.assertEqual(translator.translate('This', {}, 'zh'), '此')

    def test_batch_keeps_good_items_and_retries_bad_item(self):
        response='{"translations":[{"id":"a","translation":"请提供需要翻译的正文"},{"id":"b","translation":"回流"}]}'
        with patch.object(translator, 'complete', return_value=response):
            self.assertEqual(translator.translate_batch([{'id':'a','text':'This'},{'id':'b','text':'Reflux'}], {}, 'zh'), {'b':'回流'})

    def test_actual_source_request_can_be_translated(self):
        self.assertEqual(translator.validate_translation('Please provide the text', '请提供文本'), '请提供文本')


if __name__ == '__main__':
    unittest.main()
