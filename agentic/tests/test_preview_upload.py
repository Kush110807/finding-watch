"""Regression: preview formatting must not mutate nullable numeric source data."""
import json
import unittest

import pandas as pd

from engine import load_csv, run_tool
from presentation import preview_display_table


UNFAMILIAR = (b'ref_code,zone_label,measurement\n'
              b'0001,Alpha,10\n'
              b'0002,Alpha,\n'
              b'0003,Beta,5\n')


class PreviewUploadTests(unittest.TestCase):
    def test_nullable_numeric_preview_and_grouped_accounting(self):
        source = load_csv(UNFAMILIAR)
        before = source.copy(deep=True)
        self.assertEqual(str(source['measurement'].dtype), 'Int64')
        table = preview_display_table(source.head(30))
        self.assertEqual(list(table['ref_code']), ['0001', '0002', '0003'])
        self.assertEqual(list(table['measurement']), ['10', 'Missing', '5'])
        pd.testing.assert_frame_equal(source, before)
        self.assertTrue(pd.isna(source.loc[1, 'measurement']))

        profile = run_tool(source, 'inspect_dataset', {})
        profile_display = preview_display_table(pd.DataFrame(profile['rows']))
        self.assertEqual(len(profile_display), 3)
        self.assertEqual(profile['metadata']['total_rows'], 3)
        self.assertEqual(next(r for r in profile['rows'] if r['column'] == 'measurement')['missing'], 1)

        grouped = run_tool(source, 'grouped_summary',
                           {'group': 'zone_label', 'metric': 'measurement', 'operation': 'sum'})
        self.assertEqual({r['group_value']: r['value'] for r in grouped['rows']},
                         {'Alpha': 10, 'Beta': 5})
        self.assertEqual(grouped['evidence']['accounting']['operation_exclusions']
                         ['missing_metric_excluded_from_values'], 1)
        self.assertEqual(grouped['evidence']['accounting']['selected_rows'], 3)
        self.assertEqual(grouped['rows'][0]['row_count'], 2)
        pd.testing.assert_frame_equal(source, before)

    def test_exact_large_nullable_integer_and_literal_missing_text(self):
        raw = (b'ref_code,segment,total\n'
               b'0007,Missing,999999999999999\n'
               b'0012,Other,\n')
        source = load_csv(raw)
        before = source.copy(deep=True)
        table = preview_display_table(source)
        self.assertEqual(table.loc[0, 'ref_code'], '0007')
        self.assertEqual(table.loc[0, 'segment'], 'Missing')
        self.assertEqual(table.loc[0, 'total'], '999999999999999')
        self.assertEqual(table.loc[1, 'total'], 'Missing')
        self.assertEqual(table.loc[1, 'ref_code'], '0012')
        pd.testing.assert_frame_equal(source, before)
        out = run_tool(source, 'grouped_summary',
                       {'group': 'segment', 'metric': 'total', 'operation': 'sum'})
        self.assertEqual({r['group_value']: r['value'] for r in out['rows']},
                         {'Missing': 999999999999999, 'Other': None})
        self.assertIn('999999999999999', json.dumps(out))
        self.assertTrue(pd.isna(source.loc[1, 'total']))

    def test_input_preview_is_bounded_without_discarding_analysis_rows(self):
        raw = ('ref_code,segment,measurement\n' +
               ''.join(f'{i:04d},A,{i}\n' for i in range(1, 36))).encode()
        source = load_csv(raw)
        table = preview_display_table(source.head(30))
        self.assertEqual(len(table), 30)
        self.assertEqual(table.iloc[0]['ref_code'], '0001')
        self.assertEqual(len(source), 35)
        out = run_tool(source, 'grouped_summary',
                       {'group': 'segment', 'metric': 'measurement', 'operation': 'sum'})
        self.assertEqual(out['rows'][0]['value'], sum(range(1, 36)))
        self.assertEqual(out['evidence']['accounting']['input_rows'], 35)


if __name__ == '__main__':
    unittest.main()
