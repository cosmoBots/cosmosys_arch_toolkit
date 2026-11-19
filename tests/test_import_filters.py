import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from import_filters import classify, read_filters


class ImportFiltersTest(unittest.TestCase):
    def test_profiles_and_exceptions(self):
        rules = read_filters(Path(__file__).resolve().parents[1] / 'examples/filters/BancoIFU.csv')
        names = ['DIN912-M03X12', 'TORNILLO_DIN-912_M3X12', 'ISO2338_3',
                 'M6X14', 'FOLDING-MIRROR', 'DIN_TRACK_35', '44V-M70-110_BASE_PLATE_MAIN',
                 'POSICIONADOR_M04X10', 'POSICIONADOR_M03X05.001', 'ST_M12X10_C', 'SCREW_HOLDER']
        modes, _ = classify(names, rules)
        self.assertEqual(modes, ['exclude'] * 4 + ['include'] * 7)

    def test_order_case_and_atomic(self):
        modes, rows = classify(['Piston', 'Kit', 'KitKeep'], [
            dict(search='text', pattern='PISTON', action='exclude'),
            dict(search='regex', pattern='^kit', action='atomic'),
            dict(search='text', pattern='keep', action='include')])
        self.assertEqual(modes, ['exclude', 'atomic', 'include'])
        self.assertEqual(rows[1]['matches'], [1, 2])

    def test_csv_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'filters.csv'
            for contents in ['pattern,search,action\n', 'search,pattern,action\nregex,[,exclude\n',
                             'search,pattern,action\ntext,,atomic\n',
                             'search,pattern,action\ntext,x,delete\n']:
                path.write_text(contents)
                with self.assertRaises(ValueError):
                    read_filters(path)
            path.write_text('\ufeffsearch,pattern,action\r\ntext,"one,two",atomic\r\n')
            self.assertEqual(read_filters(path)[0]['pattern'], 'one,two')
