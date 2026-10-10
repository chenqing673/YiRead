"""Layout previews preserve source graphics/data and never call a provider."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
from storage import translation_layout, paper_reader, pdf_view, translation_store
from storage.pdf_parser import parse_pdf


class TranslationLayout(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        mapping=lambda name: str(self.root/name)
        self.patches=[patch.object(module,'get_data_path',side_effect=mapping) for module in (translation_layout,paper_reader,pdf_view,translation_store)]
        for p in self.patches:p.start()
        folder=self.root/'library'/'fixture';folder.mkdir(parents=True);self.source=folder/'source.pdf'
        with pymupdf.open() as document:
            page=document.new_page(width=600,height=800)
            for x,prefix in [(40,'Left'),(310,'Right')]:
                result=page.insert_textbox(pymupdf.Rect(x,120,x+250,230),prefix+' researchers investigated the chemical conditions and reported the synthetic yields. The reaction was stirred for three hours in a suitable solvent.',fontsize=11)
                self.assertGreaterEqual(result,0)
            page.insert_text((40,290),'Equation: a = b = c = d',fontsize=11)
            page.draw_line((40,310),(560,310))
            pix=pymupdf.Pixmap(pymupdf.csRGB,pymupdf.IRect(0,0,40,40),False);pix.clear_with(80)
            page.insert_image(pymupdf.Rect(100,340,200,420),pixmap=pix)
            page.insert_text((40,450),'Fig. 1. Synthetic conditions and resulting structures.',fontsize=10)
            for y in [500,530,560]:page.draw_line((40,y),(560,y))
            for x in [40,300,560]:page.draw_line((x,500),(x,560))
            page.insert_text((50,520),'Entry',fontsize=10);page.insert_text((310,520),'Yield',fontsize=10)
            page.insert_text((50,550),'1',fontsize=10);page.insert_text((310,550),'75%',fontsize=10)
            document.save(self.source)
        self.paper=folder/'paper.json';self.paper.write_text(json.dumps(parse_pdf(self.source)),encoding='utf8')
        self.translated=self.root/'translation'/'fixture.json';self.translated.parent.mkdir()
        blocks=[{'id':b['id'],'translation':'研究人员考察反应条件，并报告合成收率。反应在适当溶剂中搅拌三小时。'} for b in parse_pdf(self.source)['pages'][0]['blocks']]
        self.translated.write_text(json.dumps({'engine':'openai-compatible','blocks':blocks}),encoding='utf8')
        translation_layout._layout.cache_clear();translation_layout._render_background.cache_clear()

    def tearDown(self):
        translation_layout._layout.cache_clear();translation_layout._render_background.cache_clear()
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def test_background_removes_only_translated_prose_preserving_formula_table_and_graphics(self):
        plan=translation_layout.get_translation_layout('fixture',1)
        self.assertGreaterEqual(sum(b['placement']=='replace' for b in plan['blocks']),3)
        with pdf_view.PDF_LOCK,translation_layout.background_document('fixture',plan) as document:
            page=document[0];text=page.get_text()
            self.assertNotIn('researchers investigated',text)
            self.assertIn('Equation: a = b = c = d',text)
            self.assertIn('75%',text);self.assertIn('Yield',text)
            self.assertEqual(len(page.get_images()),1)
            self.assertGreaterEqual(len(page.get_drawings()),7)

    def test_read_only_preview_does_not_change_sources_translations_or_call_model(self):
        before={p:p.read_bytes() for p in (self.source,self.paper,self.translated)}
        with patch('core.translator.complete',side_effect=AssertionError('preview called provider')):
            plan=translation_layout.get_translation_layout('fixture',1)
            image=translation_layout.render_translation_background('fixture',1,plan['version'])
            self.assertTrue(image.startswith(b'\x89PNG'))
        self.assertTrue(all(p.read_bytes()==value for p,value in before.items()))

    def test_three_rule_table_without_vertical_lines_keeps_cells_and_neighboring_prose(self):
        with pymupdf.open() as document:
            page=document.new_page(width=600,height=800)
            for y in [120,140,260]:page.draw_line((40,y),(290,y))
            page.insert_text((50,135),'Entry     Solvent     Yield',fontsize=10)
            page.insert_textbox(pymupdf.Rect(50,150,280,250),'1  Methanol  75%\n2  Ethanol  80%\n3  Acetonitrile  65%',fontsize=10)
            page.insert_textbox(pymupdf.Rect(320,120,560,250),'Researchers investigated the reaction conditions and reported the synthetic yields. The reaction was stirred for three hours.',fontsize=11)
            document.save(self.source)
        parsed=parse_pdf(self.source);self.paper.write_text(json.dumps(parsed))
        self.translated.write_text(json.dumps({'engine':'openai-compatible','blocks':[{'id':b['id'],'translation':'完整中文译文'} for b in parsed['pages'][0]['blocks']]}))
        plan=translation_layout.get_translation_layout('fixture',1)
        with pdf_view.PDF_LOCK,translation_layout.background_document('fixture',plan) as document:
            text=document[0].get_text()
            self.assertIn('Methanol',text);self.assertIn('75%',text)
            self.assertNotIn('Researchers investigated',text)

    def test_partial_translation_does_not_remove_untranslated_original_text(self):
        data=json.loads(self.translated.read_text());data['blocks']=data['blocks'][:1]
        self.translated.write_text(json.dumps(data))
        plan=translation_layout.get_translation_layout('fixture',1)
        with pdf_view.PDF_LOCK,translation_layout.background_document('fixture',plan) as document:
            self.assertIn('Right researchers',document[0].get_text())
        self.assertTrue(any(b['placement']=='untranslated' for b in plan['blocks']))

    def test_background_revision_must_match_layout_revision_after_edit(self):
        plan=translation_layout.get_translation_layout('fixture',1)
        data=json.loads(self.translated.read_text());data['blocks'][0]['translation']='人工修订后的完整译文'
        stamp=self.translated.stat().st_mtime_ns;self.translated.write_text(json.dumps(data));os.utime(self.translated,ns=(stamp+1000000,stamp+1000000))
        self.assertNotEqual(translation_layout.get_translation_layout('fixture',1)['version'],plan['version'])
        with self.assertRaises(ValueError):translation_layout.render_translation_background('fixture',1,plan['version'])

    def test_legacy_page_spanning_two_columns_is_preserved_with_full_translation(self):
        data=json.loads(self.paper.read_text());original=data['pages'][0]['blocks']
        data['pages'][0]['blocks']=[{'id':'legacy','text':'\n'.join(b['text'] for b in original),'rects':[r for b in original for r in b['rects']]}]
        self.paper.write_text(json.dumps(data));self.translated.write_text(json.dumps({'engine':'openai-compatible','blocks':[{'id':'legacy','translation':'完整旧译文'}]}))
        plan=translation_layout.get_translation_layout('fixture',1)
        self.assertEqual(plan['blocks'][0]['placement'],'preserve')
        with pdf_view.PDF_LOCK,translation_layout.background_document('fixture',plan) as document:self.assertIn('Left researchers',document[0].get_text())


if __name__=='__main__':unittest.main(verbosity=2)
