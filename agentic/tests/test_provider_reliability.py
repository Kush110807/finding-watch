"""Quota-free deterministic reliability tests; no SDK or network dependency."""
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from provider_reliability import (RequestPacer, RetryPolicy, ProviderFailure,
    classify, invoke_with_retries, _retry_delay)

class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.waits = []
        self.lock = threading.Lock()
    def monotonic(self):
        with self.lock:
            return self.t
    def sleep(self, seconds):
        with self.lock:
            self.waits.append(seconds)
            self.t += seconds

class APIProblem(Exception):
    def __init__(self, status, details=None, headers=None):
        self.code = status
        self.details = details or {}
        self.response = type('Response', (), {'headers': headers or {}})()
        super().__init__('PRIVATE KEY AND CSV PAYLOAD MUST NEVER LEAK')

class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.pacer = RequestPacer(clock=self.clock.monotonic, sleep=self.clock.sleep)
        self.policy = RetryPolicy(interval=13, request_budget=90, attempts=3)
        self.events = []
    def invoke(self, request, policy=None):
        return invoke_with_retries(request, policy=policy or self.policy,
            pacer=self.pacer, clock=self.clock.monotonic, sleep=self.clock.sleep,
            random_float=lambda:0.5, notify=self.events.append)
    def test_process_pacer_spaces_sequential_calls(self):
        self.assertEqual(self.invoke(lambda:1),1)
        self.assertEqual(self.invoke(lambda:2),2)
        self.assertEqual(self.clock.waits,[13.0])
        self.assertEqual(self.events[0]['event'],'waiting')
    def test_simultaneous_callers_get_distinct_slots(self):
        # Two workers race through the same lock-protected pacing state.
        gate = threading.Barrier(3)
        def run(i):
            gate.wait()
            return self.invoke(lambda:i)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(run,i) for i in (1,2)]
            gate.wait()
            self.assertEqual(set(f.result() for f in futures),{1,2})
        self.assertEqual(len(self.clock.waits),1)
        self.assertEqual(self.clock.waits[0],13)
    def test_503_then_success_is_two_provider_calls(self):
        calls=[]
        def request():
            calls.append(1)
            if len(calls)==1: raise APIProblem(503)
            return 'ok'
        self.assertEqual(self.invoke(request),'ok')
        self.assertEqual(len(calls),2)
        self.assertIn('retrying',[e['event'] for e in self.events])
    def test_504_and_transport_timeout_retry(self):
        for error in [APIProblem(504),TimeoutError('SECRET')]:
            with self.subTest(error=type(error)):
                self.setUp()
                attempts=[]
                def request():
                    attempts.append(1)
                    if len(attempts)==1: raise error
                    return 'ok'
                self.assertEqual(self.invoke(request),'ok')
                self.assertEqual(len(attempts),2)
    def test_429_ambiguous_has_only_one_retry(self):
        calls=[]
        def request():
            calls.append(1)
            raise APIProblem(429)
        with self.assertRaises(ProviderFailure) as cm:self.invoke(request)
        self.assertEqual(len(calls),2)
        self.assertEqual(cm.exception.category,'rate_limit_or_quota')
        self.assertEqual(cm.exception.attempts,2)
        self.assertNotIn('PRIVATE',str(cm.exception))
    def test_daily_quota_never_retries(self):
        error=APIProblem(429,{'details':[{'@type':'type.googleapis.com/google.rpc.QuotaFailure',
                 'violations':[{'quotaId':'GenerateRequestsPerDayPerProjectPerModel'}]}]})
        calls=[]
        def request():
            calls.append(1)
            raise error
        with self.assertRaises(ProviderFailure) as cm:self.invoke(request)
        self.assertEqual(cm.exception.category,'daily_quota')
        self.assertEqual(len(calls),1)
    def test_retry_after_header_and_structured_delay(self):
        error=APIProblem(503,{'details':[{'@type':'type.googleapis.com/google.rpc.RetryInfo',
                                          'retryDelay':'19s'}]}, {'Retry-After':'15'})
        self.assertEqual(_retry_delay(error),19)
        count=0
        def request():
            nonlocal count
            count+=1
            if count==1:raise error
            return 'ok'
        self.assertEqual(self.invoke(request),'ok')
        self.assertIn(19,self.clock.waits)
    def test_long_retry_guidance_stops_instead_of_early_retry(self):
        calls=[]
        error=APIProblem(429,{'details':[{'@type':'google.rpc.RetryInfo','retryDelay':'400s'}]})
        def request():
            calls.append(1)
            raise error
        with self.assertRaises(ProviderFailure):self.invoke(request)
        self.assertEqual(len(calls),1)
    def test_nonretryable_400_401_403_404(self):
        for status in [400,401,403,404]:
            with self.subTest(code=status):
                self.setUp()
                count=[]
                def request():
                    count.append(1)
                    raise APIProblem(status)
                with self.assertRaises(ProviderFailure) as cm:self.invoke(request)
                self.assertEqual(len(count),1)
                self.assertEqual(cm.exception.status,status)
    def test_unexpected_program_error_not_retried_or_leaked(self):
        count=[]
        def request():
            count.append(1)
            raise ValueError('SECRET')
        with self.assertRaises(ProviderFailure) as cm:self.invoke(request)
        self.assertEqual(len(count),1)
        self.assertNotIn('SECRET',str(cm.exception))
    def test_finite_attempts_and_budget(self):
        count=[]
        def request():
            count.append(1)
            raise APIProblem(503)
        with self.assertRaises(ProviderFailure):self.invoke(request)
        self.assertEqual(len(count),3)
        self.setUp()
        policy=RetryPolicy(interval=13, attempts=4, request_budget=16)
        with self.assertRaises(ProviderFailure):self.invoke(request,policy=policy)
        self.assertLessEqual(self.clock.monotonic(),16)
    def test_late_success_is_not_marked_as_completed(self):
        policy=RetryPolicy(interval=13, attempts=1, request_budget=15)
        def request():
            self.clock.sleep(16)
            return 'late data'
        with self.assertRaises(ProviderFailure) as cm:self.invoke(request,policy=policy)
        self.assertEqual(cm.exception.category,'time_budget')
        self.assertEqual(cm.exception.attempts,1)
    def test_queued_request_that_cannot_fit_budget_is_not_counted(self):
        self.invoke(lambda:'first')
        count=[]
        def request():
            count.append(1)
            return 'unexpected'
        with self.assertRaises(ProviderFailure) as cm:self.invoke(
            request,policy=RetryPolicy(interval=13, attempts=2, request_budget=5))
        self.assertEqual(count,[])
        self.assertEqual(cm.exception.attempts,0)
        self.assertEqual(cm.exception.category,'time_budget')

    def test_analysis_level_budget_counts_retries_across_requests(self):
        counter=[0]
        def guard():
            if counter[0]>=2: return False
            counter[0]+=1
            return True
        self.assertEqual(invoke_with_retries(lambda:'ok',policy=self.policy,
            pacer=self.pacer,clock=self.clock.monotonic,sleep=self.clock.sleep,
            request_guard=guard),'ok')
        self.assertEqual(invoke_with_retries(lambda:'ok',policy=self.policy,
            pacer=self.pacer,clock=self.clock.monotonic,sleep=self.clock.sleep,
            request_guard=guard),'ok')
        with self.assertRaises(ProviderFailure) as cm:
            invoke_with_retries(lambda:'should not run',policy=self.policy,
                pacer=self.pacer,clock=self.clock.monotonic,sleep=self.clock.sleep,
                request_guard=guard)
        self.assertEqual(cm.exception.category,'analysis_request_limit')
        self.assertEqual(counter[0],2)
        self.assertEqual(cm.exception.attempts,0)

    def test_safe_diagnostics_only(self):
        with self.assertRaises(ProviderFailure) as cm:self.invoke(lambda:(_ for _ in ()).throw(APIProblem(400)))
        self.assertEqual(cm.exception.diagnostic()['http_status'],400)
        self.assertNotIn('PRIVATE',str(cm.exception.diagnostic()))
    def test_error_classification(self):
        self.assertEqual(classify(APIProblem(400))[0],'invalid_request')
        self.assertEqual(classify(APIProblem(429))[0],'rate_limit_or_quota')
        self.assertEqual(classify(APIProblem(504))[0],'provider_transient')
        self.assertEqual(classify(TimeoutError())[0],'transport_timeout_or_connection')

if __name__=='__main__':unittest.main()
