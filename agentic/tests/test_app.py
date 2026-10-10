"""Streamlit AppTest contracts. Execute only with Streamlit and SDK installed.

These are UI tests (not live model verification). AI requests are patched and use
an evidence-bearing response rather than the obsolete Phase 3 `answered` status.
"""
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

from engine import load_csv, run_tool


def _launch():
    return AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=20).run()


def _run_button(at):
    return next(b for b in at.button if b.label=='Run analysis').click().run()


class AppTests(unittest.TestCase):
    def test_all_five_manual_tools(self):
        for choice in ['Inspect dataset','Filter rows','Summarise groups','Analyse time trends','Measure correlation']:
            with self.subTest(tool=choice):
                at=_launch()
                at.selectbox[0].select(choice).run()
                if choice=='Filter rows':
                    at.selectbox[1].select('category').run()
                    at.text_input[0].input('Coffee').run()
                if choice=='Summarise groups':
                    at.selectbox[1].select('category').run()
                _run_button(at)
                self.assertFalse(at.exception)
                self.assertFalse(at.error)
                output=at.session_state['last_manual']['output']
                self.assertEqual(output['evidence']['calculation_status'],'completed')
                self.assertEqual(output['evidence']['executed_spec']['tool'],output['tool'])
                self.assertEqual(output['evidence']['accounting']['input_rows'],4)
                self.assertTrue(at.dataframe)  # both source preview and calculation result

    def test_manual_filter_evidence_and_pending_controls(self):
        at=_launch()
        at.selectbox[0].select('Summarise groups').run()
        at.selectbox[1].select('category').run()
        # 0 is the number of optional AND filters for grouped/time/correlation.
        at.number_input[0].set_value(1).run()
        at.selectbox[4].select('category').run()
        at.text_input[0].input('Coffee').run()
        _run_button(at)
        self.assertFalse(at.exception)
        out=at.session_state['last_manual']['output']
        self.assertEqual(out['evidence']['executed_spec']['filters'],[
            {'field':'category','operator':'eq','value':'Coffee'}])
        self.assertEqual(out['evidence']['accounting']['selected_rows'],2)
        self.assertEqual(out['rows'][0]['value'],3000)
        # Editing a filter does not overwrite the submitted specification.
        at.text_input[0].input('Snacks').run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['last_manual']['output']['rows'][0]['value'],3000)
        self.assertTrue(any('previous result is hidden' in str(c.value).lower()
                            for c in at.warning))

    def test_upload_empty_state(self):
        at=_launch()
        at.radio[0].set_value('Upload CSV').run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.dataframe),0)

    def test_error_feedback(self):
        at=_launch()
        at.selectbox[0].select('Filter rows').run()
        at.selectbox[1].select('revenue').run()
        at.text_input[0].input('invalid number').run()
        _run_button(at)
        self.assertFalse(at.exception)
        self.assertEqual(len(at.error),1)


class ChatAppTests(unittest.TestCase):
    def _submit(self,at):
        return next(b for b in at.button if b.label=='Ask Gemini').click().run()

    def test_submitted_question_binding_and_current_evidence_contract(self):
        df=load_csv((Path(__file__).resolve().parents[1] / 'data' / 'demo_sales.csv').read_bytes())
        tool_output=run_tool(df,'grouped_summary',{'group':'category','metric':'revenue','operation':'sum'})
        sample={'status':'evidence_available','answer':'Coffee leads with 3000.',
                'trace':[{'tool':'grouped_summary','arguments':{'group':'category','metric':'revenue',
                   'operation':'sum'},'result':tool_output}], 'calculation_verified':True,
                'explanation_verified':False,'question':'Which category leads?',
                'dataset_fingerprint_sha256':tool_output['evidence']['dataset_fingerprint_sha256']}
        with patch('agent.ask',return_value=sample) as ask:
            at=_launch()
            at.checkbox[0].check().run()
            at.text_input[0].input('Which category leads?').run()
            self._submit(at)
            self.assertFalse(at.exception)
            ask.assert_called_once()
            saved=at.session_state['last_answer']
            self.assertEqual(saved['response']['status'],'evidence_available')
            self.assertFalse(saved['response']['explanation_verified'])
            self.assertEqual(saved['submitted_question'],'Which category leads?')
            self.assertEqual(saved['response']['trace'][0]['result']['evidence']['calculation_status'],'completed')
            at.text_input[0].input('Which date is best?').run()
            self.assertFalse(at.exception)
            self.assertEqual(at.session_state['last_answer']['submitted_question'],'Which category leads?')
            self.assertTrue(any('pending' in str(w.value).lower() for w in at.warning))

    def test_missing_key_feedback(self):
        from agent import AgentError
        with patch('agent.ask',side_effect=AgentError('No API key found.')):
            at=_launch()
            at.checkbox[0].check().run()
            at.text_input[0].input('Question').run()
            self._submit(at)
            self.assertFalse(at.exception)
            self.assertIn('No API key',at.error[0].value)

