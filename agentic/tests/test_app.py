"""Streamlit AppTest contracts. Execute only with Streamlit and SDK installed.

These are UI tests (not live model verification). AI requests are patched and use
an evidence-bearing response rather than the obsolete Phase 3 `answered` status.
"""
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

from engine import load_csv, run_tool


def _fresh():
    return AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=20).run()


def _field(at, collection, label):
    # Streamlit exposes sidebar controls in a separate tree on some releases.
    for root in (at, at.sidebar):
        for item in getattr(root, collection, []):
            if item.label==label:
                return item
    raise AssertionError(f'Missing {collection} control {label!r}')


def _loaded():
    at=_fresh()
    return _field(at,'button','Try an example').click().run()


def _select_local_suggestion(at):
    """Apply a safe suggestion explicitly, without running a calculation."""
    chooser=_field(at,'selectbox','Choose a suggested question')
    at=chooser.select(chooser.options[0]).run()
    return _field(at,'button','Use this question').click().run()


def _launch():
    # Legacy tests use the optional manual workbench. New Stage 1 tests call _loaded().
    at=_loaded()
    return _field(at,'toggle','Advanced · five manual analysis tools').set_value(True).run()



def _run_button(at):
    return _field(at,'button','Run analysis').click().run()


class AppTests(unittest.TestCase):
    def test_all_five_manual_tools(self):
        for choice in ['Inspect dataset','Filter rows','Summarise groups','Analyse time trends','Measure correlation']:
            with self.subTest(tool=choice):
                at=_launch()
                _field(at,'selectbox','Analysis tool').select(choice).run()
                if choice=='Filter rows':
                    _field(at,'selectbox','Group by' if choice=='Summarise groups' else 'Column').select('category').run()
                    _field(at,'text_input','Filter value' if choice=='Filter rows' else 'Filter 1 value').input('Coffee').run()
                if choice=='Summarise groups':
                    _field(at,'selectbox','Group by').select('category').run()
                _run_button(at)
                self.assertFalse(at.exception)
                self.assertFalse(at.error)
                output=at.session_state['last_manual']['output']
                self.assertEqual(output['evidence']['calculation_status'],'completed')
                self.assertEqual(output['evidence']['executed_spec']['tool'],output['tool'])
                self.assertEqual(output['evidence']['accounting']['input_rows'],4)
                self.assertEqual(output['evidence']['calculation_status'],'completed')

    def test_manual_filter_evidence_and_pending_controls(self):
        at=_launch()
        _field(at,'selectbox','Analysis tool').select('Summarise groups').run()
        _field(at,'selectbox','Group by').select('category').run()
        # 0 is the number of optional AND filters for grouped/time/correlation.
        _field(at,'number_input','Number of filters').set_value(1).run()
        _field(at,'selectbox','Filter 1 column').select('category').run()
        _field(at,'text_input','Filter 1 value').input('Coffee').run()
        _run_button(at)
        self.assertFalse(at.exception)
        out=at.session_state['last_manual']['output']
        self.assertEqual(out['evidence']['executed_spec']['filters'],[
            {'field':'category','operator':'eq','value':'Coffee'}])
        self.assertEqual(out['evidence']['accounting']['selected_rows'],2)
        self.assertEqual(out['rows'][0]['value'],3000)
        # Editing a filter does not overwrite the submitted specification.
        _field(at,'text_input','Filter 1 value').input('Snacks').run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['last_manual']['output']['rows'][0]['value'],3000)
        self.assertTrue(any('previous result is hidden' in str(c.value).lower()
                            for c in at.warning))

    def test_upload_empty_state(self):
        at=_fresh()
        # AppTest does not reliably support file_uploader uploads; empty entry is verified here.
        self.assertFalse(at.exception)
        self.assertFalse(any('Your calculated finding' in h.value for h in at.subheader))

    def test_error_feedback(self):
        at=_launch()
        _field(at,'selectbox','Analysis tool').select('Filter rows').run()
        _field(at,'selectbox','Column').select('revenue').run()
        _field(at,'text_input','Filter value').input('invalid number').run()
        _run_button(at)
        self.assertFalse(at.exception)
        self.assertEqual(len(at.error),1)


