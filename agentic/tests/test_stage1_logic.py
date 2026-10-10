"""Offline Stage 1 contracts: no UI, SDK, network or fake browser claims."""
import unittest
from pathlib import Path
from engine import load_csv,run_tool
from stage1_logic import suggested_questions,suggested_date_format,calculated_trace_entries,primary_candidates,two_group_difference,candidate_title
from presentation import display_rows,summary

DEMO=Path(__file__).resolve().parents[1]/'data'/'demo_sales.csv'

class Stage1LogicTests(unittest.TestCase):
    def setUp(self):
        self.df=load_csv(DEMO.read_bytes())

    def test_suggested_demo_runs_locally_with_exact_expected_values(self):
        examples=suggested_questions(list(self.df.columns),['revenue','units'],self.df)
        self.assertTrue(examples)
        first=examples[0]
        self.assertIn('category',first['question'])
        self.assertIn('revenue',first['question'])
        out=run_tool(self.df,first['tool'],first['arguments'])
        self.assertEqual([(r['group_value'],r['value']) for r in out['rows']],
                         [('Coffee',3000),('Snacks',1400)])
        self.assertEqual(out['evidence']['accounting']['input_rows'],4)
        self.assertEqual(out['evidence']['accounting']['selected_rows'],4)
        self.assertEqual(out['evidence']['executed_spec']['filters'],[])
        self.assertEqual(two_group_difference(out)['difference'],1600)

    def test_unknown_schema_no_revenue_or_product_promises(self):
        df=load_csv(b'department,score\nAlpha,3\nBeta,7\nAlpha,2\n')
        examples=suggested_questions(list(df.columns),['score'],df)
        self.assertTrue(examples)
        self.assertTrue(all('revenue' not in e['question'] and 'product' not in e['question'] for e in examples))
        self.assertEqual(examples[0]['arguments'],{'group':'department','metric':'score','operation':'sum'})

    def test_only_id_or_dates_does_not_create_business_group(self):
        df=load_csv(b'order_id,amount\n001,1\n002,2\n')
        self.assertFalse(any(e['tool']=='grouped_summary' for e in suggested_questions(list(df.columns),['amount'],df)))

    def _date_example(self, raw):
        df=load_csv(raw.encode('utf-8'))
        matches=[s for s in suggested_questions(list(df.columns),['amount'],df)
                 if s['tool']=='time_trend']
        return df, matches

    def test_iso_monthly_suggestion_is_executable(self):
        df,matches=self._date_example('period_date,amount\n2026-01-09,4\n2026-02-10,8\n')
        self.assertEqual(len(matches),1)
        self.assertEqual(matches[0]['arguments']['date_format'],'%Y-%m-%d')
        out=run_tool(df,matches[0]['tool'],matches[0]['arguments'])
        self.assertEqual(out['evidence']['accounting']['selected_rows'],2)
        self.assertEqual(sum(r['value'] for r in out['rows']),2)

    def test_unambiguous_day_first_format_is_selected_from_values(self):
        df,matches=self._date_example('purchase_date,amount\n13/02/2026,4\n03/03/2026,8\n')
        self.assertEqual(len(matches),1)
        self.assertEqual(matches[0]['arguments']['date_format'],'%d/%m/%Y')
        out=run_tool(df,matches[0]['tool'],matches[0]['arguments'])
        self.assertEqual(sum(r['value'] for r in out['rows']),2)

    def test_unambiguous_month_first_format_is_selected_from_values(self):
        df,matches=self._date_example('sale_date,amount\n02/13/2026,4\n03/05/2026,8\n')
        self.assertEqual(len(matches),1)
        self.assertEqual(matches[0]['arguments']['date_format'],'%m/%d/%Y')
        self.assertEqual(sum(r['value'] for r in run_tool(df,matches[0]['tool'],matches[0]['arguments'])['rows']),2)

    def test_ambiguous_slash_dates_never_create_monthly_suggestion(self):
        _,matches=self._date_example('sale_date,amount\n01/02/2026,4\n03/04/2026,8\n')
        self.assertFalse(matches)
        self.assertIsNone(suggested_date_format(['01/02/2026','03/04/2026']))

    def test_invalid_dates_prevent_monthly_suggestion_instead_of_dropping_rows(self):
        for raw in ('2026-02-30','2026-01-10\nnot-a-date',
                    ' 2026-01-10 ', '2026-01-10 ',
                    '1400-01-10', '3000-01-10',
                    '13/02/2026\n31/02/2026','2026-01-01T10:30:00'):
            with self.subTest(raw=raw):
                _,matches=self._date_example('invoice_date,amount\n'+
                    '\n'.join(date+',1' for date in raw.split('\n'))+'\n')
                self.assertFalse(matches)

    def test_empty_dates_never_suggest_and_missing_values_are_not_invalid(self):
        _,empty=self._date_example('created_date,amount\n,4\n,8\n')
        self.assertFalse(empty)
        df,matches=self._date_example('created_date,amount\n2026-01-10,4\n,8\n')
        self.assertEqual(len(matches),1)
        self.assertEqual(matches[0]['arguments']['date_format'],'%Y-%m-%d')
        # Exactly one valid date: the missing row is excluded by deterministic engine.
        out=run_tool(df,matches[0]['tool'],matches[0]['arguments'])
        self.assertEqual(sum(r['value'] for r in out['rows']),1)
        self.assertEqual(out['evidence']['accounting']['input_rows'],2)

    def test_date_named_column_with_identifiers_does_not_guess_calendar_format(self):
        _,matches=self._date_example('effective_date,amount\n20260101,4\n20260201,8\n')
        self.assertFalse(matches)

    def test_inspection_then_grouping_primary_is_aggregation(self):
        inspected=run_tool(self.df,'inspect_dataset',{})
        grouped=run_tool(self.df,'grouped_summary',{'group':'category','metric':'revenue','operation':'sum'})
        trace=[{'tool':'inspect_dataset','result':inspected}, {'tool':'grouped_summary','result':grouped}]
        self.assertEqual(len(calculated_trace_entries(trace)),2)
        self.assertEqual(primary_candidates(trace),[(2,trace[1])])

    def test_two_analytical_results_require_choice(self):
        group=run_tool(self.df,'grouped_summary',{'group':'category','operation':'count_rows'})
        trend=run_tool(self.df,'time_trend',{'date_column':'date','date_format':'%Y-%m-%d','frequency':'month','operation':'count_rows'})
        trace=[{'tool':'grouped_summary','result':group},{'tool':'time_trend','result':trend}]
        self.assertEqual(len(primary_candidates(trace)),2)
        self.assertNotEqual(candidate_title(1,trace[0]),candidate_title(2,trace[1]))

    def test_identical_results_keep_separate_trace_occurrences(self):
        group=run_tool(self.df,'grouped_summary',{'group':'category','operation':'count_rows'})
        trace=[{'tool':'grouped_summary','result':group}]*2
        self.assertEqual([idx for idx,_ in primary_candidates(trace)],[1,2])

    def test_no_successful_calculation_has_no_primary(self):
        self.assertEqual(primary_candidates([{'tool':'grouped_summary','result':{'error':'Invalid'}}]),[])

    def test_exact_integer_and_null_still_safe_before_pandas(self):
        rows=[{'group_value':'A','value':10999999999999989}, {'group_value':'B','value':None}]
        shown=display_rows(rows)
        self.assertEqual(shown[0]['value'],'10,999,999,999,999,989')
        self.assertEqual(shown[1]['value'],'No numeric value')
        self.assertEqual(rows[0]['value'],10999999999999989)
        self.assertIsNone(rows[1]['value'])

    def test_difference_returns_none_for_missing_and_truncated(self):
        out=run_tool(self.df,'grouped_summary',{'group':'category','metric':'revenue','operation':'sum'})
        out['rows'][1]['value']=None
        self.assertIsNone(two_group_difference(out))
        out['rows'][1]['value']=1400
        out['evidence']['display']['truncated']=True
        self.assertIsNone(two_group_difference(out))

    def test_ties_do_not_get_invented_leader(self):
        df=load_csv(b'type,score\nA,10\nB,10\n')
        out=run_tool(df,'grouped_summary',{'group':'type','metric':'score','operation':'sum'})
        self.assertTrue(two_group_difference(out)['tie'])
        self.assertIn('tie',summary(out).lower())

if __name__=='__main__': unittest.main()
