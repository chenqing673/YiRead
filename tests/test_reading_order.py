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