class M2ChallengeAppTests(unittest.TestCase):
    """Run on Windows with real Streamlit and SDK packages (no live model calls)."""

    @staticmethod
    def widget(at, collection, label):
        return next(item for item in getattr(at,collection) if item.label==label)

    def test_manual_comparison_requires_explicit_confirmation(self):
        at=_launch()
        at.selectbox[0].select('Summarise groups').run()
        self.widget(at,'selectbox','Group by').select('category').run()
        _run_button(at)
        self.assertFalse(at.exception)
        self.assertNotIn('last_manual_comparison',at.session_state)
        self.widget(at,'selectbox','Challenged filter column').select('category').run()
        self.widget(at,'text_input','Challenged filter value').input('Coffee').run()
        self.assertFalse(at.exception)
        self.assertNotIn('last_manual_comparison',at.session_state)
        self.widget(at,'button','Run confirmed manual comparison').click().run()
        self.assertFalse(at.exception)
        result=at.session_state['last_manual_comparison']['result']
        self.assertEqual(result['status'],'completed')
        self.assertFalse(any('not calculated or approved' in str(w.value).lower() for w in at.warning))
        self.assertTrue(any('confirmed' in str(x.value).lower() for x in at.success))
        self.assertTrue(any('Challenge · confirmed' in str(x.value) for x in at.markdown))
        self.assertFalse(any('Challenge · pending' in str(x.value) for x in at.markdown))
        self.assertEqual(result['accounting']['baseline']['selected_rows'],4)
        self.assertEqual(result['accounting']['challenged']['selected_rows'],2)
        self.widget(at,'text_input','Challenged filter value').input('Snacks').run()
        self.assertFalse(at.exception)
        self.assertIn('last_manual_comparison',at.session_state)
        self.assertFalse(any('Download comparison JSON'==b.label for b in at.button))
        self.assertTrue(any('pending' in str(w.value).lower() for w in at.warning))

    def test_ai_comparison_pending_then_user_confirmed(self):
        from comparisons import prepare_comparison
        df=load_csv((Path(__file__).resolve().parents[1]/'data'/'demo_sales.csv').read_bytes())
        base={'tool':'grouped_summary','arguments':{'group':'category','metric':'revenue','operation':'sum'},'filters':[]}
        challenged={**base,'filters':[{'field':'region','operator':'eq','value':'North'}]}
        plan=prepare_comparison(df,base,challenged)
        sample={'status':'comparison_pending','answer':'Proposal pending user confirmation.',
                'pending_comparison':plan,'trace':[{'tool':'propose_grouped_comparison',
                    'arguments':{},'result':{'proposal':plan,'not_calculated':True}}],
                'calculation_verified':False,'explanation_verified':False,
                'dataset_fingerprint_sha256':plan['dataset_fingerprint_sha256']}
        with patch('agent.ask',return_value=sample):
            at=_launch()
            self.widget(at,'checkbox','Use Gemini for this question: send the question, column names/types and analysis results (which may include matching rows).').check().run()
            self.widget(at,'text_input','Question').input('What if North only?').run()
            next(b for b in at.button if b.label=='Ask Gemini').click().run()
            self.assertFalse(at.exception)
            self.assertNotIn('last_ai_comparison',at.session_state)
            self.widget(at,'button','Confirm and run proposed comparison').click().run()
            self.assertFalse(at.exception)
            result=at.session_state['last_ai_comparison']['result']
            self.assertEqual(result['accounting']['challenged']['selected_rows'],2)
            self.assertEqual(result['status'],'completed')
            self.assertFalse(any('not calculated' in str(x.value).lower() for x in at.warning))
            self.assertTrue(any('confirmed' in str(x.value).lower() for x in at.success))
            self.widget(at,'text_input','Question').input('Some other question').run()
            self.assertFalse(at.exception)
            self.assertFalse(any(b.label=='Confirm and run proposed comparison' for b in at.button))

