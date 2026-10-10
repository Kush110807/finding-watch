"""Independent Stage 3 UI-spec and evidence regressions (no Streamlit dependency)."""
import copy
import unittest
from engine import load_csv, AnalysisError
from comparisons import prepare_comparison, execute_comparison
from challenge_logic import (identity,changed_filters,column_operators,categorical_values,
                             parse_numeric,parse_contains_text,conclusion,comparison_display_rows,definition_line,unchanged_line)

GOLDEN=b'category,status,revenue\nCoffee,completed,120\nCoffee,completed,90\nCoffee,cancelled,300\nSnacks,completed,180\nSnacks,completed,100\n'

def spec(filters=None,group='category',metric='revenue',limit=100):
    return {'tool':'grouped_summary','arguments':{'group':group,'metric':metric,'operation':'sum'},
            'filters':filters or [],'display_limit':limit}

class ChallengeStateTests(unittest.TestCase):
    def setUp(self):
        self.df=load_csv(GOLDEN)

    def test_open_editor_is_not_plan_and_has_no_numeric_result(self):
        # The pure input contract contains no call to prepare/execute; the only
        # route to either is the explicitly submitted Review/Confirm in the UI.
        original=spec()
        condition={'field':'status','operator':'eq','value':'completed'}
        changed=changed_filters(original['filters'],'Add condition',condition=condition)
        self.assertEqual(original['filters'],[])
        self.assertEqual(changed,[condition])
        self.assertNotIn('result',original)

    def test_add_golden_and_exact_definition(self):
        condition={'field':'status','operator':'eq','value':'completed'}
        challenged=spec(changed_filters([],'Add condition',condition=condition))
        p=prepare_comparison(self.df,spec(),challenged)
        self.assertNotIn('comparison',p)
        self.assertEqual(p['changed_condition']['kind'],'added')
        self.assertEqual(definition_line(challenged),'“status” equals \'completed\'')
        r=execute_comparison(self.df,spec(),challenged)
        vals={x['group_value']:(x['baseline_value'],x['challenged_value'],x['difference_challenged_minus_baseline'])
              for x in r['comparison']['all_results']}
        self.assertEqual(vals,{'Coffee':(510,210,-300),'Snacks':(280,280,0)})
        self.assertEqual(conclusion(r),'The leader changes from Coffee to Snacks.')

    def test_demo_region_golden_same_leader(self):
        from pathlib import Path
        df=load_csv((Path(__file__).resolve().parents[1]/'data/demo_sales.csv').read_bytes())
        r=execute_comparison(df,spec(group='category'),spec([{'field':'region','operator':'eq','value':'North'}],group='category'))
        vals={v['group_value']:(v['baseline_value'],v['challenged_value']) for v in r['comparison']['all_results']}
        self.assertEqual(vals,{'Coffee':(3000,1200),'Snacks':(1400,800)})
        self.assertEqual(conclusion(r),'Coffee remains the leader.')
        self.assertEqual((r['accounting']['baseline']['selected_rows'],r['accounting']['challenged']['selected_rows']),(4,2))

    def test_replace_and_remove_preserve_all_other_conditions(self):
        a={'field':'status','operator':'eq','value':'completed'}
        b={'field':'category','operator':'ne','value':'Ghost'}
        changed=changed_filters([a,b],'Replace condition',index=0,condition={'field':'status','operator':'ne','value':'cancelled'})
        self.assertEqual(changed[1],b)
        self.assertEqual(changed_filters([a,b],'Remove condition',index=1),[a])
        self.assertEqual(changed_filters([a,b],'Add condition',condition={'field':'revenue','operator':'gt','value':1}),
                         [a,b,{'field':'revenue','operator':'gt','value':1}])
        with self.assertRaises(AnalysisError): changed_filters([a],'Remove condition',index=None)
        with self.assertRaises(AnalysisError): changed_filters([a],'Replace condition',index=0)
        with self.assertRaises(AnalysisError): changed_filters([a],'Add condition')

    def test_incomplete_or_unsupported_not_reviewable(self):
        for mode in ('',None,'Remove condition','Replace condition'):
            with self.subTest(mode=mode):
                with self.assertRaises(AnalysisError):changed_filters([] ,mode,index=None)
        with self.assertRaises(AnalysisError):changed_filters([{'field':'status','operator':'eq','value':'x'}]*8,'Add condition',condition={'field':'status','operator':'eq','value':'y'})

    def test_type_safe_value_choices_and_operators(self):
        df=load_csv(b'group,id,score\nA,0007,13\nB,0012,\nA,,7\n')
        self.assertEqual(categorical_values(df,'id'),['0007','0012'])
        self.assertIn('contains',column_operators(df,'id'))
        self.assertNotIn('gt',column_operators(df,'id'))
        self.assertIn('ge',column_operators(df,'score'))
        self.assertNotIn('contains',column_operators(df,'score'))
        self.assertEqual(parse_numeric('13'),13)
        self.assertEqual(parse_numeric('-2.5'),-2.5)
        for bad in ('','abc','NaN','inf','1e309','9007199254740993'):
            with self.subTest(bad=bad):
                with self.assertRaises(AnalysisError):parse_numeric(bad)

    def test_empty_string_and_missing_are_distinct(self):
        import pandas as pd
        df=pd.DataFrame({'type':['',None,'North'],'amount':[1,2,3]})
        self.assertEqual(categorical_values(df,'type'),['','North'])
        self.assertEqual(changed_filters([],'Add condition',condition={'field':'type','operator':'eq','value':''})[0]['value'],'')
        self.assertEqual(changed_filters([],'Add condition',condition={'field':'type','operator':'is_missing'})[0]['operator'],'is_missing')

    def test_binding_changes_with_dataset_question_occurrence_trace(self):
        a={'dataset':'a','question':'q','occurrence':1,'trace_index':1}
        for field,val in [('dataset','b'),('question','new'),('occurrence',2),('trace_index',2)]:
            b={**a,field:val}
            self.assertNotEqual(identity(a),identity(b))
        self.assertEqual(identity(a),identity(copy.deepcopy(a)))

    def test_absent_zero_and_missing_values_stay_distinct(self):
        df=load_csv(b'g,region,amount\nA,North,0\nB,South,5\nC,North,\n')
        r=execute_comparison(df,spec(group='g',metric='amount'),spec([{'field':'region','operator':'eq','value':'North'}],group='g',metric='amount'))
        rows={x['G']:x for x in comparison_display_rows(r)}
        self.assertEqual(rows['A']['Alternative'],'0')
        self.assertEqual(rows['B']['Alternative'],'Absent group')
        self.assertEqual(rows['C']['Alternative'],'No numeric value')
        self.assertEqual(rows['B']['Difference'],'Not comparable')

    def test_exact_large_integers_and_truncation(self):
        df=load_csv(b'g,region,amount\n'+b'A,North,999999999999999\n'*11+b'B,South,\n')
        r=execute_comparison(df,spec(group='g',metric='amount',limit=1),spec([{'field':'region','operator':'eq','value':'North'}],group='g',metric='amount',limit=1))
        self.assertEqual(r['comparison']['display']['total_groups'],2)
        self.assertTrue(r['comparison']['display']['truncated'])
        self.assertEqual(comparison_display_rows(r)[0]['Original'],'10,999,999,999,999,989')
        self.assertEqual(conclusion(r),'A remains the leader.')

    def test_presentation_does_not_modify_downloadable_json(self):
        import json
        df=load_csv(b'g,region,amount\nA,North,5\nB,South,0\nC,North,\n')
        result=execute_comparison(df,spec(group='g',metric='amount'),
            spec([{'field':'region','operator':'eq','value':'North'}],group='g',metric='amount'))
        baseline=json.dumps(result,sort_keys=True,ensure_ascii=False,allow_nan=False)
        self.assertEqual(len(comparison_display_rows(result)),3)
        self.assertTrue(conclusion(result))
        self.assertEqual(json.dumps(result,sort_keys=True,ensure_ascii=False,allow_nan=False),baseline)

    def test_collision_safe_comparison_headings_keep_exact_groups_and_json(self):
        import json
        # Group columns named original/alternative/difference previously
        # overwrote the group values with the corresponding numeric heading.
        for group in ('original','alternative','difference'):
            with self.subTest(group=group):
                raw=(f'{group},region,amount\n'.encode()
                     +b'Coffee,North East,999999999999999\n'*11
                     +b'Snacks,South,5\nZero,North West,0\nMissing,North West,\n')
                df=load_csv(raw)
                base=spec(group=group,metric='amount')
                alternative=spec([{'field':'region','operator':'contains','value':'North'}],
                                 group=group,metric='amount')
                result=execute_comparison(df,base,alternative)
                original=json.dumps(result,sort_keys=True,ensure_ascii=False,allow_nan=False)
                rows=comparison_display_rows(result)
                self.assertEqual(len(rows),4)
                headings=list(rows[0])
                self.assertEqual(len(headings),len(set(headings)))
                self.assertEqual(headings[0],group.capitalize()+' (group)')
                self.assertEqual(headings[1:],['Original','Alternative','Difference'])
                by_group={row[headings[0]]:row for row in rows}
                self.assertEqual(set(by_group),{'Coffee','Snacks','Zero','Missing'})
                self.assertEqual(by_group['Coffee']['Original'],'10,999,999,999,999,989')
                self.assertEqual(by_group['Coffee']['Alternative'],'10,999,999,999,999,989')
                self.assertEqual(by_group['Coffee']['Difference'],'0')
                self.assertEqual(by_group['Snacks']['Alternative'],'Absent group')
                self.assertEqual(by_group['Zero']['Alternative'],'0')
                self.assertEqual(by_group['Missing']['Alternative'],'No numeric value')
                self.assertEqual(json.dumps(result,sort_keys=True,ensure_ascii=False,allow_nan=False),original)

    def test_contains_text_requires_explicit_substring_and_matches_full_rows(self):
        df=load_csv(b'g,region,amount\nA,North East,5\nA,North West,7\nB,South,4\n')
        base=spec(group='g',metric='amount')
        for invalid in ('', ' ', '\t', None, 123, 'x'*257):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(AnalysisError):
                    parse_contains_text(invalid)
        self.assertEqual(parse_contains_text('North'),'North')
        self.assertEqual(parse_contains_text(' North '),' North ')
        condition={'field':'region','operator':'contains','value':parse_contains_text('North')}
        alt=spec(changed_filters([], 'Add condition',condition=condition),group='g',metric='amount')
        plan=prepare_comparison(df,base,alt)
        self.assertEqual(plan['changed_condition']['kind'],'added')
        result=execute_comparison(df,base,alt)
        self.assertEqual(result['accounting']['challenged']['selected_rows'],2)
        a=next(row for row in result['comparison']['all_results'] if row['group_value']=='A')
        self.assertEqual((a['baseline_value'],a['challenged_value']),(12,12))
        # Whole-value equality remains distinct: neither matching region equals North.
        only_exact=spec([{'field':'region','operator':'eq','value':'North'}],group='g',metric='amount')
        with self.assertRaisesRegex(AnalysisError,'[Nn]o rows'):
            execute_comparison(df,base,only_exact)

    def test_tie_and_empty_selection(self):
        df=load_csv(b'g,region,amount\nA,North,5\nB,North,5\nA,South,1\n')
        r=execute_comparison(df,spec(group='g',metric='amount'),spec([{'field':'region','operator':'eq','value':'North'}],group='g',metric='amount'))
        self.assertEqual(conclusion(r),'The alternative has a tie: A, B.')
        with self.assertRaisesRegex(AnalysisError,'[Nn]o rows'):
            execute_comparison(df,spec(group='g',metric='amount'),spec([{'field':'region','operator':'eq','value':'Nowhere'}],group='g',metric='amount'))

if __name__=='__main__': unittest.main()
