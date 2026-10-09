"""Offline isolated SDK-shim tests: NOT pinned-Gemini-SDK or live-provider validation."""
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from engine import load_csv

class _Part:
    def __init__(self, *, function_call=None, text=None, function_response=None):
        self.function_call=function_call
        self.text=text
        self.function_response=function_response
        self.thought=False
    @staticmethod
    def from_text(text):
        return _Part(text=text)

class _Content:
    def __init__(self, *, role, parts):
        self.role=role
        self.parts=parts

class _FunctionResponse:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake_types=types.ModuleType('google.genai.types')
        fake_types.Content=_Content
        fake_types.Part=_Part
        fake_types.FunctionResponse=_FunctionResponse
        fake_types.FunctionDeclaration=lambda **kw:types.SimpleNamespace(**kw)
        fake_genai=types.ModuleType('google.genai')
        fake_genai.types=fake_types
        fake_google=types.ModuleType('google')
        fake_google.genai=fake_genai
        dotenv=types.ModuleType('dotenv')
        dotenv.dotenv_values=lambda _:{}
        source=Path(__file__).resolve().parents[1]/'agent.py'
        module_spec=importlib.util.spec_from_file_location('_isolated_m2_agent',source)
        m=importlib.util.module_from_spec(module_spec)
        with patch.dict(sys.modules,{'google':fake_google,'google.genai':fake_genai,
                                     'google.genai.types':fake_types,'dotenv':dotenv}):
            module_spec.loader.exec_module(m)
        cls.agent=m
        cls.df=load_csv(b'category,status,revenue\nCoffee,done,120\nCoffee,no,300\nSnacks,done,180\n')

    def fc(self,name,args):
        return types.SimpleNamespace(candidates=[types.SimpleNamespace(content=_Content(
            role='model',parts=[_Part(function_call=types.SimpleNamespace(name=name,args=args,id='fake'))]))])

    def plain(self,body='Text response'):
        return types.SimpleNamespace(candidates=[types.SimpleNamespace(content=_Content(
            role='model',parts=[_Part(text=body)]))])

    def pair(self):
        return {'baseline':{'group':'category','metric':'revenue','operation':'sum','filters':[]},
                'challenged':{'group':'category','metric':'revenue','operation':'sum',
                              'filters':[{'field':'status','operator':'eq','value':'done'}]}}

    def test_valid_proposal_pending_not_calculated(self):
        result=self.agent.execute(self.df,'Challenge completed orders',
            lambda _:self.fc('propose_grouped_comparison',self.pair()))
        self.assertEqual(result['status'],'comparison_pending')
        self.assertFalse(result['calculation_verified'])
        self.assertTrue(result['pending_comparison']['confirmation_required'])
        self.assertNotIn('comparison',result)
        self.assertTrue(result['trace'][0]['result']['not_calculated'])

    def test_baseline_context_forwarded_and_locked(self):
        baseline={'tool':'grouped_summary','arguments':{'group':'category','metric':'revenue','operation':'sum'},'filters':[]}
        def generate(contents):
            msg=json.loads(contents[0].parts[0].text)
            self.assertEqual(msg['submitted_baseline_grouped_spec'],baseline)
            return self.fc('propose_grouped_comparison',self.pair())
        result=self.agent.execute(self.df,'Try completed only',generate,baseline_spec=baseline)
        self.assertEqual(result['status'],'comparison_pending')

    def test_redefined_baseline_rejected(self):
        baseline={'tool':'grouped_summary','arguments':{'group':'category','metric':'revenue','operation':'sum'},'filters':[]}
        altered=self.pair()
        altered['baseline']['operation']='count_rows'
        sequence=iter([self.fc('propose_grouped_comparison',altered),self.plain('Approved!')])
        result=self.agent.execute(self.df,'Try completed only',lambda _:next(sequence),baseline_spec=baseline)
        self.assertEqual(result['status'],'unverified')
        self.assertIn('error',result['trace'][0]['result'])

    def test_multiple_filter_changes_rejected(self):
        args=self.pair()
        args['challenged']['filters'].append({'field':'category','operator':'eq','value':'Coffee'})
        sequence=iter([self.fc('propose_grouped_comparison',args),self.plain('Completed')])
        result=self.agent.execute(self.df,'Try conditions',lambda _:next(sequence))
        self.assertEqual(result['status'],'unverified')
        self.assertIn('exactly one',result['trace'][0]['result']['error'])

    def test_malformed_proposal_returns_controlled_error(self):
        sequence=iter([self.fc('propose_grouped_comparison',{'baseline':[],'challenged':{}}),self.plain('Done')])
        result=self.agent.execute(self.df,'Bad comparison',lambda _:next(sequence))
        self.assertEqual(result['status'],'unverified')
        self.assertIn('object',result['trace'][0]['result']['error'])

    def test_five_existing_tools_remain_distinct(self):
        from engine import TOOLS
        self.assertEqual(set(TOOLS),{'inspect_dataset','filter_rows','grouped_summary','time_trend','correlation'})
        self.assertEqual(len(self.agent.DECLARATIONS),7)

if __name__=='__main__': unittest.main()
