"""Paragraph geometry tests for preserved PDF appearance and existing translations."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
import json
from unittest.mock import patch
import pymupdf
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from storage.pdf_parser import parse_pdf
from storage.pdf_view import locate_legacy_blocks, normalized_rect, _page_png
from core.alignment import sentence_spans, source_segments
from storage.reading_alignment import paired_spans, _reading_units, translation_signature

class PdfGeometry(unittest.TestCase):
    def test_shared_page_word_geometry_preserves_positions_without_repeated_normalization(self):
        with pymupdf.open() as document:
            page=document.new_page();page.insert_text((50,80),'First paragraph about science.')
            blocks=[{'id':'first','text':'First paragraph about science.'}];within=[[0,0,1,1]]
            expected=locate_legacy_blocks(page,blocks,within=within)
            geometry=[(word,normalized_rect(word[:4],page)) for word in page.get_text('words',sort=False)]
            with patch('storage.pdf_view.normalized_rect',wraps=normalized_rect) as counter:
                self.assertEqual(locate_legacy_blocks(page,blocks,within=within,word_geometry=geometry),expected)
                self.assertEqual(counter.call_count,len(expected[0]['rects']))
    def test_disk_page_cache_survives_memory_eviction_and_invalidates_source_stamp(self):
        with tempfile.TemporaryDirectory() as folder:
            path=os.path.join(folder,'cache-source.pdf');self.make_pdf(path);cache=os.path.join(folder,'cache')
            with patch('storage.pdf_view.get_data_path',return_value=cache):
                stamp=os.stat(path).st_mtime_ns;first=_page_png(path,stamp,1);_page_png.cache_clear()
                with patch('storage.pdf_view.pymupdf.open',side_effect=AssertionError('unexpected render')):
                    self.assertEqual(_page_png(path,stamp,1),first)
                _page_png(path,stamp+1,1);self.assertEqual(len(list(Path(cache).glob('*.png'))),2)
    def test_sentence_boundaries_keep_decimals_abbreviations_and_chinese(self):
        text='As shown in Fig. 2, compound 1 gave 75.5% yield. It was stirred at 25 C for 3 h. Next step.'
        parts=[text[a:b] for a,b in sentence_spans(text)]
        self.assertEqual(len(parts),3);self.assertIn('Fig. 2',parts[0]);self.assertIn('75.5%',parts[0])
        self.assertEqual(len(source_segments(text)),3)
        self.assertEqual(len(sentence_spans('收率为75.5%。反应3小时。')),2)
        self.assertFalse(paired_spans('Yield 75%. Next 3 h.','收率70%。然后3小时。'))
        self.assertFalse(paired_spans('First. Second.','合并为一句。'))

    def test_sentence_geometry_stays_in_the_correct_column(self):
        with pymupdf.open() as doc:
            page=doc.new_page(width=600,height=400)
            page.insert_text((30,80),'Same sentence. Unique left.')
            page.insert_text((330,80),'Same sentence. Unique right.')
            parent=locate_legacy_blocks(page,[{'id':'right','text':'Same sentence. Unique right.'}])[0]['rects']
            units=locate_legacy_blocks(page,[{'id':'a','text':'Same sentence.'},{'id':'b','text':'Unique right.'}],within=parent)
            self.assertTrue(all(r[0]>.5 for u in units for r in u['rects']))
            self.assertLess(units[0]['rects'][0][2],units[1]['rects'][0][2])
            unmatched=locate_legacy_blocks(page,[{'id':'bad','text':'Unique left.'}],within=parent)
            self.assertEqual(unmatched[0]['rects'],[])

    def test_readonly_existing_sentence_alignment_preserves_saved_translation(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf=Path(folder,'source.pdf');paper=Path(folder,'paper.json');translation=Path(folder,'translation.json')
            source='Compound 1 gave 75% yield. Compound 2 gave 80% yield.'
            with pymupdf.open() as doc:
                page=doc.new_page();page.insert_textbox(pymupdf.Rect(40,80,550,300),source,fontsize=12);doc.save(pdf)
            parsed=parse_pdf(pdf);parsed['pages'][0]['blocks'][0]['id']='legacy'
            paper.write_text(json.dumps(parsed),encoding='utf8')
            saved={'blocks':[{'id':'legacy','translation':'化合物1收率75%。化合物2收率80%。'}]}
            translation.write_text(json.dumps(saved),encoding='utf8');before=translation.read_bytes()
            args=lambda:[value for path in (pdf,paper,translation) for value in (str(path),os.stat(path).st_mtime_ns)]
            mapping=_reading_units(*args());units=mapping['legacy'];self.assertEqual(len(units),2)
            self.assertEqual(_reading_units(*args(),translation_signature({'blocks':[]})),{})
            self.assertEqual(units[0]['kind'],'sentence-order');self.assertLess(units[0]['rects'][0][0],units[1]['rects'][0][0])
            self.assertEqual(translation.read_bytes(),before)
            saved['blocks'][0]['translation']='化合物1收率70%。化合物2收率80%。'
            translation.write_text(json.dumps(saved),encoding='utf8');_reading_units.cache_clear()
            self.assertEqual(_reading_units(*args()),{})
    def make_pdf(self, path, rotation=0, cropped=False):
        with pymupdf.open() as doc:
            page=doc.new_page(width=400,height=600)
            page.insert_text((70,100),'First paragraph about science.',fontsize=12)
            page.insert_text((70,220),'Second paragraph about reading.',fontsize=12)
            page.draw_rect(pymupdf.Rect(50,350,180,430),color=(1,0,0),fill=(.8,.8,1))
            if cropped:page.set_cropbox(pymupdf.Rect(30,30,350,550))
            page.set_rotation(rotation)
            doc.save(path)
    def test_new_import_has_separate_paragraph_geometry(self):
        with tempfile.TemporaryDirectory() as folder:
            path=os.path.join(folder,'source.pdf');self.make_pdf(path)
            result=parse_pdf(path)
            blocks=result['pages'][0]['blocks']
            self.assertEqual(len(blocks),2)
            self.assertEqual(blocks[0]['id'],'p1_b1')
            self.assertLess(blocks[0]['rects'][0][1],blocks[1]['rects'][0][1])
            for block in blocks:
                for rect in block['rects']:self.assertTrue(all(0<=value<=1 for value in rect))
    def test_old_ids_preserved_and_missing_text_not_falsely_highlighted(self):
        with tempfile.TemporaryDirectory() as folder:
            path=os.path.join(folder,'source.pdf');self.make_pdf(path)
            with pymupdf.open(path) as document:
                results=locate_legacy_blocks(document[0],[{'id':'old_a','text':'First paragraph about science.'},{'id':'old_b','text':'Second paragraph about reading.'},{'id':'unmatched','text':'This text does not exist anywhere.'}])
                self.assertEqual([b['id'] for b in results],['old_a','old_b','unmatched'])
                self.assertTrue(results[0]['rects']);self.assertTrue(results[1]['rects']);self.assertEqual(results[2]['rects'],[])
    def test_duplicate_paragraphs_match_distinct_locations(self):
        with pymupdf.open() as document:
            page=document.new_page();page.insert_text((50,80),'Repeated paragraph.');page.insert_text((50,180),'Repeated paragraph.')
            results=locate_legacy_blocks(page,[{'id':'first','text':'Repeated paragraph.'},{'id':'second','text':'Repeated paragraph.'}])
            self.assertLess(results[0]['rects'][0][1],results[1]['rects'][0][1])
    def test_rotation_crop_and_render_use_the_same_coordinates(self):
        with tempfile.TemporaryDirectory() as folder:
            for rotation in (0,90,180,270):
                path=os.path.join(folder,str(rotation)+'.pdf');self.make_pdf(path,rotation,True)
                result=parse_pdf(path);meta=result['pages'][0]
                with pymupdf.open(path) as document:
                    page=document[0]
                    bbox=page.get_text('dict',sort=True)['blocks'][0]['lines'][0]['bbox']
                    self.assertEqual(meta['blocks'][0]['rects'][0],normalized_rect(bbox,page))
                png=_page_png(path,os.stat(path).st_mtime_ns,1)
                pix=pymupdf.Pixmap(png)
                self.assertAlmostEqual(pix.width/pix.height,meta['width']/meta['height'],places=2)
                # Highlight region must overlap rendered dark text, rather than blank paper.
                rect=meta['blocks'][0]['rects'][0]
                found=False
                for y in range(int(rect[1]*pix.height),min(pix.height,int(rect[3]*pix.height)+1)):
                    for x in range(int(rect[0]*pix.width),min(pix.width,int(rect[2]*pix.width)+1)):
                        if min(pix.pixel(x,y)[:3])<100:found=True;break
                    if found:break
                self.assertTrue(found)

if __name__=='__main__':unittest.main(verbosity=2)
