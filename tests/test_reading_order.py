"""Reading order tests use synthetic PDFs and never change the user's library."""
import sys,tempfile,unittest,copy,json
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import pymupdf
from storage.reading_order import order_items,ordered_blocks
from storage.pdf_parser import parse_pdf
from storage import paper_reader

def item(name,x,y,w=.30,h=.025):return {'name':name,'box':[x,y,x+w,y+h]}

class ReadingOrder(unittest.TestCase):
    def test_narrow_journal_gutter_is_not_read_row_by_row(self):
        items=[item(prefix+str(n),x,.1+n*.04,.435,.01) for n in range(4) for x,prefix in [(.06,'L'),(.515,'R')]]
        self.assertEqual([i['name'] for i in order_items(items)],[prefix+str(n) for prefix in 'LR' for n in range(4)])

    def test_column_widths_change_below_abstract_separator(self):
        items=[item(prefix+str(n),x,.2+n*.04,w,.01) for n in range(3) for x,w,prefix in [(.06,.22,'INFO'),(.34,.60,'ABSTRACT')]]
        items.append(item('rule',0,.5,1,0))
        items.extend(item(prefix+str(n),x,.6+n*.04,.435,.01) for n in range(3) for x,prefix in [(.06,'L'),(.515,'R')])
        expected=[prefix+str(n) for prefix in ['INFO','ABSTRACT'] for n in range(3)]+['rule']+[prefix+str(n) for prefix in 'LR' for n in range(3)]
        self.assertEqual([i['name'] for i in order_items(items)],expected)

    def test_existing_tall_paragraphs_use_line_geometry_including_rotated_pdf(self):
        blocks=[{'id':prefix,'text':prefix,'rects':[[x,y,x+.435,y+.01] for y in [.1,.2,.3]]} for x,prefix in [(.515,'R'),(.06,'L')]]
        self.assertEqual([b['id'] for b in ordered_blocks(blocks)],['L','R'])
        rotated=[{**b,'rects':[[1-r[3],r[0],1-r[1],r[2]] for r in b['rects']]} for b in blocks]
        self.assertEqual([b['id'] for b in ordered_blocks(rotated,rotation=90)],['L','R'])

    def test_actual_pdf_with_abstract_rules_and_narrow_body_columns(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'journal.pdf'
            with pymupdf.open() as doc:
                page=doc.new_page(width=600,height=800)
                for n,y in enumerate([150,170,190]):
                    page.insert_text((40,y),'ARTICLE INFO '+str(n),fontsize=9)
                    page.insert_text((204,y),'ABSTRACT '+str(n)+' '+('chemical conditions '*5),fontsize=9)
                page.draw_line((40,220),(560,220))
                for n,y in enumerate([260,330,400]):
                    for x,prefix in [(40,'LEFT'),(306,'RIGHT')]:
                        self.assertGreaterEqual(page.insert_textbox(pymupdf.Rect(x,y,x+252,y+60),prefix+str(n)+' '+('synthetic conditions '*5),fontsize=10),0)
                doc.save(path)
            text='\n'.join(b['text'] for b in parse_pdf(path)['pages'][0]['blocks'])
            self.assertLess(text.index('LEFT2'),text.index('RIGHT0'))
            self.assertLess(text.index('ABSTRACT 2'),text.index('LEFT0'))

    def test_two_columns_with_full_width_title_and_middle_caption(self):
        items=[item('title',.1,.02,.8),item('caption',.1,.5,.8)]
        for x,prefix in [(.1,'L'),(.6,'R')]:
            for index,y in enumerate([.15,.25,.65,.75]):items.append(item(prefix+str(index),x,y))
        self.assertEqual([i['name'] for i in order_items(items)],['title','L0','L1','R0','R1','caption','L2','L3','R2','R3'])

    def test_three_columns_not_row_major(self):
        items=[item(prefix+str(index),x,y,.23) for index,y in enumerate([.15,.25,.35]) for x,prefix in [(.05,'A'),(.38,'B'),(.71,'C')]]
        self.assertEqual([i['name'] for i in order_items(items)],[prefix+str(index) for prefix in 'ABC' for index in range(3)])

    def test_single_column_and_short_indented_labels_stay_vertical(self):
        items=[item('first',.1,.1,.8),item('label',.3,.2,.06),item('next',.1,.3,.8)]
        self.assertEqual([i['name'] for i in order_items(items)],['first','label','next'])

    def test_existing_ids_and_text_are_preserved_without_mutation(self):
        items=[item(prefix+str(index),x,y) for index,y in enumerate([.1,.2,.3]) for x,prefix in [(.1,'L'),(.6,'R')]]
        blocks=[{'id':i['name'],'text':i['name'],'rects':[i['box']]} for i in items];before=copy.deepcopy(blocks)
        self.assertEqual([b['id'] for b in ordered_blocks(blocks)],['L0','L1','L2','R0','R1','R2'])
        self.assertEqual(blocks,before)
        self.assertEqual(ordered_blocks([{'id':'old','text':'no geometry'}]),[{'id':'old','text':'no geometry'}])

    def test_actual_pdf_extracts_complete_left_column_before_right(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'columns.pdf'
            with pymupdf.open() as doc:
                page=doc.new_page(width=600,height=800)
                page.insert_text((50,40),'A full width academic title across the two columns',fontsize=18)
                # Interleave writing order deliberately: PDF object order is not reading order.
                for index,y in enumerate([100,180,260]):
                    for x,prefix in [(50,'LEFT'),(330,'RIGHT')]:
                        page.insert_textbox(pymupdf.Rect(x,y,x+220,y+65),prefix+str(index)+' paragraph describes synthetic chemistry conditions and yields.',fontsize=11)
                doc.save(path)
            parsed=parse_pdf(path);text='\n'.join(b['text'] for b in parsed['pages'][0]['blocks'])
            self.assertLess(text.index('LEFT2'),text.index('RIGHT0'))
            self.assertLess(text.index('LEFT0'),text.index('LEFT1'))
            self.assertEqual(text.count('RIGHT2'),1)
            self.assertTrue(all(b['rects'] for b in parsed['pages'][0]['blocks']))

    def test_legacy_page_recovers_order_without_rewriting_ids_or_saved_data(self):
        with tempfile.TemporaryDirectory() as folder:
            paper_dir=Path(folder)/'legacy';paper_dir.mkdir()
            with pymupdf.open() as doc:
                page=doc.new_page(width=600,height=800)
                for index,y in enumerate([100,180,260]):
                    for x,prefix in [(50,'LEFT'),(330,'RIGHT')]:
                        page.insert_textbox(pymupdf.Rect(x,y,x+220,y+65),prefix+str(index)+' paragraph describes synthetic chemistry conditions and yields.',fontsize=11)
                doc.save(paper_dir/'source.pdf')
            saved=json.dumps({'pages':[{'page':1,'blocks':[{'id':'original-page-id','text':'old scrambled source '*100}]}]}).encode()
            (paper_dir/'paper.json').write_bytes(saved)
            with patch.object(paper_reader,'get_data_path',return_value=folder):
                result=paper_reader.get_paper('legacy')['pages'][0]['blocks'][0]
            self.assertEqual(result['id'],'original-page-id')
            self.assertLess(result['text'].index('LEFT2'),result['text'].index('RIGHT0'))
            self.assertTrue(result['rects'])
            self.assertEqual((paper_dir/'paper.json').read_bytes(),saved)

if __name__=='__main__':unittest.main(verbosity=2)
