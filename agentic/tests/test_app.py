import unittest
from streamlit.testing.v1 import AppTest

class AppTests(unittest.TestCase):
    def test_all_tools(self):
        for choice in ['Inspect dataset','Filter rows','Summarise groups','Analyse time trends','Measure correlation']:
            with self.subTest(tool=choice):
                at=AppTest.from_file('../app.py').run()
                at.selectbox[0].select(choice).run()
                if choice=='Filter rows':
                    at.selectbox[1].select('category').run()
                    at.text_input[0].input('Coffee').run()
                if choice=='Summarise groups': at.selectbox[1].select('category').run()
                at.button[0].click().run()
                self.assertFalse(at.exception)
                self.assertFalse(at.error)
                self.assertEqual(len(at.dataframe),2)
    def test_upload_empty_state(self):
        at=AppTest.from_file('../app.py').run()
        at.radio[0].set_value('Upload CSV').run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.dataframe),0)
    def test_error_feedback(self):
        at=AppTest.from_file('../app.py').run()
        at.selectbox[0].select('Filter rows').run()
        at.selectbox[1].select('revenue').run()
        at.text_input[0].input('invalid number').run()
        at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.error),1)

if __name__=='__main__': unittest.main()

class ChatAppTests(unittest.TestCase):
    def test_chat_submission(self):
        from unittest.mock import patch
        sample={'status':'answered','answer':'Coffee totals 3000.','trace':[],'model':'test'}
        with patch('agent.ask',return_value=sample) as ask:
            at=AppTest.from_file('../app.py').run()
            at.checkbox[0].check().run()
            at.text_input[0].input('Which category leads?').run()
            next(b for b in at.button if b.label=='Ask Gemini').click().run()
            self.assertFalse(at.exception)
            ask.assert_called_once()
            self.assertEqual(at.session_state['last_answer']['response']['answer'],'Coffee totals 3000.')
    def test_missing_key_feedback(self):
        from unittest.mock import patch
        from agent import AgentError
        with patch('agent.ask',side_effect=AgentError('No API key found.')):
            at=AppTest.from_file('../app.py').run()
            at.checkbox[0].check().run()
            at.text_input[0].input('Question').run()
            next(b for b in at.button if b.label=='Ask Gemini').click().run()
            self.assertFalse(at.exception)
            self.assertIn('No API key',at.error[0].value)