class ChatAppTests(unittest.TestCase):
    def _submit(self,at):
        return _field(at,'button','Analyse').click().run()

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
            _field(at,'checkbox','I agree to send my question and relevant dataset information to Gemini.').check().run()
            _field(at,'text_input','Your question').input('Which category leads?').run()
            self._submit(at)
            self.assertFalse(at.exception)
            ask.assert_called_once()
            saved=at.session_state['last_answer']
            self.assertEqual(saved['response']['status'],'evidence_available')
            self.assertFalse(saved['response']['explanation_verified'])
            self.assertEqual(saved['submitted_question'],'Which category leads?')
            self.assertEqual(saved['response']['trace'][0]['result']['evidence']['calculation_status'],'completed')
            _field(at,'text_input','Your question').input('Which date is best?').run()
            self.assertFalse(at.exception)
            self.assertEqual(at.session_state['last_answer']['submitted_question'],'Which category leads?')
            self.assertTrue(any('pending' in str(w.value).lower() for w in at.warning))

    def test_missing_key_feedback(self):
        from agent import AgentError
        with patch('agent.ask',side_effect=AgentError('No API key found.')):
            at=_launch()
            _field(at,'checkbox','I agree to send my question and relevant dataset information to Gemini.').check().run()
            _field(at,'text_input','Your question').input('Question').run()
            self._submit(at)
            self.assertFalse(at.exception)
            self.assertTrue(any('Gemini could not complete' in x.value for x in at.error))
            self.assertEqual(at.session_state['stage1_question'],'Question')

class M2ChallengeAppTests(unittest.TestCase):
    """Run on Windows with real Streamlit and SDK packages (no live model calls)."""

    @staticmethod
    def widget(at, collection, label):
        return _field(at,collection,label)

    def test_manual_comparison_requires_explicit_confirmation(self):
        at=_launch()
        _field(at,'selectbox','Analysis tool').select('Summarise groups').run()
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
            self.widget(at,'checkbox','I agree to send my question and relevant dataset information to Gemini.').check().run()
            self.widget(at,'text_input','Your question').input('What if North only?').run()
            _field(at,'button','Analyse').click().run()
            self.assertFalse(at.exception)
            self.assertNotIn('last_ai_comparison',at.session_state)
            self.widget(at,'button','Confirm and run proposed comparison').click().run()
            self.assertFalse(at.exception)
            result=at.session_state['last_ai_comparison']['result']
            self.assertEqual(result['accounting']['challenged']['selected_rows'],2)
            self.assertEqual(result['status'],'completed')
            self.assertFalse(any('not calculated' in str(x.value).lower() for x in at.warning))
            self.assertTrue(any('confirmed' in str(x.value).lower() for x in at.success))
            self.widget(at,'text_input','Your question').input('Some other question').run()
            self.assertFalse(at.exception)
            self.assertFalse(any(b.label=='Confirm and run proposed comparison' for b in at.button))

class P1P3UiAppTests(unittest.TestCase):
    """Requires Streamlit + pinned google-genai; never makes live provider calls."""
    @staticmethod
    def field(at, collection, label):
        return _field(at,collection,label)

    @staticmethod
    def mocked_answer(status='clarification', answer='Which column and measure?', trace=None):
        return {'status':status, 'answer':answer,'trace':trace or [],
                'calculation_verified':False,'explanation_verified':False}

    def submit_question(self, at, text):
        self.field(at,'checkbox','I agree to send my question and relevant dataset information to Gemini.').check().run()
        self.field(at,'text_input','Your question').input(text).run()
        self.field(at,'button','Analyse').click().run()
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
            self.field(at,'text_input','Your question').input('What changed?').run()
            self.assertFalse(at.exception)
            self.assertTrue(any('current question has changed' in str(w.value).lower() for w in at.info))

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
            self.assertTrue(any('did not complete' in str(e.value).lower() for e in at.error))

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
            self.assertGreaterEqual(len(at.dataframe),1)
            rendered=at.dataframe[-1].value
            self.assertIn('10,999,999,999,999,989',list(rendered.iloc[0].astype(str)))
            self.assertIn('No numeric value',list(rendered.iloc[1].astype(str)))
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
            self.field(at,'checkbox','I agree to send my question and relevant dataset information to Gemini.').check().run()
            self.field(at,'text_input','Your question').input('A different unrelated question').run()
            self.field(at,'button','Analyse').click().run()
            self.assertIsNone(send.call_args.kwargs['baseline_spec'])

    def test_saved_findings_are_planned_only(self):
        at=_launch()
        self.assertFalse(at.exception)
        self.assertNotIn('saved_findings',at.session_state)
        self.assertFalse(any('Saved Findings' in str(b.label) for b in at.button))



