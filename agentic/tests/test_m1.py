"""Independent M1 fixtures: expected values calculated manually, not via tools."""
import json
import math
import unittest
import pandas as pd
from engine import load_csv, run_tool, execute_spec, AnalysisError, numeric_columns

class ComposableAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.raw=(b'order_id,date,category,region,status,revenue,x,y\n'
                  b'0001,2026-01-01,Coffee,North,complete,10,1,2\n'
                  b'0002,2026-01-02,Coffee,South,complete,20,2,4\n'
                  b'0003,2026-01-03,Snacks,North,complete,30,3,6\n'
                  b'0004,2026-02-01,Coffee,North,cancelled,300,4,8\n'
                  b'0005,2026-02-02,Snacks,South,complete,40,,10\n'
                  b'0006,,Snacks,North,complete,,6,\n'
                  b'0007,2026-02-03,,North,complete,5,,\n')
        self.df=load_csv(self.raw)

    def do(self,tool,args=None,filters=None,limit=None):
        spec={'spec_version':1,'tool':tool,'arguments':args or {},'filters':filters or []}
        if limit is not None: spec['display_limit']=limit
        return execute_spec(self.df,spec)

    def test_combined_filters_full_aggregation(self):
        output=self.do('grouped_summary',{'group':'category','metric':'revenue','operation':'sum'},[
            {'field':'region','operator':'eq','value':'North'},
            {'field':'status','operator':'eq','value':'complete'}])
        values={row['group_value']:row['value'] for row in output['rows']}
        self.assertEqual(values,{'Coffee':10,'Snacks':30,None:5})
        ac=output['evidence']['accounting']
        self.assertEqual((ac['input_rows'],ac['selected_rows'],ac['excluded_by_filters']),(7,4,3))
        self.assertEqual([s['newly_excluded'] for s in ac['filters_sequential']],[2,1])
        self.assertEqual(ac['operation_exclusions']['missing_metric_excluded_from_values'],1)
        self.assertEqual(ac['operation_exclusions']['missing_group_labels_included'],1)
        self.assertEqual(sum(r['row_count'] for r in output['rows']),4)

    def test_overlapping_filter_exclusions_not_double_counted(self):
        filters=[{'field':'region','operator':'eq','value':'North'},
                 {'field':'region','operator':'ne','value':'South'},
                 {'field':'status','operator':'eq','value':'complete'}]
        out=self.do('grouped_summary',{'group':'status','operation':'count_rows'},filters)
        self.assertEqual([f['newly_excluded'] for f in out['evidence']['accounting']['filters_sequential']],[2,0,1])
        self.assertEqual(out['evidence']['accounting']['excluded_by_filters'],3)

    def test_full_data_not_preview(self):
        payload=b'group,units\n'+(b'A,1\n'*1500)+(b'B,4\n'*15)
        large=load_csv(payload)
        inspect=run_tool(large,'filter_rows',{'field':'group','operator':'eq','value':'A','limit':2})
        self.assertEqual(len(inspect['rows']),2)
        self.assertTrue(inspect['evidence']['display']['truncated'])
        totals=run_tool(large,'grouped_summary',{'group':'group','metric':'units','operation':'sum',
                 'filters':[{'field':'group','operator':'eq','value':'A'}],'display_limit':1})
        self.assertEqual(totals['rows'][0]['value'],1500)
        self.assertEqual(totals['evidence']['accounting']['selected_rows'],1500)
        self.assertFalse(totals['evidence']['display']['truncated'])

    def test_result_truncation_does_not_affect_aggregation(self):
        out=self.do('grouped_summary',{'group':'category','metric':'revenue','operation':'sum'},limit=1)
        self.assertEqual(len(out['rows']),1)
        self.assertEqual(out['evidence']['display'],{
            'limit':1,'total_result_rows':3,'returned_rows':1,'truncated':True})
        self.assertEqual(out['rows'][0]['value'],330) # includes the cancelled record (unfiltered)

    def test_explicit_time_filters_with_missing_overlap(self):
        out=self.do('time_trend',{'date_column':'date','metric':'revenue','date_format':'%Y-%m-%d',
                                 'frequency':'month','operation':'sum'},[
                {'field':'status','operator':'eq','value':'complete'}])
        self.assertEqual([(r['period_start'],r['value']) for r in out['rows']],
                         [('2026-01-01',60),('2026-02-01',45)])
        x=out['evidence']['accounting']['operation_exclusions']
        self.assertEqual(x,{'missing_date_excluded':1,'missing_metric_and_date_overlap':1,
                            'missing_metric_with_valid_date_excluded_from_values':0,
                            'excluded_from_numeric_values_union':1})
        self.assertEqual(out['evidence']['accounting']['selected_rows'],6)

    def test_time_double_missing_partitions(self):
        d=load_csv(b'd,v\n,\n2026-01-01,\n,3\n2026-01-01,4\n')
        out=execute_spec(d,{'tool':'time_trend','arguments':{'date_column':'d','metric':'v'},'filters':[]})
        self.assertEqual(out['rows'][0]['value'],4)
        self.assertEqual(out['evidence']['accounting']['operation_exclusions'],{
            'missing_date_excluded':2,'missing_metric_and_date_overlap':1,
            'missing_metric_with_valid_date_excluded_from_values':1,
            'excluded_from_numeric_values_union':3})

    def test_correlations_filter_and_disjoint_missing_partitions(self):
        out=self.do('correlation',{'x':'x','y':'y'},[
            {'field':'status','operator':'eq','value':'complete'}])
        # Complete pairs are (1,2), (2,4), (3,6); exactly r=1.
        self.assertAlmostEqual(out['rows'][0]['pearson_r'],1.0)
        self.assertEqual(out['evidence']['accounting']['operation_exclusions'],{
            'missing_x_only':1,'missing_y_only':1,'missing_both':1,
            'excluded_incomplete_pairs_union':3,'complete_pairs':3})

    def test_identifiers_and_explicit_parse_policy(self):
        self.assertEqual(self.df['order_id'].tolist(),['0001','0002','0003','0004','0005','0006','0007'])
        self.assertNotIn('order_id',numeric_columns(self.df))
        self.assertIn('revenue',numeric_columns(self.df))
        self.assertEqual(self.df['date'].iloc[0],'2026-01-01')
        self.assertEqual(len(self.df.attrs['source_sha256']),64)
        r=self.do('grouped_summary',{'group':'order_id','operation':'count_rows'})
        self.assertEqual(r['rows'][0]['group_value'],'0001')
        self.assertEqual(r['evidence']['dataset_fingerprint_sha256'],self.df.attrs['source_sha256'])

    def test_numeric_looking_identifiers_in_generic_columns(self):
        d=load_csv(b'token,account,amount\n0012,123456,2.50\n0009,123457,3.25\n')
        self.assertEqual(d['token'].tolist(),['0012','0009'])
        self.assertEqual(d['account'].tolist(),['123456','123457'])
        self.assertIn('amount',numeric_columns(d))

    def test_ambiguous_numeric_and_dates_are_rejected(self):
        d=load_csv(b'g,metric,when\nA,01,01/02/2026\nB,02,02/03/2026\n')
        with self.assertRaisesRegex(AnalysisError,'ambiguous'):
            execute_spec(d,{'tool':'grouped_summary','arguments':{'group':'g','metric':'metric'}})
        r=execute_spec(d,{'tool':'time_trend',
            'arguments':{'date_column':'when','operation':'count_rows','date_format':'%d/%m/%Y'}})
        self.assertEqual(r['rows'][0]['period_start'],'2026-02-01')

    def test_empty_selection_is_explicit_error(self):
        with self.assertRaisesRegex(AnalysisError,'No rows match'):
            self.do('grouped_summary',{'group':'category','metric':'revenue'},[
                {'field':'region','operator':'eq','value':'East'}])

    def test_missing_group_and_tied_top_warning(self):
        d=load_csv(b'g,v\nA,2\nB,2\n,\n')
        r=execute_spec(d,{'tool':'grouped_summary','arguments':{'group':'g','metric':'v'}})
        self.assertEqual(r['rows'][2]['group_value'],None)
        self.assertTrue(any('tie' in w for w in r['evidence']['warnings']))

    def test_invalid_spec_types_columns_and_ops(self):
        bad=[
            {'tool':'danger'},
            {'tool':'grouped_summary','arguments':{'group':'category','metric':'revenue','operation':'median'}},
            {'tool':'grouped_summary','arguments':{'group':'invalid','metric':'revenue'}},
            {'tool':'correlation','arguments':{'x':'x','y':'y','secret':'foo'}},
            {'tool':'grouped_summary','arguments':{'group':'category','operation':'count_rows','metric':'revenue'}},
            {'tool':'inspect_dataset','filters':[{'field':'region','operator':'regexp','value':'N.*'}]},
            {'tool':'inspect_dataset','filters':[{'field':'region','operator':'gt','value':'North'}]},
            {'tool':'inspect_dataset','filters':[{'field':'region','operator':'eq','value':'North'}]*9},
            {'tool':'inspect_dataset','display_limit':0},
            {'tool':'inspect_dataset','display_limit':True},
            {'tool':'inspect_dataset','display_limit':float('nan')},
            {'tool':'correlation','arguments':{'x':'x','y':'y'},'filters':[{'field':'x','operator':'lt','value':float('inf')}]},
            {'tool':'filter_rows'},
            {'tool':'inspect_dataset','unknown':True},
            {'tool':'inspect_dataset','spec_version':2},
        ]
        for spec in bad:
            with self.subTest(spec=spec),self.assertRaises(AnalysisError):
                execute_spec(self.df,spec)

    def test_nonfinite_and_unsupported_data(self):
        d=load_csv(b'category,value\nA,inf\nB,3\n')
        with self.assertRaises(AnalysisError):
            execute_spec(d,{'tool':'grouped_summary','arguments':{'group':'category','metric':'value'}})
        d2=pd.DataFrame({'group':['A','A'],'metric':[float('inf'),3]})
        with self.assertRaises(AnalysisError):
            execute_spec(d2,{'tool':'grouped_summary','arguments':{'group':'group','metric':'metric'}})

    def test_input_immutability_json_finiteness(self):
        before=self.df.copy(deep=True)
        specs=[
            ('grouped_summary',{'group':'category','metric':'revenue'}),
            ('time_trend',{'date_column':'date','metric':'revenue'}),
            ('correlation',{'x':'x','y':'y'}),
            ('filter_rows',{})]
        for tool,args in specs:
            filters=[{'field':'region','operator':'eq','value':'North'}] if tool!='correlation' else []
            if tool=='filter_rows': filters=[{'field':'region','operator':'eq','value':'North'}]
            if tool=='correlation':
                filters=[]
            if tool=='time_trend':
                # selected North has a missing date; still has valid dates.
                pass
            try:
                r=self.do(tool,args,filters)
                json.dumps(r,allow_nan=False)
            except AnalysisError as exc:
                # correlation has four complete pairs and should always work
                self.fail(str(exc))
            pd.testing.assert_frame_equal(self.df,before)
            self.assertEqual(self.df.attrs,before.attrs)

    def test_unfamiliar_schemas(self):
        d=load_csv(b'city,weight,price\nDelhi,3,100\nMumbai,2,40\nDelhi,1,10\n')
        r=execute_spec(d,{'tool':'grouped_summary','arguments':{'group':'city','metric':'price'},
                          'filters':[{'field':'weight','operator':'ge','value':2}]})
        self.assertEqual([(row['group_value'],row['value']) for row in r['rows']],
                         [('Delhi',100),('Mumbai',40)])
        q=load_csv(b'week_date,marks,hours\n2026-01-05,10,2\n2026-01-12,20,4\n2026-01-19,30,6\n')
        r=execute_spec(q,{'tool':'correlation','arguments':{'x':'marks','y':'hours'}})
        self.assertAlmostEqual(r['rows'][0]['pearson_r'],1.)

if __name__=='__main__': unittest.main()
