"""Stage 2 offline presentation and response-state regressions."""
import json
import math
import unittest
from datetime import datetime
import pandas as pd
from engine import load_csv, run_tool, AnalysisError
from stage2_logic import calculated_choices, result_selection_key, append_clarification_context, response_failure_kind
from presentation import summary, visible_result_rows, important_notices, observed_period_label, chart_safe

DEMO=b'date,category,region,revenue,units\n2026-01-01,Coffee,North,1200,40\n2026-01-02,Snacks,South,600,30\n2026-02-01,Coffee,South,1800,60\n2026-02-02,Snacks,North,800,40\n'

class Stage2ToolViews(unittest.TestCase):
    def setUp(self): self.df=load_csv(DEMO)

    def test_inspection_overview_and_quality_are_descriptive_only(self):
        out=run_tool(self.df,'inspect_dataset',{})
        self.assertEqual(out['tool'],'inspect_dataset')
        self.assertIn('4 records across 5 columns',summary(out))
        rows=visible_result_rows(out)
        self.assertEqual(rows[0]['Column'],'date')
        self.assertEqual(rows[0]['Missing values'],'0')
        self.assertNotIn('verified',summary(out))

    def test_filtered_rows_distinguish_matched_vs_displayed_preserve_ids(self):
        df=load_csv(b'id,segment,amount\n0007,A,5\n0008,A,6\n0009,B,7\n')
        out=run_tool(df,'filter_rows',{'field':'segment','operator':'eq','value':'A','limit':1})
        self.assertEqual(out['evidence']['accounting']['selected_rows'],2)
        self.assertEqual(out['evidence']['display']['returned_rows'],1)
        self.assertTrue(out['evidence']['display']['truncated'])
        self.assertIn('2 records match',summary(out))
        self.assertEqual(visible_result_rows(out)[0]['id'],'0007')

    def test_grouped_all_operations_and_no_invented_units(self):
        for operation,expected in [('sum',3000),('mean',1500.0),('min',1200),('max',1800),('count_rows',2)]:
            with self.subTest(operation=operation):
                args={'group':'category','operation':operation}
                if operation!='count_rows':args['metric']='revenue'
                out=run_tool(self.df,'grouped_summary',args)
                self.assertIn('Coffee',summary(out))
                self.assertEqual(out['rows'][0]['value'],expected)
                self.assertEqual(len(visible_result_rows(out)[0]),2)
                self.assertNotIn('₹',summary(out))

    def test_grouped_missing_ties_and_display_truncation(self):
        df=load_csv(b'group,number\nA,10\nB,10\nC,\n')
        out=run_tool(df,'grouped_summary',{'group':'group','metric':'number','operation':'sum'})
        self.assertIn('tie',summary(out).lower())
        self.assertEqual(visible_result_rows(out)[-1]['Total of “number”'] if 'Total of “number”' in visible_result_rows(out)[-1] else visible_result_rows(out)[-1]['Total number'],'No numeric value')
        self.assertTrue(any('numeric' in x.lower() for x in important_notices(out)))
        limited=run_tool(df,'grouped_summary',{'group':'group','metric':'number','operation':'sum','display_limit':1})
        self.assertIn('cannot be established',summary(limited))

    def test_time_periods_actual_and_date_semantics_visible(self):
        out=run_tool(self.df,'time_trend',{'date_column':'date','date_format':'%Y-%m-%d',
                       'frequency':'month','metric':'revenue','operation':'sum'})
        self.assertEqual([r['value'] for r in out['rows']],[1800,2600])
        self.assertIn('2 observed month periods',summary(out))
        self.assertEqual([r['Period'] for r in visible_result_rows(out)],['Jan 2026','Feb 2026'])
        self.assertEqual(observed_period_label('2026-01-26','week'),'Week of 26 Jan 2026')

    def test_time_missing_date_exclusion_and_no_implicit_zero(self):
        df=load_csv(b'date,amount\n2026-01-01,5\n,6\n2026-03-01,7\n')
        out=run_tool(df,'time_trend',{'date_column':'date','date_format':'%Y-%m-%d',
                       'frequency':'month','metric':'amount','operation':'sum'})
        self.assertEqual(len(out['rows']),2)
        self.assertEqual([r['value'] for r in out['rows']],[5,7])
        self.assertEqual(out['evidence']['accounting']['operation_exclusions']['missing_date_excluded'],1)
        self.assertTrue(any('date' in x for x in important_notices(out)))

    def test_correlation_usable_pairs_noncausal_and_rejections(self):
        df=load_csv(b'x,y\n1,2\n2,4\n3,6\n4,\n')
        out=run_tool(df,'correlation',{'x':'x','y':'y'})
        self.assertIn('3 complete pairs',summary(out))
        self.assertEqual(visible_result_rows(out)[0]['First column'],'x')
        self.assertEqual(visible_result_rows(out)[0]['Second column'],'y')
        self.assertTrue(any('not cause' in x for x in important_notices(out)))
        with self.assertRaises(AnalysisError):
            run_tool(load_csv(b'x,y\n1,2\n1,3\n1,4\n'),'correlation',{'x':'x','y':'y'})
        with self.assertRaises(AnalysisError):
            run_tool(load_csv(b'x,y\n1,2\n2,\n3,6\n'),'correlation',{'x':'x','y':'y'})

    def test_exact_large_int_null_unchanged(self):
        df=load_csv(b'g,amount\n'+b'A,999999999999999\n'*11+b'B,\n')
        out=run_tool(df,'grouped_summary',{'group':'g','metric':'amount','operation':'sum'})
        before=json.dumps(out)
        rows=visible_result_rows(out)
        self.assertEqual(rows[0]['Total amount'],'10,999,999,999,999,989')
        self.assertEqual(rows[1]['Total amount'],'No numeric value')
        self.assertFalse(chart_safe(out['rows']))
        self.assertEqual(json.dumps(out),before)