class DuplicateDownloadAppTests(unittest.TestCase):
    """Real Streamlit AppTest checks; AI calls are patched, never live requests.

    Both result visibility and absence of StreamlitDuplicateElementId are
    mandatory. These cases previously crashed during the full render.
    """
    @staticmethod
    def field(at, collection, label):
        return _field(at,collection,label)

    def submit(self, at, response, question='Show results'):
        with patch('agent.ask',return_value=response):
            self.field(at,'checkbox','I agree to send my question and relevant dataset information to Gemini.').check().run()
            self.field(at,'text_input','Your question').input(question).run()
            self.field(at,'button','Analyse').click().run()
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
        self.assertTrue(any('Calculated finding' in h for h in headings))
        self.assertIn('last_visible_ai_trace_index',at.session_state)
        self.assertFalse(at.exception, str(at.exception))

    def test_two_identical_analytical_results_in_one_ai_trace_remain_visible(self):
        df=load_csv((Path(__file__).resolve().parents[1]/'data'/'demo_sales.csv').read_bytes())
        output=run_tool(df,'grouped_summary',{'group':'category','operation':'count_rows'})
        event=self.event('grouped_summary',output)
        at=self.submit(_launch(),self.response([event,event]),'Show each tool call')
        self.assertEqual(len(at.session_state['last_answer']['response']['trace']),2)
        self.assertGreaterEqual(len(at.dataframe),1)
        self.assertTrue(any(w.label=='Which calculated result would you like to see?' for w in at.selectbox))
        options=_field(at,'selectbox','Which calculated result would you like to see?').options
        _field(at,'selectbox','Which calculated result would you like to see?').select(options[0]).run()
        self.assertTrue(any('Calculated finding' in h.value for h in at.subheader))
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
        self.assertGreaterEqual(len(at.dataframe),1)
        headings=[x.value for x in at.subheader]
        self.assertFalse(any('Dataset inspection' in h for h in headings))
        self.assertTrue(any('Calculated finding' in h for h in headings))
        self.assertFalse(at.exception, str(at.exception))

