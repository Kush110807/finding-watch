import unittest
import json
from unittest.mock import patch
import pandas as pd
from engine import *

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.df=load_csv(b'date,category,revenue,units\n2026-01-01,A,10,1\n2026-01-02,A,20,2\n2026-02-01,B,30,3\n2026-02-02,B,,4\n')
    def test_inspection(self):
        r=inspect_dataset(self.df)
        self.assertEqual(r['metadata']['total_rows'],4)
        self.assertEqual(r['rows'][2]['missing'],1)
    def test_group(self):
        r=grouped_summary(self.df,'category','revenue','mean')
        self.assertEqual([(x['group_value'],x['value']) for x in r['rows']],[('B',30),('A',15)])
        self.assertEqual(r['rows'][0]['non_missing_metric_count'],1)
    def test_missing_groups_and_values(self):
        d=load_csv(b'g,n\nA,\n,2\nA,\n')
        r=grouped_summary(d,'g','n')
        self.assertIsNone(r['rows'][1]['value'])
        self.assertIsNone(r['rows'][0]['group_value'])
    def test_count(self):
        self.assertEqual([x['value'] for x in grouped_summary(self.df,'category',operation='count_rows')['rows']],[2,2])
    def test_filter(self):
        r=filter_rows(self.df,'revenue','ge','20',limit=1)
        self.assertEqual(r['metadata']['matched_rows'],2)
        self.assertTrue(r['metadata']['truncated'])
        self.assertEqual(r['rows'][0]['revenue'],20)
    def test_ne_excludes_missing(self):
        self.assertEqual(filter_rows(self.df,'revenue','ne','10')['metadata']['matched_rows'],2)
    def test_literal_contains(self):
        d=load_csv(b'x\na.b\naxb\n')
        self.assertEqual(filter_rows(d,'x','contains','.')['metadata']['matched_rows'],1)
    def test_missing_filter(self):
        self.assertEqual(filter_rows(self.df,'revenue','is_missing')['metadata']['matched_rows'],1)
    def test_monthly(self):
        r=time_trend(self.df,'date','revenue')
        self.assertEqual([x['value'] for x in r['rows']],[30,30])
    def test_week_boundary(self):
        d=load_csv(b'd,n\n2026-01-04,1\n2026-01-05,2\n')
        self.assertEqual([r['period_start'] for r in time_trend(d,'d','n','week')['rows']],['2025-12-29','2026-01-05'])
    def test_explicit_date_order(self):
        d=load_csv(b'd,n\n01/02/2026,4\n')
        self.assertEqual(time_trend(d,'d','n',date_format='%d/%m/%Y')['rows'][0]['period_start'],'2026-02-01')
    def test_invalid_date(self):
        d=load_csv(b'd,n\n2026-02-30,1\n')
        with self.assertRaises(AnalysisError): time_trend(d,'d','n')
    def test_missing_date(self):
        d=load_csv(b'd,n\n,99\n2026-01-01,1\n')
        r=time_trend(d,'d','n')
        self.assertEqual(r['metadata']['excluded_missing_dates'],1)
        self.assertEqual(r['rows'][0]['value'],1)
    def test_correlation(self):
        r=correlation(self.df,'revenue','units')
        self.assertAlmostEqual(r['rows'][0]['pearson_r'],1)
        self.assertEqual(r['metadata']['complete_pairs'],3)
    def test_negative_correlation(self):
        d=load_csv(b'x,y\n1,9\n2,7\n3,5\n4,3\n')
        self.assertAlmostEqual(correlation(d,'x','y')['rows'][0]['pearson_r'],-1)
    def test_constant_correlation(self):
        d=load_csv(b'x,y\n1,2\n1,3\n1,4\n')
        with self.assertRaises(AnalysisError): correlation(d,'x','y')
    def test_insufficient_pairs(self):
        with self.assertRaises(AnalysisError): correlation(self.df.head(2),'revenue','units')
    def test_csv_rejections(self):
        for raw in [b'',b'a,a\n1,2\n',b'a, a\n1,2\n',b'a,\n1,2\n',b'a,b\n1\n',b'a,b\n1,2,3\n',b'a,b\n',b'x\n\xff',b'x\n\x00',b'a,b\n"unterminated,2']:
            with self.subTest(raw=raw), self.assertRaises(AnalysisError): load_csv(raw)
    def test_limits(self):
        with patch('engine.MAX_BYTES',2),self.assertRaises(AnalysisError): load_csv(b'x\n1\n')
        with patch('engine.MAX_ROWS',1),self.assertRaises(AnalysisError): load_csv(b'x\n1\n2\n')
        with patch('engine.MAX_COLUMNS',1),self.assertRaises(AnalysisError): load_csv(b'x,y\n1,2\n')
    def test_bom_quotes_labels(self):
        d=load_csv('\ufefflabel,n\n"a,b",1\nNA,2\nNULL,3\n'.encode())
        self.assertEqual(d.label.tolist(),['a,b','NA','NULL'])
    def test_invalid_arguments(self):
        for name,args in [('unknown',{}),('filter_rows',{'field':'nope','operator':'eq','value':1}),('correlation',{'x':'units','y':'units'}),('filter_rows',{'field':'units','operator':'gt','value':'bad'})]:
            with self.subTest(name=name), self.assertRaises(AnalysisError): run_tool(self.df,name,args)
    def test_infinity(self):
        d=load_csv(b'g,n\nA,inf\n')
        with self.assertRaises(AnalysisError): grouped_summary(d,'g','n')
    def test_readonly_and_json(self):
        before=self.df.copy(deep=True)
        for name,args in [('inspect_dataset',{}),('grouped_summary',{'group':'category','metric':'revenue'}),('time_trend',{'date_column':'date','metric':'revenue'}),('correlation',{'x':'revenue','y':'units'}),('filter_rows',{'field':'units','operator':'gt','value':1})]:
            out=run_tool(self.df,name,args)
            json.dumps(out,allow_nan=False)
            pd.testing.assert_frame_equal(before,self.df)

if __name__=='__main__': unittest.main()
