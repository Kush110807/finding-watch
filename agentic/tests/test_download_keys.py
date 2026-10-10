"""Offline widget-identity contract; real UI collision tests are in test_app.py."""
import unittest
from download_keys import evidence_key


class DownloadKeyTests(unittest.TestCase):
    def test_distinct_locations_can_render_the_same_json_at_once(self):
        locations=['manual_result','clarified_result','ai_trace_result',
                   'manual_comparison','clarified_comparison','ai_comparison','ai_response']
        keys=[evidence_key(location,1 if location=='ai_trace_result' else 0)
              for location in locations]
        self.assertEqual(len(keys),len(set(keys)))

    def test_equal_repeated_trace_results_use_position_not_evidence_digest(self):
        # The same trace calculation can be repeated without its result changing.
        shared_evidence={'tool':'grouped_summary','rows':[{'group_value':'A','value':3}]}
        trace=[shared_evidence,shared_evidence,shared_evidence]
        keys=[evidence_key('ai_trace_result',i) for i,_ in enumerate(trace,1)]
        self.assertEqual(len(keys),len(set(keys)))
        self.assertEqual(evidence_key('ai_trace_result',2),keys[1])
        self.assertNotEqual(keys[0],keys[1])

    def test_stable_across_rerenders_and_independent_of_content(self):
        self.assertEqual(evidence_key('manual_result'),evidence_key('manual_result'))
        self.assertEqual(evidence_key('ai_response'),evidence_key('ai_response'))
        self.assertNotEqual(evidence_key('manual_result'),evidence_key('clarified_result'))

    def test_all_stage1_nontrace_locations_have_distinct_stable_keys(self):
        new_locations=['stage1_profile','stage1_local_result','suggested_comparison']
        existing=['manual_result','clarified_result','manual_comparison',
                  'clarified_comparison','ai_comparison','ai_response']
        keys=[evidence_key(location) for location in new_locations+existing]
        self.assertEqual(len(keys),len(set(keys)))
        for location in new_locations:
            with self.subTest(location=location):
                self.assertEqual(evidence_key(location),evidence_key(location,0))
                self.assertIn(location,evidence_key(location))
                for invalid in [-1,1,2,True,1.0,'1',None]:
                    with self.assertRaises(ValueError):
                        evidence_key(location,invalid)

    def test_primary_and_supporting_results_use_distinct_one_based_positions(self):
        # Even when primary and supporting evidence is byte-for-byte identical,
        # the two widgets exist simultaneously, once at each rendering surface.
        keys=[evidence_key(location,position)
              for location in ['ai_trace_result','ai_primary_result','ai_support_result']
              for position in [1,2,3]]
        self.assertEqual(len(keys),len(set(keys)))
        self.assertEqual(evidence_key('ai_primary_result',2),
                         evidence_key('ai_primary_result',2))
        self.assertNotEqual(evidence_key('ai_primary_result',2),
                            evidence_key('ai_support_result',2))
        for location in ('ai_primary_result','ai_support_result','ai_trace_result'):
            with self.subTest(location=location):
                for invalid in [0,-1,True,1.0,'1',None]:
                    with self.assertRaises(ValueError):
                        evidence_key(location,invalid)

    def test_selected_gemini_comparison_has_own_single_result_download(self):
        # The same evidence can coexist in original AI trace and a confirmed
        # user comparison; different rendering surfaces must remain distinct.
        selected=evidence_key('ai_selected_comparison')
        self.assertNotEqual(selected,evidence_key('ai_comparison'))
        self.assertNotEqual(selected,evidence_key('suggested_comparison'))
        self.assertNotEqual(selected,evidence_key('ai_primary_result',1))
        self.assertEqual(selected,evidence_key('ai_selected_comparison',0))
        with self.assertRaises(ValueError):
            evidence_key('ai_selected_comparison',1)

    def test_invalid_locations_and_positions_fail_explicitly(self):
        for location,occurrence in [('unknown',0),('manual_result',1),
                                     ('ai_trace_result',0),('ai_trace_result',-1),
                                     ('ai_trace_result',True),([],0)]:
            with self.subTest(location=location,occurrence=occurrence):
                with self.assertRaises(ValueError):evidence_key(location,occurrence)


if __name__=='__main__':
    unittest.main()
