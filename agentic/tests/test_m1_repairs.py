"""Independent expected results for M1 reviewer defects: overflow and malformed input."""
import json
import math
import unittest

import pandas as pd

from engine import (AnalysisError, load_csv, execute_spec, run_tool, grouped_summary,
                    time_trend, filter_rows)

HUGE=999999999999999
TOTAL=9999999999999990000  # independent hand calculation: 999999999999999 * 10000


class OverflowRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.group=load_csv(b'g,amount\n'+(f'A,{HUGE}\n'.encode()*10000))
        cls.time=load_csv(b'd,amount\n'+(f'2026-01-01,{HUGE}\n'.encode()*10000))

    def test_group_sum_exceeds_signed_64bit_exactly(self):
        output=execute_spec(self.group,{'tool':'grouped_summary',
            'arguments':{'group':'g','metric':'amount','operation':'sum'}})
        self.assertEqual(output['rows'][0]['value'],TOTAL)
        self.assertIs(type(output['rows'][0]['value']),int)
        self.assertEqual(output['evidence']['calculation_status'],'completed')
        self.assertTrue(any('exact in JSON' in warning for warning in output['evidence']['warnings']))
        self.assertEqual(output['evidence']['accounting']['selected_rows'],10000)
        self.assertEqual(json.loads(json.dumps(output,allow_nan=False))['rows'][0]['value'],TOTAL)

    def test_time_sum_exceeds_signed_64bit_exactly(self):
        out=execute_spec(self.time,{'tool':'time_trend','arguments':{
            'date_column':'d','metric':'amount','date_format':'%Y-%m-%d',
            'frequency':'month','operation':'sum'}})
        self.assertEqual(out['rows'],[{'period_start':'2026-01-01','value':TOTAL,
                                     'row_count':10000,'non_missing_metric_count':10000}])
        self.assertEqual(json.loads(json.dumps(out,allow_nan=False))['rows'][0]['value'],TOTAL)

    def test_mixed_nulls_exact_positive_negative_and_min_max(self):
        df=load_csv((b'g,v\nA,\nA,999999999999999\nA,999999999999999\n'
                     b'B,\nC,-999999999999999\nC,-999999999999999\n'))
        for op,expected in [('sum', [2*HUGE, -2*HUGE, None]),
                             ('min',[HUGE,-HUGE,None]),('max',[HUGE,-HUGE,None])]:
            out=execute_spec(df,{'tool':'grouped_summary','arguments':{
                'group':'g','metric':'v','operation':op}})
            self.assertEqual([row['value'] for row in out['rows']],expected)
            self.assertIsNone(next(r for r in out['rows'] if r['group_value']=='B')['value'])
            json.dumps(out,allow_nan=False)

    def test_means_high_range_rejected_instead_of_rounding(self):
        df=pd.DataFrame({'g':['A','A'],'x':[2**53+1,2**53+3],
                         'd':['2026-01-01']*2})
        for tool,args in [
            ('grouped_summary',{'group':'g','metric':'x','operation':'mean'}),
            ('time_trend',{'date_column':'d','metric':'x','operation':'mean'})]:
            with self.subTest(tool=tool),self.assertRaisesRegex(AnalysisError,'precision'):
                execute_spec(df,{'tool':tool,'arguments':args})

    def test_floating_overflow_rejected_not_completed(self):
        df=pd.DataFrame({'g':['A','A'],'d':['2026-01-01']*2,'x':[1e308,1e308]})
        for tool,args in [
            ('grouped_summary',{'group':'g','metric':'x','operation':'sum'}),
            ('time_trend',{'date_column':'d','metric':'x','operation':'sum'}),
            ('grouped_summary',{'group':'g','metric':'x','operation':'mean'})]:
            with self.subTest(tool=tool,op=args['operation']),self.assertRaisesRegex(AnalysisError,'range|finite|overflow|accumulation'):
                execute_spec(df,{'tool':tool,'arguments':args})

    def test_large_integer_correlation_rejects_precision_loss(self):
        df=pd.DataFrame({'x':[2**53+1,2**53+2,2**53+3], 'y':[1,2,3]})
        with self.assertRaisesRegex(AnalysisError,'precision'):
            execute_spec(df,{'tool':'correlation','arguments':{'x':'x','y':'y'}})

    def test_safe_float_cancellation(self):
        df=pd.DataFrame({'g':['A']*3,'x':[1e100,1.0,-1e100]})
        out=execute_spec(df,{'tool':'grouped_summary',
                              'arguments':{'group':'g','metric':'x','operation':'sum'}})
        self.assertEqual(out['rows'][0]['value'],1.0)

    def test_count_is_not_affected_by_safe_sum(self):
        out=run_tool(self.group,'grouped_summary',{'group':'g','operation':'count_rows'})
        self.assertEqual(out['rows'][0]['value'],10000)

    def test_direct_legacy_tools_share_safe_accumulation(self):
        self.assertEqual(grouped_summary(self.group,'g','amount')['rows'][0]['value'],TOTAL)
        self.assertEqual(time_trend(self.time,'d','amount')['rows'][0]['value'],TOTAL)


