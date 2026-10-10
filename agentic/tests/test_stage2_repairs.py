"""Reviewer Stage 2 presentation repairs. Offline, no Streamlit required."""
import json
import unittest

import pandas as pd

from engine import load_csv, run_tool
from presentation import (detailed_group_table, simple_group_table,
                          visible_result_rows, preview_counts, unique_presentation_columns)


class Stage2RepairTests(unittest.TestCase):
    def test_grouped_heading_collision_preserves_both_columns_and_original_evidence(self):
        df=load_csv(b'Total revenue,revenue\nCoffee,10\nSnacks,5\n')
        out=run_tool(df, 'grouped_summary',
                     {'group':'Total revenue','metric':'revenue','operation':'sum'})
        original=json.dumps(out,ensure_ascii=False,sort_keys=True)
        spec=out['evidence']['executed_spec']
        table=simple_group_table(out['rows'],spec)
        self.assertEqual(table,[
            {'Total revenue (group)':'Coffee','Total revenue':'10'},
            {'Total revenue (group)':'Snacks','Total revenue':'5'}])
        self.assertEqual(visible_result_rows(out),table)
        detailed=detailed_group_table(out['rows'],spec)
        self.assertEqual(list(detailed[0]),[
            'Total revenue (group)','Total revenue','Records in group',
            'Records with numeric values'])
        self.assertEqual(detailed[0]['Total revenue (group)'],'Coffee')
        self.assertEqual(detailed[1]['Total revenue (group)'],'Snacks')
        self.assertEqual(detailed[0]['Records in group'],'1')
        self.assertEqual(json.dumps(out,ensure_ascii=False,sort_keys=True),original)

    def test_detailed_count_heading_collision(self):
        df=load_csv(b'Records in group,amount\nCoffee,10\nSnacks,5\n')
        out=run_tool(df,'grouped_summary',
                     {'group':'Records in group','metric':'amount','operation':'sum'})
        detailed=detailed_group_table(out['rows'],out['evidence']['executed_spec'])
        self.assertEqual(len(detailed[0]),4)
        self.assertEqual(len(set(detailed[0])),4)
        self.assertEqual(detailed[0]['Records in group (group)'],'Coffee')
        self.assertEqual(detailed[0]['Records in group'],'1')

    def test_dynamic_labels_are_unique_even_when_roles_recur(self):
        names=unique_presentation_columns([
            ('group_value','Group'),('value','Group'),('row_count','Group'),
            ('non_missing_metric_count','Group')])
        self.assertEqual(len(set(names.values())),4)
        self.assertEqual(names['non_missing_metric_count'],'Group')

    def test_large_integer_and_null_survive_colliding_group_heading(self):
        df=load_csv(b'Total amount,amount\n'+b'A,999999999999999\n'*11+b'B,\n')
        out=run_tool(df,'grouped_summary',
                     {'group':'Total amount','metric':'amount','operation':'sum'})
        original=json.dumps(out)
        rows=simple_group_table(out['rows'],out['evidence']['executed_spec'])
        rendered=pd.DataFrame(rows,dtype=str)
        self.assertEqual(rendered.iloc[0]['Total amount (group)'],'A')
        self.assertEqual(rendered.iloc[0]['Total amount'],'10,999,999,999,999,989')
        self.assertEqual(rendered.iloc[1]['Total amount'],'No numeric value')
        self.assertEqual(json.dumps(out),original)

    @staticmethod
    def filtered_fixture(limit):
        df=load_csv(b'key,segment\n'+b'0001,A\n'*13+b'0002,B\n')
        return run_tool(df,'filter_rows',{'field':'segment','operator':'eq',
                                          'value':'A','limit':limit})

    def test_ui_preview_cap_when_engine_returns_more_than_twelve(self):
        out=self.filtered_fixture(100)
        self.assertEqual(preview_counts(out),{'matched':13,'returned':13,'visible':12})
        self.assertEqual(len(visible_result_rows(out,cap=12)),12)
        self.assertFalse(out['evidence']['display']['truncated'])
        self.assertEqual(out['rows'][12]['key'],'0001')

    def test_engine_truncation_before_ui_preview_cap(self):
        out=self.filtered_fixture(5)
        self.assertEqual(preview_counts(out),{'matched':13,'returned':5,'visible':5})
        self.assertEqual(len(visible_result_rows(out,cap=12)),5)
        self.assertTrue(out['evidence']['display']['truncated'])
        self.assertEqual(out['evidence']['display']['total_result_rows'],13)

    def test_both_engine_and_ui_preview_caps(self):
        out=self.filtered_fixture(13)
        self.assertEqual(preview_counts(out),{'matched':13,'returned':13,'visible':12})
        self.assertEqual(preview_counts(out,cap=7)['visible'],7)
        self.assertEqual(preview_counts(out,cap=13)['visible'],13)

    def test_existing_demo_columns_remain_familiar(self):
        out=run_tool(load_csv(b'category,revenue\nCoffee,3000\nSnacks,1400\n'),
                     'grouped_summary',{'group':'category','metric':'revenue','operation':'sum'})
        self.assertEqual(simple_group_table(out['rows'],out['evidence']['executed_spec']),[
            {'category':'Coffee','Total revenue':'3,000'},
            {'category':'Snacks','Total revenue':'1,400'}])


if __name__=='__main__':
    unittest.main()
