"""Reviewer regressions: pure offline exact evidence and approval-state checks.

Runtime Streamlit assertions live in test_app.py and require the real package.
"""
import json
import unittest
import pandas as pd
from engine import run_tool, load_csv
from comparisons import prepare_comparison, execute_comparison
from presentation import display_rows, confirmed_comparison_matches, comparison_table

class RepairTests(unittest.TestCase):
    def setUp(self):
        self.df=load_csv(b'g,amount\n'+b'A,999999999999999\n'*11+b'B,\n')
        self.base={'tool':'grouped_summary',
            'arguments':{'group':'g','metric':'amount','operation':'sum'},'filters':[]}

    def test_exact_eleven_row_integer_and_missing_before_pandas_table(self):
        out=run_tool(self.df,'grouped_summary',self.base['arguments'])
        original={r['group_value']:r['value'] for r in out['rows']}
        self.assertEqual(original,{'A':10999999999999989,'B':None})
        display=display_rows(out['rows'])
        self.assertEqual(display[0]['value'],'10,999,999,999,999,989')
        self.assertEqual(display[1]['value'],'No numeric value')
        table=pd.DataFrame(display,dtype=str)
        self.assertEqual(table.iloc[0]['value'],'10,999,999,999,999,989')
        self.assertEqual(table.iloc[1]['value'],'No numeric value')
        self.assertIs(type(original['A']),int)
        self.assertEqual(json.loads(json.dumps(out))['rows'][0]['value'],10999999999999989)
        self.assertEqual(out['rows'][1]['value'],None)

    def test_comparison_table_exact_large_delta_and_missing(self):
        df=pd.DataFrame({'g':['A']*11+['B'],'amount':pd.Series([999999999999999]*11+[pd.NA],dtype='Int64'),
                         'keep':['yes']*10+['no','yes']})
        challenge={**self.base,'filters':[{'field':'keep','operator':'eq','value':'yes'}]}
        result=execute_comparison(df,self.base,challenge)
        row={r['Group']:r for r in comparison_table(result)}
        self.assertEqual(row['A']['All baseline'],'10,999,999,999,999,989')
        self.assertEqual(row['A']['Challenged'],'9,999,999,999,999,990')
        self.assertEqual(row['A']['Difference'],'-999,999,999,999,999')
        self.assertEqual(row['B']['All baseline'],'No numeric value')
        self.assertEqual(row['B']['Challenged'],'No numeric value')

    def test_confirmation_requires_exact_plan_and_exact_baseline_binding(self):
        df=pd.DataFrame({'g':['A','B'], 'amount':[2,1],'keep':['yes','no']})
        base=self.base
        challenge={**base,'filters':[{'field':'keep','operator':'eq','value':'yes'}]}
        plan=prepare_comparison(df,base,challenge)
        result=execute_comparison(df,base,challenge)
        binding={'kind':'clarified','dataset':'v1','question':'Which leads?',
                 'chosen':base['arguments']}
        stored={'plan':plan,'baseline_binding':binding,'result':result}
        self.assertTrue(confirmed_comparison_matches(stored,plan,binding))
        edited=prepare_comparison(df,base,{**base,'filters':[{'field':'keep','operator':'eq','value':'no'}]})
        self.assertFalse(confirmed_comparison_matches(stored,edited,binding))
        self.assertFalse(confirmed_comparison_matches(stored,plan,{**binding,'question':'Unrelated'}))
        self.assertFalse(confirmed_comparison_matches(None,plan,binding))
        self.assertFalse(confirmed_comparison_matches({**stored,'result':{'status':'error'}},plan,binding))

    def test_column_rendering_has_no_float_coercion_in_mixed_null_types(self):
        rows=[{'code':'0012','value':10999999999999989,'other':None},
              {'code':'0033','value':None,'other':'present'}]
        before=json.dumps(rows)
        result=display_rows(rows)
        self.assertEqual(result[0]['code'],'0012')
        self.assertEqual(result[0]['value'],'10,999,999,999,999,989')
        self.assertEqual(result[1]['value'],'No numeric value')
        self.assertEqual(result[0]['other'],'Missing')
        self.assertEqual(json.dumps(rows),before)

if __name__=='__main__': unittest.main()