class MalformedSpecRegressionTests(unittest.TestCase):
    def setUp(self):
        self.df=load_csv(b'g,amount,d\nA,3,2026-01-01\nB,7,2026-01-02\n')

    def _assert_analysis_error(self,raw):
        with self.assertRaises(AnalysisError) as ctx:
            execute_spec(self.df,raw)
        self.assertTrue(str(ctx.exception))

    def test_filter_operator_list_not_type_error(self):
        self._assert_analysis_error({'tool':'grouped_summary',
            'arguments':{'group':'g','metric':'amount'},
            'filters':[{'field':'g','operator':[],'value':'A'}]})

    def test_date_format_list_not_type_error(self):
        self._assert_analysis_error({'tool':'time_trend',
            'arguments':{'date_column':'d','metric':'amount','date_format':[]}})

    def test_filter_rows_none_filters_not_type_error(self):
        with self.assertRaisesRegex(AnalysisError,'Filters must be a list'):
            run_tool(self.df,'filter_rows',{'field':'g','operator':'eq','value':'A','filters':None})

    def test_more_malformed_specs_are_controlled(self):
        cases=[
            {'tool':'inspect_dataset','arguments':None},
            {'tool':'time_trend','arguments':{'date_column':'d','metric':'amount','date_format':{}}},
            {'tool':'grouped_summary','arguments':{'group':'g','metric':'amount','operation':{}}},
            {'tool':'time_trend','arguments':{'date_column':'d','metric':'amount','operation':[]}},
            {'tool':'time_trend','arguments':{'date_column':'d','metric':'amount','frequency':[]}},
            {'tool':'inspect_dataset','filters':None},
            {'tool':'inspect_dataset','filters':[None]},
            {'tool':'inspect_dataset','filters':{'field':'g'}},
            {'tool':'inspect_dataset','filters':[{'field':'g','operator':{},'value':'A'}]},
            {'tool':'inspect_dataset','filters':[{'field':'g','operator':'eq','value':[]}]},
            {'tool':'inspect_dataset','display_limit':[]},
            {'tool':'inspect_dataset','arguments':{3:'bad'}},
            {'tool':'inspect_dataset','spec_version':[]},
            {'tool':'inspect_dataset','tool':[]},
        ]
        for raw in cases:
            with self.subTest(spec=repr(raw)):
                self._assert_analysis_error(raw)

    def test_bad_run_tool_adapters(self):
        inputs=[
            ([],{}),({},{}),('filter_rows',[]),('grouped_summary',{'group':'g','metric':'amount','filters':None}),
            ('filter_rows',{'field':'g','operator':[],'value':'A'}),
            ('filter_rows',{'field':'g','operator':'eq','value':'A','filters':{}}),
            ('filter_rows',{'field':'g','operator':'eq','value':'A','filters':[None]}),
            ('filter_rows',{'field':'g','operator':'eq','value':'A','filters':None}),
        ]
        for name,args in inputs:
            with self.subTest(name=repr(name),args=repr(args)),self.assertRaises(AnalysisError):
                run_tool(self.df,name,args)

    def test_direct_legacy_entry_points_validate_malformed_types(self):
        with self.assertRaises(AnalysisError): filter_rows(self.df,'g',[],value='A')
        with self.assertRaises(AnalysisError): grouped_summary(self.df,'g','amount',operation=[])
        with self.assertRaises(AnalysisError): time_trend(self.df,'d','amount',date_format=[])
        with self.assertRaises(AnalysisError): grouped_summary(self.df,[], 'amount')


if __name__=='__main__':
    unittest.main()
