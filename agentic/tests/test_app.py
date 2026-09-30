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