class Stage2State(unittest.TestCase):
    def setUp(self):
        df=load_csv(DEMO)
        self.inspect=run_tool(df,'inspect_dataset',{})
        self.group=run_tool(df,'grouped_summary',{'group':'category','metric':'revenue','operation':'sum'})

    def test_inspection_is_support_when_substantive_present(self):
        trace=[{'tool':'inspect_dataset','result':self.inspect},
               {'tool':'grouped_summary','result':self.group}]
        self.assertEqual([x['position'] for x in calculated_choices(trace)],[2])
        self.assertIn('Total of “revenue”',calculated_choices(trace)[0]['label'])

    def test_identical_responses_remain_separate_by_occurrence(self):
        trace=[{'tool':'grouped_summary','result':self.group},
               {'tool':'grouped_summary','result':self.group}]
        choices=calculated_choices(trace)
        self.assertEqual([c['position'] for c in choices],[1,2])
        self.assertNotEqual(choices[0]['label'],choices[1]['label'])
        self.assertEqual(choices[0]['event']['result'],choices[1]['event']['result'])

    def test_definition_labels_expose_filters_and_periods(self):
        df=load_csv(DEMO)
        filt=run_tool(df,'grouped_summary',{'group':'category','metric':'revenue','operation':'mean',
                          'filters':[{'field':'region','operator':'eq','value':'North'}]})
        t=run_tool(df,'time_trend',{'date_column':'date','date_format':'%Y-%m-%d',
                    'frequency':'month','operation':'count_rows'})
        trace=[{'tool':'grouped_summary','result':filt},{'tool':'time_trend','result':t}]
        labels=[c['label'] for c in calculated_choices(trace)]
        self.assertIn('Average of “revenue”',labels[0])
        self.assertIn('North',labels[0]);self.assertIn('%Y-%m-%d',labels[1]);self.assertIn('month',labels[1])

    def test_selection_scope_changes_for_data_question_response_and_rerun(self):
        response={'status':'evidence_available','trace':[{'tool':'grouped_summary','result':self.group}]}
        key=result_selection_key('data-v1','Question',response,1)
        self.assertEqual(key,result_selection_key('data-v1','Question',response,1))
        for changed in [result_selection_key('data-v2','Question',response,1),
                        result_selection_key('data-v1','Other question',response,1),
                        result_selection_key('data-v1','Question',response,2),
                        result_selection_key('data-v1','Question',{'status':'error'},1)]:
            self.assertNotEqual(key,changed)

    def test_calculation_vs_provider_failure_classification(self):
        self.assertEqual(response_failure_kind({'status':'unverified','trace':[{'result':{'error':'Bad date'}}]}),'calculation')
        self.assertEqual(response_failure_kind({'status':'error','trace':[]}), 'provider')
        self.assertEqual(response_failure_kind({'status':'limited','trace':[]}), 'needs_detail')

    def test_contextual_followups_preserve_original_and_are_bounded(self):
        self.assertEqual(append_clarification_context(None,'  Dates are DD/MM/YYYY  '),'Dates are DD/MM/YYYY')
        self.assertEqual(append_clarification_context('Dates are DD/MM/YYYY','Use months'),
                         'Dates are DD/MM/YYYY\nAdditional clarification: Use months')
        for current,next_answer in [(None,''),('a',' '),('x'*1999,'More text')]:
            with self.assertRaises(ValueError):append_clarification_context(current,next_answer)

if __name__=='__main__':unittest.main()
