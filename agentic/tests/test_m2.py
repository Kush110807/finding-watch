"""Deterministic M2 regression suite with independently enumerated expected values."""
import copy
import json
import unittest
import pandas as pd
from engine import AnalysisError, load_csv
from comparisons import prepare_comparison, execute_comparison

GOLDEN = (b'category,status,revenue\nCoffee,completed,120\nCoffee,completed,90\n'
          b'Coffee,cancelled,300\nSnacks,completed,180\nSnacks,completed,100\n')

def spec(filters=None, *, group='category', metric='revenue', operation='sum', limit=100):
    arguments={'group':group,'operation':operation}
    if operation!='count_rows':
        arguments['metric']=metric
    return {'tool':'grouped_summary','arguments':arguments,'filters':filters or [],
            'display_limit':limit}

COMPLETE={'field':'status','operator':'eq','value':'completed'}

class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.df=load_csv(GOLDEN)
        self.baseline=spec()
        self.challenge=spec([COMPLETE])

    def check_error(self,a,b,needle):
        with self.assertRaises(AnalysisError) as ctx:
            execute_comparison(self.df,a,b)
        self.assertIn(needle.lower(),str(ctx.exception).lower())

    def test_golden_independent_expected_totals_and_counts(self):
        r=execute_comparison(self.df,self.baseline,self.challenge)
        rows={x['group_value']:x for x in r['comparison']['all_results']}
        self.assertEqual({k:(v['baseline_value'],v['challenged_value'],v['difference_challenged_minus_baseline'])
                          for k,v in rows.items()}, {'Coffee':(510,210,-300),'Snacks':(280,280,0)})
        self.assertEqual((r['accounting']['baseline']['selected_rows'],r['accounting']['challenged']['selected_rows']),(5,4))
        self.assertEqual(r['accounting']['challenged']['excluded_by_filters'],1)
        self.assertEqual(r['changed_condition'],{'kind':'added','before':None,'after':COMPLETE})
        self.assertEqual((r['comparison']['baseline_leaders'],r['comparison']['challenged_leaders']),(['Coffee'],['Snacks']))
        self.assertTrue(r['comparison']['leader_changed'])
        self.assertEqual(r['baseline_spec']['arguments'],r['challenged_spec']['arguments'])
        self.assertEqual(r['baseline']['evidence']['calculation_status'],'completed')
        self.assertEqual(r['challenged']['evidence']['calculation_status'],'completed')
        json.loads(json.dumps(r,allow_nan=False))

    def test_preview_does_not_calculate(self):
        p=prepare_comparison(self.df,self.baseline,self.challenge)
        self.assertTrue(p['confirmation_required'])
        self.assertNotIn('comparison',p)
        self.assertNotIn('results',p)

    def test_same_leader(self):
        r=execute_comparison(self.df,self.baseline,spec([{'field':'status','operator':'ne','value':'completed'}]))
        self.assertEqual((r['comparison']['baseline_leaders'],r['comparison']['challenged_leaders']),(['Coffee'],['Coffee']))
        self.assertFalse(r['comparison']['leader_changed'])

    def test_tied_leaders(self):
        df=load_csv(b'city,status,points\nA,y,5\nB,y,5\nA,n,2\n')
        b=spec(group='city',metric='points')
        c=spec([{'field':'status','operator':'eq','value':'y'}],group='city',metric='points')
        r=execute_comparison(df,b,c)
        self.assertEqual(r['comparison']['baseline_leaders'],['A'])
        self.assertEqual(set(r['comparison']['challenged_leaders']),{'A','B'})

    def test_group_disappears_and_zero_is_distinct(self):
        df=load_csv(b'item,status,amount\nA,done,0\nB,notdone,4\n')
        c=spec([{'field':'status','operator':'eq','value':'done'}],group='item',metric='amount')
        r=execute_comparison(df,spec(group='item',metric='amount'),c)
        rows={row['group_value']:row for row in r['comparison']['all_results']}
        self.assertEqual(rows['A']['challenged_value'],0)
        self.assertTrue(rows['A']['challenged_present'])
        self.assertFalse(rows['B']['challenged_present'])
        self.assertIsNone(rows['B']['challenged_value'])
        self.assertIsNone(rows['B']['difference_challenged_minus_baseline'])

    def test_missing_group_and_all_missing_measure(self):
        df=load_csv(b'item,status,amount\n,done,5\nA,done,\nA,no,\nB,done,3\n')
        b=spec(group='item',metric='amount')
        c=spec([{'field':'status','operator':'eq','value':'done'}],group='item',metric='amount')
        r=execute_comparison(df,b,c)
        rows={row['group_value']:row for row in r['comparison']['all_results']}
        self.assertIn(None,rows)
        self.assertEqual(rows[None]['baseline_value'],5)
        self.assertIsNone(rows['A']['baseline_value'])
        self.assertIsNone(rows['A']['challenged_value'])
        self.assertTrue(rows['A']['challenged_present'])
        self.assertIsNone(rows['A']['difference_challenged_minus_baseline'])
        self.assertEqual(r['accounting']['baseline']['operation_exclusions']['missing_metric_excluded_from_values'],2)

    def test_empty_challenged_selection_fails_controlled(self):
        self.check_error(self.baseline,spec([{'field':'status','operator':'eq','value':'not-present'}]),'no rows')

    def test_malformed_specs(self):
        for a,b in [({'tool':[],'arguments':{},'filters':[]},self.challenge),
                    (self.baseline,{**self.challenge,'filters':[{'field':'status','operator':[],'value':'completed'}]}),
                    (self.baseline,{**self.challenge,'filters':None}),
                    (self.baseline,{**self.challenge,'filters':[{'field':'zzz','operator':'eq','value':'X'}]})]:
            with self.subTest(b=b):
                with self.assertRaises(AnalysisError):
                    execute_comparison(self.df,a,b)

    def test_only_grouped_supported(self):
        bad={'tool':'time_trend','arguments':{'date_column':'date','metric':'revenue'},'filters':[]}
        self.check_error(bad,self.challenge,'grouped_summary')

    def test_change_multiple_filters_rejected(self):
        conditions=[COMPLETE,{'field':'category','operator':'eq','value':'Coffee'}]
        self.check_error(self.baseline,spec(conditions),'exactly one')
        self.check_error(self.baseline,self.baseline,'exactly one')
        # One replacement of one condition with two conditions is not allowed.
        self.check_error(self.challenge,spec([{'field':'status','operator':'eq','value':'cancelled'},
                                         {'field':'category','operator':'eq','value':'Coffee'}]),'exactly one')

    def test_arguments_must_remain_identical(self):
        self.check_error(self.baseline,spec([COMPLETE],operation='count_rows'),'preserve')
        self.check_error(self.baseline,spec([COMPLETE],group='status'),'preserve')
        self.check_error(self.baseline,spec([COMPLETE],metric='count'),'preserve')

    def test_remove_and_replace(self):
        b=spec([COMPLETE])
        r=execute_comparison(self.df,b,self.baseline)
        self.assertEqual(r['changed_condition']['kind'],'removed')
        self.assertEqual(r['comparison']['challenged_leaders'],['Coffee'])
        c=spec([{'field':'status','operator':'eq','value':'cancelled'}])
        r=execute_comparison(self.df,b,c)
        self.assertEqual(r['changed_condition']['kind'],'replaced')
        self.assertEqual(r['accounting']['challenged']['selected_rows'],1)
        self.assertEqual(r['comparison']['challenged_leaders'],['Coffee'])

    def test_reordering_filters_is_not_change(self):
        first=[COMPLETE,{'field':'category','operator':'ne','value':'Odd'}]
        self.check_error(spec(first),spec(list(reversed(first))),'exactly one')

    def test_overlapping_filters_record_sequential_counts(self):
        b=spec([{'field':'status','operator':'ne','value':'notknown'}])
        c=spec([{'field':'status','operator':'ne','value':'notknown'},COMPLETE])
        r=execute_comparison(self.df,b,c)
        self.assertEqual(r['accounting']['challenged']['excluded_by_filters'],1)
        self.assertEqual([x['newly_excluded'] for x in r['accounting']['challenged']['filters_sequential']],[0,1])

    def test_large_exact_integer_sums_and_differences(self):
        records=b'g,status,amount\n'+(b'A,done,999999999999999\n'*10000)+b'A,cancelled,999999999999999\n'
        df=load_csv(records)
        b=spec(group='g',metric='amount')
        c=spec([{'field':'status','operator':'eq','value':'done'}],group='g',metric='amount')
        r=execute_comparison(df,b,c)
        row=r['comparison']['all_results'][0]
        self.assertEqual(row['baseline_value'],10001*999999999999999)
        self.assertEqual(row['challenged_value'],9999999999999990000)
        self.assertEqual(row['difference_challenged_minus_baseline'],-999999999999999)
        self.assertIs(type(row['challenged_value']),int)
        self.assertIs(type(json.loads(json.dumps(r))['comparison']['all_results'][0]['challenged_value']),int)

    def test_full_groups_match_by_values_not_order(self):
        # B wins baseline, A wins challenged; their relative row sorting reverses.
        df=load_csv(b'k,flag,amount\nA,y,8\nB,y,3\nB,n,50\n')
        b=spec(group='k',metric='amount')
        c=spec([{'field':'flag','operator':'eq','value':'y'}],group='k',metric='amount')
        r=execute_comparison(df,b,c)
        rows={x['group_value']:x for x in r['comparison']['all_results']}
        self.assertEqual((rows['A']['baseline_value'],rows['A']['challenged_value']),(8,8))
        self.assertEqual((rows['B']['baseline_value'],rows['B']['challenged_value']),(53,3))
        self.assertEqual((r['comparison']['baseline_leaders'],r['comparison']['challenged_leaders']),(['B'],['A']))

    def test_beyond_display_cap(self):
        raw='group,flag,amount\n'+'\n'.join(f'G{i:03},yes,{i+1}' for i in range(250))+'\n'
        df=load_csv(raw.encode())
        b=spec(group='group',metric='amount',limit=1)
        c=spec([{'field':'flag','operator':'eq','value':'yes'}],group='group',metric='amount',limit=1)
        r=execute_comparison(df,b,c)
        self.assertEqual(r['comparison']['display']['total_groups'],250)
        self.assertTrue(r['comparison']['display']['truncated'])
        self.assertEqual(len(r['comparison']['displayed_results']),1)
        self.assertEqual(len(r['comparison']['all_results']),250)
        self.assertEqual(r['comparison']['baseline_leaders'],['G249'])
        self.assertEqual(r['baseline']['evidence']['display']['returned_rows'],1)
        self.assertEqual(r['baseline']['evidence']['display']['total_result_rows'],250)

    def test_different_dataset_schema_and_count(self):
        df=load_csv(b'branch,tier,visits\nMain,vip,2\nOther,standard,1\nOther,vip,3\n')
        b=spec(group='branch',operation='count_rows')
        c=spec([{'field':'tier','operator':'eq','value':'vip'}],group='branch',operation='count_rows')
        r=execute_comparison(df,b,c)
        rows={x['group_value']:x for x in r['comparison']['all_results']}
        self.assertEqual((rows['Main']['baseline_value'],rows['Main']['challenged_value']),(1,1))
        self.assertEqual((rows['Other']['baseline_value'],rows['Other']['challenged_value']),(2,1))
        self.assertEqual(set(r['comparison']['challenged_leaders']),{'Main','Other'})

    def test_fingerprint_guard_and_input_unchanged(self):
        before=self.df.copy(deep=True)
        attrs=copy.deepcopy(self.df.attrs)
        with self.assertRaisesRegex(AnalysisError,'Dataset changed'):
            execute_comparison(self.df,self.baseline,self.challenge,expected_fingerprint='0'*64)
        r=execute_comparison(self.df,self.baseline,self.challenge)
        self.assertEqual(r['baseline']['evidence']['dataset_fingerprint_sha256'],r['challenged']['evidence']['dataset_fingerprint_sha256'])
        pd.testing.assert_frame_equal(self.df,before)
        self.assertEqual(self.df.attrs,attrs)

if __name__=='__main__': unittest.main()