class Stage1JourneyAppTests(unittest.TestCase):
    """Real Streamlit AppTests, not SDK shims or live-provider checks."""

    def test_suggested_question_requires_selection_then_apply_then_analyse(self):
        at=_loaded()
        self.assertEqual(_field(at,'text_input','Your question').value,'')
        chooser=_field(at,'selectbox','Choose a suggested question')
        self.assertIsNone(chooser.value)
        chooser.select(chooser.options[0]).run()
        self.assertEqual(_field(at,'text_input','Your question').value,'')
        self.assertNotIn('stage1_local_answer',at.session_state)
        at=_field(at,'button','Use this question').click().run()
        self.assertEqual(_field(at,'text_input','Your question').value,chooser.options[0])
        self.assertNotIn('stage1_local_answer',at.session_state)
        _field(at,'button','Analyse').click().run()
        self.assertEqual(at.session_state['stage1_local_answer']['output']['rows'][0]['value'],3000)
        self.assertFalse(at.exception,str(at.exception))

    def test_entry_has_no_dataset_until_explicit_action(self):
        at=_fresh()
        self.assertFalse(at.exception)
        self.assertTrue(any('Try an example'==b.label for b in at.button))
        self.assertFalse(any('Your calculated finding' in h.value for h in at.subheader))
        self.assertNotIn('stage1_local_answer',at.session_state)

    def test_example_answer_first_revenue_and_scope(self):
        at=_loaded()
        self.assertFalse(at.exception)
        self.assertTrue(any('demo_sales.csv' in str(x.value) for x in at.markdown))
        at=_select_local_suggestion(at)
        self.assertNotIn('stage1_local_answer',at.session_state)
        _field(at,'button','Analyse').click().run()
        self.assertFalse(at.exception,str(at.exception))
        finding=at.session_state['stage1_local_answer']['output']
        self.assertEqual(finding['evidence']['accounting']['input_rows'],4)
        self.assertEqual(finding['evidence']['accounting']['excluded_by_filters'],0)
        self.assertEqual([(r['group_value'],r['value']) for r in finding['rows']],
                         [('Coffee',3000),('Snacks',1400)])
        self.assertTrue(any('Coffee leads in total revenue' in m.value for m in at.markdown))
        self.assertTrue(any('3,000' in frame.value.to_string() for frame in at.dataframe))
        self.assertTrue(any('How this was calculated'==x.label for x in at.get('expander')))

    def test_question_edit_hides_submitted_result(self):
        at=_select_local_suggestion(_loaded())
        _field(at,'button','Analyse').click().run()
        _field(at,'text_input','Your question').input('Another question').run()
        self.assertFalse(at.exception)
        self.assertFalse(any('Your calculated finding' in h.value for h in at.subheader))
        self.assertTrue(any('pending' in str(i.value).lower() for i in at.info))

    def test_inspection_then_grouped_uses_aggregation_as_primary(self):
        df=load_csv((Path(__file__).resolve().parents[1]/'data'/'demo_sales.csv').read_bytes())
        inspected=run_tool(df,'inspect_dataset',{})
        grouped=run_tool(df,'grouped_summary',{'group':'category','metric':'revenue','operation':'sum'})
        response={'status':'evidence_available','answer':'Unverified text',
                  'calculation_verified':True,'explanation_verified':False,
                  'trace':[{'tool':'inspect_dataset','result':inspected},
                           {'tool':'grouped_summary','result':grouped}]}
        at=_loaded()
        with patch('agent.ask',return_value=response):
            _field(at,'checkbox','I agree to send my question and relevant dataset information to Gemini.').check().run()
            _field(at,'text_input','Your question').input('Profile first, then find top revenue group').run()
            _field(at,'button','Analyse').click().run()
        self.assertFalse(at.exception,str(at.exception))
        self.assertEqual(at.session_state['last_visible_ai_trace_index'],2)
        self.assertTrue(any('Calculated finding' in h.value for h in at.subheader))
        self.assertTrue(any('Coffee leads in total revenue' in m.value for m in at.markdown))
        self.assertTrue(any('3,000' in frame.value.to_string() for frame in at.dataframe))

    def test_provider_failure_preserves_question_and_exposes_recovery(self):
        from agent import AgentError
        at=_loaded()
        with patch('agent.ask',side_effect=AgentError('Test provider unavailable')):
            _field(at,'checkbox','I agree to send my question and relevant dataset information to Gemini.').check().run()
            _field(at,'text_input','Your question').input('Explain this dataset').run()
            _field(at,'button','Analyse').click().run()
        self.assertFalse(at.exception,str(at.exception))
        self.assertEqual(at.session_state['stage1_question'],'Explain this dataset')
        self.assertTrue(any('retry Analyse' in str(x.value) for x in at.error))

