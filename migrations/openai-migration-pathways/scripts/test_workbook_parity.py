"""Read the exported XLSX with stdlib XML; verify actual stored rows, not its receipt."""
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
import zipfile
import evaluate_routes

N={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def read_sheets(path):
    with zipfile.ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(t.text or '' for t in s.findall('.//s:t',N)) for s in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        book=ET.fromstring(z.read('xl/workbook.xml'))
        rels={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        result={}
        for sheet in book.findall('s:sheets/s:sheet',N):
            target=rels[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
            target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            cells={}
            for c in ET.fromstring(z.read(target)).findall('.//s:sheetData/s:row/s:c',N):
                value=c.find('s:v',N);v=value.text if value is not None else None
                if c.attrib.get('t')=='s':v=strings[int(v)]
                elif c.attrib.get('t')=='inlineStr':v=''.join(x.text or '' for x in c.findall('.//s:t',N))
                elif v is not None and c.attrib.get('t') not in {'str','e','d'}:v=float(v)
                if v is not None:cells[c.attrib['r']]=v
            result[sheet.attrib['name']]=cells
        return result


class WorkbookParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r=json.loads(evaluate_routes.DEFAULT_REGISTRY.read_text())
        cls.s=read_sheets(evaluate_routes.DEFAULT_REGISTRY.parent.parent/'assets/workbooks/openai-bedrock-feature-availability-matrix.xlsx')

    def test_every_route_row(self):
        self.assertEqual(set(self.s),{'Overview','Routes','Features','Rules','Pricing','Evidence'})
        for i,r in enumerate(self.r['routes'],7):
            for col,key in [('B','model_name'),('C','endpoint'),('D','api'),('E','inference_mode'),('F','partition'),('G','model_id')]:
                self.assertEqual(self.s['Routes'][f'{col}{i}'],r[key])
            self.assertEqual(self.s['Routes'][f'H{i}'],', '.join(r['entry_regions']))

    def test_every_feature_row(self):
        i=7
        for r in self.r['routes']:
            for feature,c in r['features'].items():
                self.assertEqual(self.s['Features'][f'B{i}'],feature)
                self.assertEqual(self.s['Features'][f'C{i}'],c['status'])
                self.assertEqual(self.s['Features'][f'D{i}'],c['reason'])
                self.assertEqual(self.s['Features'][f'E{i}'],', '.join(c['sources']));i+=1

    def test_pricing_and_evidence(self):
        i=7
        for m in self.r['models']:
            for p in m['pricing']:
                for col,key in [('D','input'),('E','cache_write'),('F','cache_read'),('G','output')]:
                    self.assertEqual(self.s['Pricing'].get(f'{col}{i}'),p[key])
                i+=1
        for i,source in enumerate(self.r['sources'],7):
            self.assertEqual(self.s['Evidence'][f'A{i}'],source['id'])
            self.assertEqual(self.s['Evidence'][f'E{i}'],source['url'])
            self.assertEqual(self.s['Evidence'][f'D{i}'][:10],source['checked_at'][:10])

    def test_summary_formula_results(self):
        for i,m in enumerate(self.r['models'],7):
            self.assertEqual(self.s['Overview'][f'A{i}'],m['name'])
            self.assertEqual(self.s['Overview'][f'D{i}'],sum(r['model_name']==m['name'] for r in self.r['routes']))


if __name__=='__main__':unittest.main()
