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
                            for c in at.get('caption')))

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

if __name__=='__main__':
    unittest.main()
