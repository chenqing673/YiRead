"""Original figures and tables stay complete and local in continuous reading."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from storage import reading_media,pdf_view,paper_reader
from storage.pdf_parser import parse_pdf


class ReadingMedia(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        mapping=lambda name:str(self.root/name)
        self.patches=[patch.object(m,'get_data_path',side_effect=mapping) for m in (reading_media,pdf_view,paper_reader)]
        for p in self.patches:p.start()
        self.folder=self.root/'library'/'media';self.folder.mkdir(parents=True)
        self.pdf=self.folder/'source.pdf';self.paper=self.folder/'paper.json'
        with pymupdf.open() as doc:
            page=doc.new_page(width=600,height=800)
            page.insert_text((40,90),'Table 1. Reaction conditions and measured yields.',fontsize=10)
            # Three-rule tables can use filled thin rectangles rather than lines.
            for y in [110,130,230]:page.draw_rect(pymupdf.Rect(40,y,300,y+.5),color=None,fill=(0,0,0))
            page.insert_text((50,125),'Entry     Solvent     Yield',fontsize=10)
            page.insert_textbox(pymupdf.Rect(50,140,290,220),'1  Methanol  75%\n2  Ethanol  80%\n3  Water  60%',fontsize=10)
            page.insert_text((40,245),'a Values are isolated yields.',fontsize=9)
            page.insert_textbox(pymupdf.Rect(330,110,560,250),'Researchers investigated the reaction conditions and measured synthetic yields. The reaction was stirred for three hours. Additional experiments confirmed these results.',fontsize=11)
            pix=pymupdf.Pixmap(pymupdf.csRGB,pymupdf.IRect(0,0,60,60),False);pix.clear_with(80)
            page.insert_image(pymupdf.Rect(100,320,300,460),pixmap=pix)
            page.insert_text((80,490),'Fig. 1. Original experimental graph.',fontsize=10)
            # Disconnected panels must remain one complete original figure.
            for x in [45,350]:
                page.draw_polyline([(x,570),(x+30,540),(x+60,570),(x+60,600),(x+30,630),(x,600),(x,570)])
                page.insert_text((x+22,537),'N',fontsize=10)
                page.insert_text((x+59,582),'O',fontsize=10)
            page.insert_text((270,655),'Scheme-II',fontsize=10)
            doc.save(self.pdf)
        self.parsed=parse_pdf(self.pdf);self.paper.write_text(json.dumps(self.parsed),encoding='utf8')
        reading_media._manifest.cache_clear();reading_media.render_reading_media.cache_clear()
    def tearDown(self):
        reading_media._manifest.cache_clear();reading_media.render_reading_media.cache_clear()
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def test_complete_three_rule_table_keeps_title_cells_and_footnote_without_neighbor_prose(self):
        assets=reading_media.get_reading_media('media')['pages'][0]['assets']
        table=next(a for a in assets if a['kind']=='table')
        self.assertLess(table['box'][1],90/800);self.assertGreater(table['box'][3],245/800)
        covered=[b['text'] for b in self.parsed['pages'][0]['blocks'] if b['id'] in table['covered']]
        self.assertTrue(any('Methanol' in t for t in covered));self.assertFalse(any('Researchers' in t for t in covered))
        self.assertGreater(len(table['covered']),1)
    def test_raster_and_disconnected_vector_panels_are_original_crops(self):
        assets=reading_media.get_reading_media('media')['pages'][0]['assets']
        figures=[a for a in assets if a['kind']=='figure']
        self.assertEqual(len(figures),2)
        vector=next(a for a in figures if a['box'][1]>.5)
        self.assertLess(vector['box'][0],45/600);self.assertGreater(vector['box'][2],410/600)
        self.assertIsNotNone(vector['anchor'])
    def test_media_is_read_only_versioned_png_with_no_model_call(self):
        before=(self.pdf.read_bytes(),self.paper.read_bytes())
        with patch('core.translator.complete',side_effect=AssertionError('paid call')):
            manifest=reading_media.get_reading_media('media');a=manifest['pages'][0]['assets'][0]
            png=reading_media.render_reading_media('media',1,a['id'],manifest['version'])
        self.assertTrue(png.startswith(b'\x89PNG'));self.assertEqual(before,(self.pdf.read_bytes(),self.paper.read_bytes()))
        with self.assertRaises(ValueError):reading_media.render_reading_media('media',1,a['id'],'old-version')
    def test_plain_prose_and_page_rules_do_not_become_figures(self):
        with pymupdf.open() as doc:
            page=doc.new_page();page.insert_textbox(pymupdf.Rect(40,100,500,300),'Ordinary scientific prose with no original figure or table.',fontsize=11)
            page.draw_line((40,80),(550,80));doc.save(self.pdf)
        self.paper.write_text(json.dumps(parse_pdf(self.pdf)))
        self.assertEqual(reading_media.get_reading_media('media')['pages'][0]['assets'],[])


if __name__=='__main__':unittest.main()
