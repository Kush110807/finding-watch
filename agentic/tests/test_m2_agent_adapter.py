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

    def test_contextual_clarification_is_separate_from_unchanged_original_question(self):
        captured=[]
        def fake_generate(contents):
            request=json.loads(contents[0].parts[0].text)
            captured.append(request)
            return self.fc('request_clarification',{'question':'Which period should be analysed?'})
        out=self.agent.execute(self.df,'What happened on 01/02/2026?',fake_generate,
            clarification_context='Use DD/MM/YYYY for the date column.')
        self.assertEqual(out['question'],'What happened on 01/02/2026?')
        self.assertEqual(out['status'],'clarification')
        self.assertEqual(captured[0]['question'],'What happened on 01/02/2026?')
        self.assertEqual(captured[0]['user_provided_clarification_context'],
                         'Use DD/MM/YYYY for the date column.')
        self.assertNotIn('tool',captured[0])

    def test_contextual_clarification_validation(self):
        for malformed in ([],{},'', '  ', 'a'*2001):
            with self.subTest(malformed=type(malformed).__name__):
                with self.assertRaises(self.agent.AgentError):
                    self.agent.execute(self.df,'Valid original question',lambda _:None,
                                       clarification_context=malformed)

    def test_provider_failure_after_successful_tool_keeps_incomplete_trace_without_replaying(self):
        ProviderFailure=self.agent.ProviderFailure
        calls=[]
        def generate(contents):
            calls.append(len(contents))
            if len(calls)==1:
                return self.fc('grouped_summary',{'group':'category','metric':'revenue','operation':'sum'})
            raise ProviderFailure('provider_transient',503,2,21)
        result=self.agent.execute(self.df,'Sum by category',generate)
        self.assertEqual(calls,[1,3])
        self.assertEqual(result['status'],'error')
        self.assertEqual(len(result['trace']),1)
        self.assertEqual(result['trace'][0]['tool'],'grouped_summary')
        self.assertFalse(result['calculation_verified'])
        self.assertFalse(result['explanation_verified'])
        self.assertEqual(result['provider_diagnostic']['attempts'],2)
        self.assertTrue(result['provider_diagnostic']['partial_tools_completed'])

    def test_initial_provider_daily_quota_returns_safe_unverified_error(self):
        ProviderFailure=self.agent.ProviderFailure
        result=self.agent.execute(self.df,'What leads?',lambda _: (_ for _ in ()).throw(
            ProviderFailure('daily_quota',429,1,1.0)))
        self.assertEqual(result['status'],'error')
        self.assertEqual(result['trace'],[])
        self.assertFalse(result['provider_diagnostic']['partial_tools_completed'])
        self.assertIn('daily',result['answer'])

    def test_five_existing_tools_remain_distinct(self):
        from engine import TOOLS
        self.assertEqual(set(TOOLS),{'inspect_dataset','filter_rows','grouped_summary','time_trend','correlation'})
        self.assertEqual(len(self.agent.DECLARATIONS),7)

if __name__=='__main__': unittest.main()
