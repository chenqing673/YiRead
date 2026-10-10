"""Chemical diagram glyphs are excluded only with supporting page geometry."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from storage.diagram_labels import chemical_label, page_labels, annotate_blocks
from storage.pdf_parser import parse_pdf
from storage import paper_reader


class DiagramLabels(unittest.TestCase):
    def make_pdf(self,path):
        with pymupdf.open() as document:
            page=document.new_page(width=600,height=800)
            page.insert_text((60,120),'C',fontsize=11)  # Meaningful isolated letter, no bonds.
            page.insert_textbox(pymupdf.Rect(60,160,300,230),'The C and N atoms were studied using 13C NMR and the reaction was stirred for three hours.',fontsize=11)
            for x,text in [(90,'N'),(145,'O'),(200,'NH2'),(255,'Cl')]:
                page.insert_text((x,310),text,fontsize=11)
                page.draw_line((x+4,313),(x+16,328));page.draw_line((x+16,328),(x+31,319))
            page.insert_text((60,380),'Fig. 1. Molecular structures of the compounds.',fontsize=11)
            # Table headings must remain even if they are atomic symbols.
            for y in [430,450,480]:page.draw_line((60,y),(300,y))
            for x in [60,130,200,300]:page.draw_line((x,430),(x,480))
            for x,text in [(70,'C'),(140,'N'),(210,'O')]:page.insert_text((x,445),text,fontsize=11)
            document.save(path)

    def test_notation_matches_atoms_and_subscripts_but_not_prose(self):
        for text in ['C','N','O','NH₂','Cl','HN','CH3','N+','NH2\nO']:
            self.assertTrue(chemical_label(text),text)
        for text in ['13C NMR','Carbon','NO conversion was observed','Fig. 1','1','HPLC']:
            self.assertFalse(chemical_label(text),text)

    def test_bonds_confirm_labels_while_prose_caption_and_table_survive(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'source.pdf';self.make_pdf(path)
            parsed=parse_pdf(path);blocks=parsed['pages'][0]['blocks']
            self.assertEqual([b['text'] for b in blocks if b.get('role')=='diagram-label'],['N','O','NH2','Cl'])
            kept='\n'.join(b['text'] for b in blocks if b.get('role')!='diagram-label')
            self.assertIn('13C NMR',' '.join(kept.split()));self.assertIn('Fig. 1.',kept)
            self.assertGreaterEqual(sum(b['text']=='C' and not b.get('role') for b in blocks),2)

    def test_existing_library_is_classified_without_rewriting_ids_or_files(self):
        with tempfile.TemporaryDirectory() as folder:
            library=Path(folder)/'library'/'fixture';library.mkdir(parents=True)
            source=library/'source.pdf';self.make_pdf(source)
            parsed=parse_pdf(source)
            for block in parsed['pages'][0]['blocks']:block.pop('role',None)
            paper_file=library/'paper.json';paper_file.write_text(json.dumps(parsed))
            before=paper_file.read_bytes()
            with patch.object(paper_reader,'get_data_path',side_effect=lambda name:str(Path(folder)/name)):
                paper=paper_reader.get_paper('fixture')
            self.assertEqual([b['id'] for b in paper['pages'][0]['blocks']],[b['id'] for b in parsed['pages'][0]['blocks']])
            self.assertEqual(sum(b.get('role')=='diagram-label' for b in paper['pages'][0]['blocks']),4)
            self.assertEqual(paper_file.read_bytes(),before)

            # Earlier individual records had no saved rectangles. Resolve their
            # source positions instead of excluding every matching letter.
            for block in parsed['pages'][0]['blocks']:block.pop('rects',None)
            paper_file.write_text(json.dumps(parsed));before=paper_file.read_bytes()
            with patch.object(paper_reader,'get_data_path',side_effect=lambda name:str(Path(folder)/name)):
                paper=paper_reader.get_paper('fixture')
            self.assertEqual(sum(b.get('role')=='diagram-label' for b in paper['pages'][0]['blocks']),4)
            self.assertEqual(paper_file.read_bytes(),before)

    def test_mixed_old_block_removes_only_confirmed_diagram_lines(self):
        blocks=[{'id':'stable','text':'N\nThe reaction gave 75% yield.','rects':[[.1,.2,.11,.22],[.1,.3,.5,.32]]}]
        result=annotate_blocks(blocks,[('N',[.1,.2,.11,.22])])
        self.assertEqual(result[0]['id'],'stable');self.assertEqual(result[0]['text'],'The reaction gave 75% yield.')
        self.assertEqual(blocks[0]['text'],'N\nThe reaction gave 75% yield.')


if __name__=='__main__':unittest.main()