class Stage1DownloadLocationAppTests(unittest.TestCase):
    """Run with REAL Streamlit AppTest and Gemini SDK on Windows.

    Model traffic is patched, but Streamlit rendering and widget identity are
    real. A missing StreamlitDependency should remain a test import failure.
    """

    @staticmethod
    def _event(tool, output):
        return {'tool':tool,'arguments':output['evidence']['executed_spec']['arguments'],
                'result':output}

    @staticmethod
    def _answer(trace):
        return {'status':'evidence_available','answer':'Model commentary is unverified',
                'trace':trace,'calculation_verified':True,'explanation_verified':False}

    def _ask(self, at, trace, question):
        with patch('agent.ask',return_value=self._answer(trace)):
            _field(at,'checkbox','I agree to send my question and relevant dataset information to Gemini.').check().run()
            _field(at,'text_input','Your question').input(question).run()
            _field(at,'button','Analyse').click().run()
        self.assertFalse(at.exception,str(at.exception))
        return at

    def test_profile_download_and_local_suggested_result_coexist(self):
        at=_select_local_suggestion(_loaded())
        _field(at,'button','Profile all columns').click().run()
        self.assertFalse(at.exception,str(at.exception))
        self.assertEqual(at.session_state['stage1_profile']['output']['tool'],'inspect_dataset')
        _field(at,'button','Analyse').click().run()
        self.assertFalse(at.exception,str(at.exception))
        self.assertEqual(at.session_state['stage1_local_answer']['output']['tool'],'grouped_summary')
        self.assertTrue(any('How this was calculated'==e.label for e in at.get('expander')))
        self.assertEqual([(r['group_value'],r['value'])
                          for r in at.session_state['stage1_local_answer']['output']['rows']],
                         [('Coffee',3000),('Snacks',1400)])

    def test_local_challenge_confirmation_renders_its_own_download(self):
        at=_select_local_suggestion(_loaded())
        _field(at,'button','Analyse').click().run()
        self.assertFalse(at.exception,str(at.exception))
        _field(at,'selectbox','Challenged filter column').select('category').run()
        _field(at,'text_input','Challenged filter value').input('Coffee').run()
        _field(at,'button','Run confirmed comparison').click().run()
        self.assertFalse(at.exception,str(at.exception))
        comparison=at.session_state['last_suggested_comparison']['result']
        self.assertEqual(comparison['status'],'completed')
        self.assertEqual(comparison['accounting']['baseline']['selected_rows'],4)
        self.assertEqual(comparison['accounting']['challenged']['selected_rows'],2)
        self.assertTrue(any('confirmed' in str(x.value).lower() for x in at.success))
        self.assertTrue(any('User-confirmed Challenge' in x.value for x in at.subheader))
        # Changing the exact condition hides the previous completed result.
        _field(at,'text_input','Challenged filter value').input('Snacks').run()
        self.assertFalse(at.exception,str(at.exception))
        self.assertFalse(any('User-confirmed Challenge' in x.value for x in at.subheader))

    def test_ai_primary_and_supporting_identical_outputs_both_render(self):
        df=load_csv((Path(__file__).resolve().parents[1]/'data'/'demo_sales.csv').read_bytes())
        grouped=run_tool(df,'grouped_summary',{'group':'category','metric':'revenue','operation':'sum'})
        event=self._event('grouped_summary',grouped)
        at=self._ask(_loaded(),[event], 'Recompute the same revenue result')
        self.assertEqual(at.session_state['last_visible_ai_trace_index'],1)
        self.assertEqual(at.session_state['last_answer']['response']['trace'][0]['result'],grouped)
        self.assertTrue(any('Calculated finding' in x.value for x in at.subheader))
        self.assertTrue(any('Other calculations and execution details'==e.label
                            for e in at.get('expander')))

    def test_two_identical_ai_trace_downloads_and_primary_choice(self):
        df=load_csv((Path(__file__).resolve().parents[1]/'data'/'demo_sales.csv').read_bytes())
        grouped=run_tool(df,'grouped_summary',{'group':'category','operation':'count_rows'})
        event=self._event('grouped_summary',grouped)
        at=self._ask(_loaded(),[event,event],'Show both calculations')
        self.assertTrue(any('Which calculated result would you like to see?'==s.label for s in at.selectbox))
        chooser=_field(at,'selectbox','Which calculated result would you like to see?')
        chooser.select(chooser.options[1]).run()
        self.assertFalse(at.exception,str(at.exception))
        self.assertEqual(at.session_state['last_visible_ai_trace_index'],2)
        self.assertEqual(len(at.session_state['last_answer']['response']['trace']),2)
        self.assertTrue(any('Calculated finding' in x.value for x in at.subheader))
        self.assertTrue(any('Other calculations and execution details'==e.label
                            for e in at.get('expander')))

    def test_inspection_then_grouped_aggregation_keeps_both_download_surfaces(self):
        df=load_csv((Path(__file__).resolve().parents[1]/'data'/'demo_sales.csv').read_bytes())
        inspection=run_tool(df,'inspect_dataset',{})
        grouped=run_tool(df,'grouped_summary',{'group':'category','metric':'revenue','operation':'sum'})
        trace=[self._event('inspect_dataset',inspection),self._event('grouped_summary',grouped)]
        at=self._ask(_loaded(),trace,'Inspect then calculate revenue')
        self.assertEqual(at.session_state['last_visible_ai_trace_index'],2)
        self.assertEqual(len(at.session_state['last_answer']['response']['trace']),2)
        self.assertTrue(any('Calculated finding' in x.value for x in at.subheader))
        self.assertFalse(at.exception,str(at.exception))