class P1P3UiAppTests(unittest.TestCase):
    """Requires Streamlit + pinned google-genai; never makes live provider calls."""
    @staticmethod
    def field(at, collection, label):
        return next(item for item in getattr(at,collection) if item.label==label)

    @staticmethod
    def mocked_answer(status='clarification', answer='Which column and measure?', trace=None):
        return {'status':status, 'answer':answer,'trace':trace or [],
                'calculation_verified':False,'explanation_verified':False}

    def submit_question(self, at, text):
        self.field(at,'checkbox','Use Gemini for this question: send the question, column names/types and analysis results (which may include matching rows).').check().run()
        self.field(at,'text_input','Question').input(text).run()
        self.field(at,'button','Ask Gemini').click().run()
        return at

    def test_best_selling_product_clarification_keeps_original_question(self):
        with patch('agent.ask',return_value=self.mocked_answer()) as mocked:
            at=self.submit_question(_launch(),'Which is the best-selling product?')
            self.assertFalse(at.exception)
            self.assertEqual(at.session_state['last_answer']['submitted_question'],'Which is the best-selling product?')
            self.assertNotIn('last_clarified',at.session_state)
            self.assertTrue(any('no column containing' in str(w.value).lower() for w in at.warning))
            # No implicit selections and no analysis before explicitly submitting.
            self.assertIsNone(self.field(at,'radio','Clarification approach').value)
            self.field(at,'radio','Clarification approach').set_value('Choose a grouping and calculation').run()
            self.assertIsNone(self.field(at,'selectbox','Which column should be compared?').value)
            self.assertIsNone(self.field(at,'selectbox','Which calculation should define “best”?').value)
            self.field(at,'selectbox','Which column should be compared?').select('category').run()
            self.field(at,'selectbox','Which calculation should define “best”?').select('Total of “units”').run()
            self.assertNotIn('last_clarified',at.session_state)
            self.field(at,'button','Analyse with my choices').click().run()
            self.assertFalse(at.exception)
            result=at.session_state['last_clarified']['output']
            self.assertEqual(result['tool'],'grouped_summary')
            self.assertEqual(result['evidence']['executed_spec']['arguments']['metric'],'units')
            self.assertEqual(result['rows'][0]['value'],100)  # Coffee total units
            mocked.assert_called_once()
            self.field(at,'text_input','Question').input('What changed?').run()
            self.assertFalse(at.exception)
            self.assertTrue(any('pending question edits' in str(w.value).lower() for w in at.warning))

    def test_clarification_explicit_count_rows_not_orders(self):
        with patch('agent.ask',return_value=self.mocked_answer()):
            at=self.submit_question(_launch(),'Which category has the most sales?')
            self.field(at,'radio','Clarification approach').set_value('Choose a grouping and calculation').run()
            self.field(at,'selectbox','Which column should be compared?').select('category').run()
            self.field(at,'selectbox','Which calculation should define “best”?').select('Record count (rows)').run()
            self.field(at,'button','Analyse with my choices').click().run()
            out=at.session_state['last_clarified']['output']
            self.assertEqual(out['evidence']['executed_spec']['arguments']['operation'],'count_rows')
            self.assertEqual({r['group_value']:r['value'] for r in out['rows']},{'Coffee':2,'Snacks':2})

    def test_provider_status_and_unverified_narrative_are_separate(self):
        with patch('agent.ask',return_value=self.mocked_answer('error','Quota unavailable.')):
            at=self.submit_question(_launch(),'What is the top category?')
            self.assertFalse(at.exception)
            self.assertTrue(any('Quota unavailable.' in str(e.value) for e in at.error))

    def test_streamlit_result_table_uses_exact_large_integer_evidence(self):
        raw=b'g,amount\n'+b'A,999999999999999\n'*11+b'B,\n'
        df=load_csv(raw)
        output=run_tool(df,'grouped_summary',{'group':'g','metric':'amount','operation':'sum'})
        response={'status':'evidence_available','answer':'Model narration not verified',
            'trace':[{'tool':'grouped_summary','arguments':{'group':'g',
                     'metric':'amount','operation':'sum'},'result':output}],
            'calculation_verified':True,'explanation_verified':False}
        with patch('agent.ask',return_value=response):
            at=self.submit_question(_launch(),'Which group has greatest total amount?')
            self.assertFalse(at.exception)
            self.assertGreaterEqual(len(at.dataframe),2)
            rendered=at.dataframe[-1].value
            self.assertEqual(rendered.iloc[0]['value'],'10,999,999,999,999,989')
            self.assertEqual(rendered.iloc[1]['value'],'No numeric value')
            self.assertEqual(output['rows'][0]['value'],10999999999999989)
            self.assertIsNone(output['rows'][1]['value'])

    def test_contextual_clarification_preserves_question_and_does_not_execute_without_submit(self):
        first=self.mocked_answer('clarification','Which date format: DD/MM/YYYY or MM/DD/YYYY?')
        second=self.mocked_answer('clarification','Which time interval?')
        with patch('agent.ask',side_effect=[first,second]) as send:
            at=self.submit_question(_launch(),'How did sales change on 01/02/2026?')
            self.field(at,'radio','Clarification approach').set_value('Explain the missing context (dates or other details)').run()
            self.assertEqual(send.call_count,1)
            self.field(at,'text_area','Your clarification').input('Dates are DD/MM/YYYY').run()
            self.assertEqual(send.call_count,1)
            self.field(at,'button','Continue with original question and my clarification').click().run()
            self.assertFalse(at.exception)
            self.assertEqual(send.call_count,2)
            self.assertEqual(send.call_args.args[1],'How did sales change on 01/02/2026?')
            self.assertEqual(send.call_args.kwargs['clarification_context'],'Dates are DD/MM/YYYY')
            self.assertEqual(at.session_state['last_answer']['submitted_question'],
                             'How did sales change on 01/02/2026?')
            self.assertNotIn('last_clarified',at.session_state)

    def test_clarified_grouped_answer_can_be_challenged_without_manual_baseline(self):
        with patch('agent.ask',return_value=self.mocked_answer()):
            at=self.submit_question(_launch(),'Which is the best-selling product?')
            self.field(at,'radio','Clarification approach').set_value('Choose a grouping and calculation').run()
            self.field(at,'selectbox','Which column should be compared?').select('category').run()
            self.field(at,'selectbox','Which calculation should define “best”?').select('Total of “units”').run()
            self.field(at,'button','Analyse with my choices').click().run()
            self.assertNotIn('last_manual',at.session_state)
            self.field(at,'selectbox','Challenged filter column').select('region').run()
            self.field(at,'text_input','Challenged filter value').input('North').run()
            self.field(at,'button','Run confirmed clarified comparison').click().run()
            self.assertFalse(at.exception)
            entry=at.session_state['last_clarified_comparison']
            self.assertEqual(entry['baseline_binding']['kind'],'clarified')
            self.assertEqual(entry['result']['baseline_spec']['arguments']['metric'],'units')
            self.assertEqual(entry['result']['status'],'completed')
            self.assertTrue(any('Challenge · confirmed' in str(x.value) for x in at.markdown))
            self.assertFalse(any('Challenge · pending' in str(x.value) for x in at.markdown))
            self.field(at,'text_input','Challenged filter value').input('South').run()
            self.assertFalse(at.exception)
            self.assertFalse(any('Download comparison JSON'==b.label for b in at.button))
            self.assertTrue(any('pending' in str(x.value).lower() for x in at.warning))

    def test_followup_baseline_must_be_explicit(self):
        from engine import load_csv,run_tool
        df=load_csv((Path(__file__).resolve().parents[1]/'data'/'demo_sales.csv').read_bytes())
        tool_out=run_tool(df,'grouped_summary',{'group':'category','metric':'revenue','operation':'sum'})
        sample={'status':'evidence_available','answer':'Unverified text',
                'trace':[{'tool':'grouped_summary','arguments':{},'result':tool_out}],
                'calculation_verified':True,'explanation_verified':False}
        with patch('agent.ask',return_value=sample) as send:
            at=_launch()
            self.field(at,'selectbox','Analysis tool').select('Summarise groups').run()
            self.field(at,'button','Run analysis').click().run()
            self.field(at,'checkbox','Use Gemini for this question: send the question, column names/types and analysis results (which may include matching rows).').check().run()
            self.field(at,'text_input','Question').input('A different unrelated question').run()
            self.field(at,'button','Ask Gemini').click().run()
            self.assertIsNone(send.call_args.kwargs['baseline_spec'])

    def test_saved_findings_are_planned_only(self):
        at=_launch()
        self.assertFalse(at.exception)
        self.assertNotIn('saved_findings',at.session_state)
        self.assertTrue(any('Saved Findings' in str(c.value) and 'planned' in str(c.value)
                            for c in at.get('caption')))



