import unittest
from unittest.mock import patch
from google.genai import types
from engine import load_csv
from agent import execute, AgentError, safe_error, configuration, DECLARATIONS

def response(*parts):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role='model',parts=list(parts)))])
def call(name,args):
    return response(types.Part(function_call=types.FunctionCall(name=name,args=args)))
def text(value): return response(types.Part.from_text(text=value))

class AgentTests(unittest.TestCase):
    def setUp(self):
        self.df=load_csv(b'category,revenue\nCoffee,10\nCoffee,20\nSnacks,5\n')
    def test_real_tool_result_and_signature_preservation(self):
        first=call('grouped_summary',{'group':'category','metric':'revenue','operation':'sum'})
        first.candidates[0].content.parts[0].thought_signature=b'signature'
        invocations=[]
        def generate(contents):
            invocations.append(len(contents))
            if len(invocations)==1: return first
            self.assertEqual(contents[1].parts[0].thought_signature,b'signature')
            payload=contents[2].parts[0].function_response.response
            self.assertEqual(payload['rows'][0]['value'],30)
            return text('Coffee leads with 30, using grouped_summary.')
        out=execute(self.df,'Highest revenue category?',generate)
        self.assertEqual(out['status'],'evidence_available')
        self.assertFalse(out['explanation_verified'])
        self.assertTrue(out['calculation_verified'])
        self.assertEqual(out['question'],'Highest revenue category?')
        self.assertEqual(len(out['trace']),1)
    def test_malformed_model_filter_remains_unverified(self):
        sequence=iter([call('grouped_summary',{'group':'category','metric':'revenue',
            'operation':'sum','filters':[{'field':'category','operator':[],
                                           'value':'Coffee'}]}),
                       text('Coffee wins, trust me.')])
        out=execute(self.df,'Which category leads?',lambda _:next(sequence))
        self.assertEqual(out['status'],'unverified')
        self.assertFalse(out['calculation_verified'])
        self.assertIn('error',out['trace'][0]['result'])
        self.assertNotIn('Coffee wins',out['answer'])

    def test_malformed_model_time_format_remains_unverified(self):
        df=load_csv(b'd,amount\n2026-01-01,20\n')
        sequence=iter([call('time_trend',{'date_column':'d','metric':'amount',
                           'date_format':[],'operation':'sum'}),
                       text('January 20.')])
        out=execute(df,'Monthly totals?',lambda _:next(sequence))
        self.assertEqual(out['status'],'unverified')
        self.assertIn('error',out['trace'][0]['result'])

    def test_ungrounded_answer_blocked(self):
        out=execute(self.df,'Total?',lambda _:text('99999'))
        self.assertEqual(out['status'],'unverified')
        self.assertNotIn('99999',out['answer'])
    def test_clarification(self):
        out=execute(self.df,'Best?',lambda _:call('request_clarification',{'question':'Best by which metric?'}))
        self.assertEqual(out['status'],'clarification')
        self.assertEqual(out['trace'][0]['tool'],'request_clarification')
    def test_unknown_tool_not_executed(self):
        responses=iter([call('exec',{'code':'print(1)'}),text('Pretend answer')])
        out=execute(self.df,'Run code',lambda _:next(responses))
        self.assertEqual(out['status'],'unverified')
        self.assertIn('error',out['trace'][0]['result'])
    def test_round_limit(self):
        out=execute(self.df,'Loop',lambda _:call('inspect_dataset',{}))
        self.assertEqual(out['status'],'limited')
        self.assertEqual(len(out['trace']),6)
    def test_call_limit(self):
        def generate(_):
            return response(*[types.Part(function_call=types.FunctionCall(name='inspect_dataset',args={})) for _ in range(10)])
        out=execute(self.df,'Loop',generate)
        self.assertEqual(out['status'],'limited')
        self.assertEqual(len(out['trace']),8)
    def test_error_redaction(self):
        def fail(_): raise RuntimeError('secret-key-in-error')
        out=execute(self.df,'Test',fail)
        self.assertEqual(out['status'],'error')
        self.assertNotIn('secret',out['answer'])
    def test_quota_error(self):
        class Quota(Exception): code=429
        self.assertIn('Quota',safe_error(Quota()))
    def test_blank_and_long(self):
        for q in ['', ' '*10,'x'*4001]:
            with self.assertRaises(AgentError): execute(self.df,q,lambda _:None)
    def test_empty_response(self):
        out=execute(self.df,'Question',lambda _:types.GenerateContentResponse())
        self.assertEqual(out['status'],'error')
    def test_config_no_secret_required(self):
        with patch('agent.dotenv_values',return_value={}),patch.dict('os.environ',{},clear=True):
            key,model=configuration()
            self.assertEqual(key,''); self.assertTrue(model)
    def test_schema_sdk_validation(self):
        self.assertEqual(len(DECLARATIONS),6)
        cfg=types.GenerateContentConfig(tools=[types.Tool(function_declarations=DECLARATIONS)])
        self.assertEqual(len(cfg.tools[0].function_declarations),6)
    def test_initial_request_contains_no_rows(self):
        def generate(contents):
            self.assertNotIn('Coffee',contents[0].parts[0].text)
            return call('request_clarification',{'question':'Which metric?'})
        execute(self.df,'Compare categories',generate)
    def test_missing_time_metric_count(self):
        df=load_csv(b'd\n2026-01-01\n2026-01-02\n')
        sequence=iter([call('time_trend',{'date_column':'d','date_format':'%Y-%m-%d','frequency':'month','operation':'count_rows'}),text('Two rows.')])
        out=execute(df,'Count monthly',lambda _:next(sequence))
        self.assertEqual(out['trace'][0]['result']['rows'][0]['value'],2)

if __name__=='__main__': unittest.main()