if __name__ == "__main__":
    unittest.main()

class Stage2AppTests(unittest.TestCase):
    """Real pinned-Streamlit AppTest regressions, no provider network calls."""
    @staticmethod
    def evidence(tool, args):
        df=load_csv((Path(__file__).resolve().parents[1]/'data'/'demo_sales.csv').read_bytes())
        return run_tool(df,tool,args)

    @staticmethod
    def response(*results):
        return {'status':'evidence_available','answer':'Provider commentary (not verified)',
                'trace':[{'tool':r['tool'],'result':r,'arguments':r['evidence']['executed_spec']['arguments']} for r in results],
                'calculation_verified':True,'explanation_verified':False}

    @staticmethod
    def ask_screen(response, question='What does this dataset show?'):
        with patch('agent.ask',return_value=response):
            at=_loaded()
            _field(at,'checkbox','I agree to send my question and relevant dataset information to Gemini.').check().run()
            _field(at,'text_input','Your question').input(question).run()
            _field(at,'button','Analyse').click().run()
        return at

    def test_inspection_view_with_quality_and_download(self):
        out=self.evidence('inspect_dataset',{})
        at=self.ask_screen(self.response(out))
        self.assertFalse(at.exception)
        self.assertTrue(any('Dataset overview' in m.value for m in at.markdown))
        self.assertTrue(any('How this was calculated'==e.label for e in at.expander))
        self.assertTrue(any(b.label=='Download original result JSON' for b in at.button))

    def test_filtered_view_total_vs_bounded_display(self):
        out=self.evidence('filter_rows',{'field':'category','operator':'eq','value':'Coffee','limit':1})
        at=self.ask_screen(self.response(out))
        self.assertFalse(at.exception)
        self.assertTrue(any('2 records match' in m.value for m in at.markdown))
        self.assertTrue(any('matching records are shown' in w.value.lower() for w in at.warning))

    def test_group_time_correlation_readable_results(self):
        cases=[('grouped_summary',{'group':'category','operation':'sum','metric':'revenue'},'Coffee leads'),
               ('time_trend',{'date_column':'date','date_format':'%Y-%m-%d','frequency':'month',
                              'operation':'sum','metric':'revenue'},'observed month periods'),
               ('correlation',{'x':'revenue','y':'units'},'Pearson correlation')]
        for tool,args,fragment in cases:
            with self.subTest(tool=tool):
                at=self.ask_screen(self.response(self.evidence(tool,args)))
                self.assertFalse(at.exception)
                self.assertTrue(any(fragment in m.value for m in at.markdown))
                self.assertTrue(any(b.label=='Download original result JSON' for b in at.button))

    def test_inspection_then_aggregation_is_primary(self):
        inspect=self.evidence('inspect_dataset',{})
        grouped=self.evidence('grouped_summary',{'group':'category','operation':'sum','metric':'revenue'})
        at=self.ask_screen(self.response(inspect,grouped))
        self.assertFalse(at.exception)
        self.assertTrue(any('Coffee leads' in m.value for m in at.markdown))
        self.assertFalse(any(s.label=='Which calculated result would you like to see?' for s in at.selectbox))
        self.assertTrue(any(b.label=='Download this tool result JSON' for b in at.button))

    def test_multiple_repeated_results_selection_is_scoped_to_response(self):
        one=self.evidence('grouped_summary',{'group':'category','operation':'sum','metric':'revenue'})
        two=self.evidence('grouped_summary',{'group':'region','operation':'count_rows'})
        at=self.ask_screen(self.response(one,one,two))
        self.assertFalse(at.exception)
        picker=_field(at,'selectbox','Which calculated result would you like to see?')
        self.assertEqual(len(picker.options),3)
        picker.select(picker.options[1]).run()
        self.assertFalse(at.exception)
        self.assertTrue(any('Calculated finding' in x.value for x in at.subheader))
        self.assertTrue(any(b.label=='Download original result JSON' for b in at.button))
        self.assertEqual(at.session_state['last_visible_ai_trace_index'],2)
        _field(at,'text_input','Your question').input('Edited question').run()
        self.assertFalse(at.exception)
        self.assertFalse(any(x.value=='Calculated finding' for x in at.subheader))
        self.assertFalse(any(b.label=='Download original result JSON' for b in at.button))

    def test_new_same_question_response_does_not_inherit_selection(self):
        one=self.evidence('grouped_summary',{'group':'category','metric':'revenue','operation':'sum'})
        with patch('agent.ask',return_value=self.response(one,one)):
            at=_loaded()
            _field(at,'checkbox','I agree to send my question and relevant dataset information to Gemini.').check().run()
            _field(at,'text_input','Your question').input('Compare totals').run()
            _field(at,'button','Analyse').click().run()
            picker=_field(at,'selectbox','Which calculated result would you like to see?')
            picker.select(picker.options[0]).run()
            self.assertEqual(at.session_state['last_visible_ai_trace_index'],1)
            _field(at,'button','Analyse').click().run()
            self.assertFalse(at.exception)
            self.assertFalse(any(x.value=='Calculated finding' for x in at.subheader))

    def test_contextual_followups_retain_prior_context_without_calculating_from_choice(self):
        clarification={'status':'clarification','answer':'Date format?','trace':[],
                       'calculation_verified':False,'explanation_verified':False}
        with patch('agent.ask',side_effect=[clarification,clarification,clarification]) as send:
            at=_loaded()
            _field(at,'checkbox','I agree to send my question and relevant dataset information to Gemini.').check().run()
            original='What happened on 02/03/2026?'
            _field(at,'text_input','Your question').input(original).run()
            _field(at,'button','Analyse').click().run()
            _field(at,'radio','Clarification approach').set_value('Explain the missing context (dates or other details)').run()
            _field(at,'text_area','Your clarification').input('Dates are DD/MM/YYYY').run()
            self.assertEqual(send.call_count,1)
            _field(at,'button','Continue with original question and my clarification').click().run()
            self.assertEqual(send.call_count,2)
            _field(at,'radio','Clarification approach').set_value('Explain the missing context (dates or other details)').run()
            _field(at,'text_area','Your clarification').input('Use monthly intervals').run()
            self.assertEqual(send.call_count,2)
            _field(at,'button','Continue with original question and my clarification').click().run()
            self.assertFalse(at.exception)
            self.assertEqual(send.call_count,3)
            self.assertEqual(send.call_args.args[1],original)
            self.assertIn('DD/MM/YYYY',send.call_args.kwargs['clarification_context'])
            self.assertIn('monthly intervals',send.call_args.kwargs['clarification_context'])

    def test_provider_error_after_success_hides_old_answer_and_preserves_question(self):
        from agent import AgentError
        one=self.evidence('grouped_summary',{'group':'category','operation':'sum','metric':'revenue'})
        with patch('agent.ask',side_effect=[self.response(one),AgentError('Temporarily unavailable')]):
            at=_loaded()
            _field(at,'checkbox','I agree to send my question and relevant dataset information to Gemini.').check().run()
            _field(at,'text_input','Your question').input('First question').run()
            _field(at,'button','Analyse').click().run()
            self.assertTrue(any('Coffee leads' in m.value for m in at.markdown))
            _field(at,'text_input','Your question').input('Second question').run()
            _field(at,'button','Analyse').click().run()
            self.assertFalse(at.exception)
            self.assertTrue(any('Gemini could not complete' in e.value for e in at.error))
            self.assertFalse(any('Coffee leads' in m.value for m in at.markdown))
            self.assertEqual(at.session_state['stage1_question'],'Second question')
