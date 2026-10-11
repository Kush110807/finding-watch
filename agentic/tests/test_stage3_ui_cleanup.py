"""Stage 3 UI cleanup contracts; deterministic, no SDK/Streamlit dependency."""
import copy
import unittest
from datetime import datetime
from engine import load_csv, run_tool
from comparisons import prepare_comparison, execute_comparison
from challenge_logic import clear_challenge_review
from presentation import (time_chart_points, observed_period_label, clarification_definition,
                          grouping_phrase, same_numeric_grouping_explanation,
                          confirmed_comparison_matches)

class Stage3CleanupTests(unittest.TestCase):
    def test_month_order_uses_actual_dates_not_month_name(self):
        rows=[{'period_start':'2026-02-01','value':2600},
              {'period_start':'2026-01-01','value':1800}]
        out=time_chart_points(rows,'month')
        self.assertEqual([x['Period'].strftime('%Y-%m-%d') for x in out],
                         ['2026-01-01','2026-02-01'])
        self.assertEqual([x['Value'] for x in out],[1800,2600])
        self.assertEqual([observed_period_label(x['Period'].strftime('%Y-%m-%d'),'month') for x in out],
                         ['Jan 2026','Feb 2026'])
        self.assertTrue(all(isinstance(x['Period'],datetime) for x in out))
        self.assertEqual(rows,[{'period_start':'2026-02-01','value':2600},
                               {'period_start':'2026-01-01','value':1800}])

    def test_missing_time_periods_are_not_fabricated(self):
        rows=[{'period_start':'2027-01-01','value':9},
              {'period_start':'2026-01-01','value':7},
              {'period_start':'2026-03-01','value':8}]
        periods=time_chart_points(rows,'month')
        self.assertEqual([p['Period'].strftime('%Y-%m-%d') for p in periods],
                         ['2026-01-01','2026-03-01','2027-01-01'])
        self.assertEqual(len(periods),len(rows))
        self.assertIsNone(time_chart_points([{'period_start':'not-a-date','value':1}],'month'))

    def test_time_chart_integrates_with_actual_engine_periods(self):
        df=load_csv(b'date,revenue\n2026-02-10,1600\n2026-01-03,1200\n2026-02-04,1000\n2026-01-04,600\n')
        out=run_tool(df,'time_trend',{'date_column':'date','date_format':'%Y-%m-%d',
                                       'metric':'revenue','frequency':'month','operation':'sum'})
        self.assertEqual([(p['Period'].strftime('%Y-%m-%d'),p['Value'])
                          for p in time_chart_points(out['rows'],'month')],
                         [('2026-01-01',1800),('2026-02-01',2600)])

    def test_clarification_does_not_infer_group_or_metric(self):
        self.assertIsNone(clarification_definition(None,'sum','revenue'))
        self.assertIsNone(clarification_definition('category',None,'revenue'))
        self.assertEqual(clarification_definition('category','sum','revenue'),
                         'Compare categories by total revenue.')
        self.assertEqual(clarification_definition('region','mean','units'),
                         'Compare regions by average units.')
        self.assertEqual(clarification_definition('Score','count_rows'),
                         'Compare “Score” values by record count.')
        self.assertEqual(clarification_definition('code','sum','amount'),
                         'Compare “code” values by total amount.')
        self.assertEqual(grouping_phrase('City'),'cities')

    def test_numeric_group_and_metric_kept_with_warning(self):
        warning=same_numeric_grouping_explanation('revenue','revenue')
        self.assertIn('distinct numeric value',warning)
        self.assertIsNone(same_numeric_grouping_explanation('category','revenue'))
        self.assertEqual(clarification_definition('revenue','sum','revenue'),
                         'Compare “revenue” values by total revenue.')

    def test_confirmed_state_survives_rerender_until_explicit_edit(self):
        df=load_csv(b'category,region,revenue\nCoffee,North,1200\nCoffee,South,1800\nSnacks,North,800\nSnacks,South,600\n')
        base={'tool':'grouped_summary','arguments':{'group':'category','metric':'revenue','operation':'sum'},'filters':[]}
        alt={**base,'filters':[{'field':'region','operator':'eq','value':'North'}]}
        plan=prepare_comparison(df,base,alt)
        result=execute_comparison(df,base,alt)
        binding={'dataset':'demo','question':'which leads','occurrence':4}
        state={'review':{'plan':plan},'completed':{'plan':plan,'baseline_binding':binding,'result':result},'editor':False}
        self.assertTrue(confirmed_comparison_matches(state['completed'],state['review']['plan'],binding))
        self.assertTrue(confirmed_comparison_matches(state['completed'],state['review']['plan'],copy.deepcopy(binding)))
        clear_challenge_review(state,'review','completed')
        state['editor']=True
        self.assertNotIn('review',state)
        self.assertNotIn('completed',state)
        self.assertTrue(state['editor'])

if __name__=='__main__':unittest.main()