class DuplicateDownloadAppTests(unittest.TestCase):
    """Real Streamlit AppTest checks; AI calls are patched, never live requests.

    Both result visibility and absence of StreamlitDuplicateElementId are
    mandatory. These cases previously crashed during the full render.
    """
    @staticmethod
    def field(at, collection, label):
        return next(item for item in getattr(at,collection) if item.label==label)

    def submit(self, at, response, question='Show results'):
        with patch('agent.ask',return_value=response):
            self.field(at,'checkbox','Use Gemini for this question: send the question, column names/types and analysis results (which may include matching rows).').check().run()
            self.field(at,'text_input','Question').input(question).run()
            self.field(at,'button','Ask Gemini').click().run()
        self.assertFalse(at.exception, str(at.exception))
        return at

    @staticmethod
    def response(trace):
        return {'status':'evidence_available','answer':'Unverified model explanation',
                'trace':trace,'calculation_verified':True,'explanation_verified':False}

    @staticmethod
    def event(tool, output):
        return {'tool':tool,'arguments':output['evidence']['executed_spec']['arguments'],
                'result':output}

    def test_manual_result_and_identical_ai_result_have_independent_download_widgets(self):
        at=_launch()
        self.field(at,'selectbox','Analysis tool').select('Summarise groups').run()
        self.field(at,'selectbox','Group by').select('category').run()
        self.field(at,'button','Run analysis').click().run()
        self.assertFalse(at.exception, str(at.exception))
        manual=at.session_state['last_manual']['output']
        self.assertEqual(manual['tool'],'grouped_summary')
        self.submit(at,self.response([self.event('grouped_summary',manual)]),
                    'Which category has the largest count?')
        self.assertEqual(at.session_state['last_manual']['output'],
                         at.session_state['last_answer']['response']['trace'][0]['result'])
        headings=[x.value for x in at.subheader]
        self.assertTrue(any('Submitted calculation' in h for h in headings))
        self.assertTrue(any('Calculation 1' in h for h in headings))
        self.assertGreaterEqual(len(at.dataframe),3)  # source preview, manual, AI
        self.assertFalse(at.exception, str(at.exception))

    def test_two_identical_analytical_results_in_one_ai_trace_remain_visible(self):
        df=load_csv((Path(__file__).resolve().parents[1]/'data'/'demo_sales.csv').read_bytes())
        output=run_tool(df,'grouped_summary',{'group':'category','operation':'count_rows'})
        event=self.event('grouped_summary',output)
        at=self.submit(_launch(),self.response([event,event]),'Show each tool call')
        self.assertEqual(len(at.session_state['last_answer']['response']['trace']),2)
        self.assertGreaterEqual(len(at.dataframe),3)
        headings=[x.value for x in at.subheader]
        self.assertTrue(any('Calculation 1' in h for h in headings))
        self.assertTrue(any('Calculation 2' in h for h in headings))
        self.assertFalse(at.exception, str(at.exception))

    def test_unmodified_evidence_download_payload_and_explicit_key(self):
        from ui_components import evidence_download
        import json
        content={'rows':[{'group_value':'A','value':10999999999999989},
                         {'group_value':'B','value':None}],
                 'evidence':{'calculation_status':'completed'}}
        unchanged=json.dumps(content,sort_keys=True)
        with patch('ui_components.st.download_button') as widget:
            evidence_download(content,'analysis_result.json','Download result JSON',
                              location='ai_trace_result',occurrence=2)
        self.assertEqual(json.loads(widget.call_args.args[1]),content)
        self.assertEqual(json.dumps(content,sort_keys=True),unchanged)
        self.assertEqual(widget.call_args.kwargs['key'],
                         'finding_watch:evidence:ai_trace_result:2')
        self.assertEqual(widget.call_args.args[3],'application/json')

    def test_inspection_followed_by_grouped_aggregation_retains_both_results(self):
        df=load_csv((Path(__file__).resolve().parents[1]/'data'/'demo_sales.csv').read_bytes())
        inspected=run_tool(df,'inspect_dataset',{})
        grouped=run_tool(df,'grouped_summary',{'group':'category','operation':'count_rows'})
        at=self.submit(_launch(),self.response([
            self.event('inspect_dataset',inspected),
            self.event('grouped_summary',grouped)]),'Profile then group records')
        tools=[x['tool'] for x in at.session_state['last_answer']['response']['trace']]
        self.assertEqual(tools,['inspect_dataset','grouped_summary'])
        self.assertGreaterEqual(len(at.dataframe),3)
        headings=[x.value for x in at.subheader]
        self.assertTrue(any('Calculation 1' in h and 'inspect_dataset' in h for h in headings))
        self.assertTrue(any('Calculation 2' in h and 'grouped_summary' in h for h in headings))
        self.assertFalse(at.exception, str(at.exception))

if __name__ == "__main__":
    unittest.main()
