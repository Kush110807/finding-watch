"""Offline presentation correctness; not Streamlit or live Gemini verification."""
import unittest
import pandas as pd
from engine import load_csv, run_tool
from comparisons import execute_comparison
from presentation import (summary, comparison_summary,comparison_table,metric_choices,
                          group_candidates,missing_product_context,chart_safe,filter_description)

GOLDEN=b'category,status,revenue\nCoffee,completed,120\nCoffee,completed,90\nCoffee,cancelled,300\nSnacks,completed,180\nSnacks,completed,100\n'

class PresentationTests(unittest.TestCase):
    def setUp(self): self.df=load_csv(GOLDEN)
    def test_golden_conclusion_and_count_definitions(self):
        result=run_tool(self.df,'grouped_summary',{'group':'category','metric':'revenue','operation':'sum'})
        self.assertIn('Coffee',summary(result)); self.assertIn('510',summary(result))
        count=run_tool(self.df,'grouped_summary',{'group':'category','operation':'count_rows'})
        self.assertIn('record count (rows)',summary(count).lower())
        self.assertNotIn('orders',summary(count).lower())
    def test_tied_leaders(self):
        df=load_csv(b'g,amount\nA,10\nB,10\nC,2\n')
        result=run_tool(df,'grouped_summary',{'group':'g','operation':'sum','metric':'amount'})
        self.assertIn('tie',summary(result).lower()); self.assertIn('A',summary(result)); self.assertIn('B',summary(result))
    def test_truncated_disallows_global_rank(self):
        out=run_tool(self.df,'grouped_summary',{'group':'category','operation':'sum','metric':'revenue','display_limit':1})
        self.assertIn('cannot be confirmed',summary(out))
    def test_missing_value_result(self):
        df=pd.DataFrame({'g':['A','A'],'amount':pd.Series([pd.NA,pd.NA],dtype='Int64')})
        out=run_tool(df,'grouped_summary',{'group':'g','operation':'sum','metric':'amount'})
        self.assertIn('No numeric group result',summary(out))
    def test_group_absent_vs_zero_vs_missing(self):
        df=load_csv(b'g,keep,value\nA,yes,1\nA,no,4\nB,yes,0\nC,no,\n')
        base={'tool':'grouped_summary','arguments':{'group':'g','metric':'value','operation':'sum'},'filters':[]}
        chall={**base,'filters':[{'field':'keep','operator':'eq','value':'yes'}]}
        out=execute_comparison(df,base,chall)
        rows={r['Group']:r for r in comparison_table(out)}
        self.assertEqual(rows['B']['Challenged'],'0')
        self.assertEqual(rows['C']['Challenged'],'Absent group')
        self.assertEqual(rows['C']['All baseline'],'No numeric value')
    def test_all_golden_differences(self):
        base={'tool':'grouped_summary','arguments':{'group':'category','metric':'revenue','operation':'sum'},'filters':[]}
        chall={**base,'filters':[{'field':'status','operator':'eq','value':'completed'}]}
        result=execute_comparison(self.df,base,chall)
        self.assertIn('Coffee',comparison_summary(result));self.assertIn('Snacks',comparison_summary(result))
        rows={r['Group']:r for r in comparison_table(result)}
        self.assertEqual(rows['Coffee']['Difference'],'-300'); self.assertEqual(rows['Snacks']['Difference'],'0')
        self.assertEqual(result['accounting']['baseline']['selected_rows'],5)
        self.assertEqual(result['accounting']['challenged']['selected_rows'],4)
    def test_unfamiliar_schema_choices(self):
        df=load_csv(b'City,QuantitySold,SalesTotal\nDelhi,2,25\nMumbai,4,50\n')
        choices=metric_choices(list(df),['QuantitySold','SalesTotal'])
        self.assertIn('Record count (rows)',choices)
        self.assertIn('Total of “QuantitySold”',choices)
        self.assertIn('Total of “SalesTotal”',choices)
        self.assertEqual(choices['Total of “SalesTotal”'],{'operation':'sum','metric':'SalesTotal'})
        self.assertEqual(group_candidates(list(df),'best-selling product')[0],'City')
        self.assertTrue(missing_product_context(list(df),'best-selling product'))
    def test_filters_preserve_exact_values(self):
        self.assertIn("'0012'",filter_description({'field':'code','operator':'eq','value':'0012'}))
    def test_large_integer_chart_disabled(self):
        self.assertFalse(chart_safe([{'value':9999999999999990000}]))
        self.assertTrue(chart_safe([{'value':210},{'value':280}]))
    def test_model_tool_relevance_not_assumed(self):
        result=run_tool(self.df,'inspect_dataset',{})
        self.assertNotIn('best',summary(result).lower())

if __name__=='__main__': unittest.main()
