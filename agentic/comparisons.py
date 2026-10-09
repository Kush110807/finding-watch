"""M2: strictly one-condition, same-dataset grouped-finding comparisons.

No LLM prose is treated as evidence. Comparison uses *complete* grouped results
from the M1 engine before the display cap is applied.
"""
import json
import math
from collections import Counter

from engine import (AnalysisError, _execute_spec_core, dataset_fingerprint,
                    column, numeric)
from specs import AnalysisSpec, SpecError


def _canonical_condition(condition):
    # Keep JSON types distinct: true is not 1, null is not absent.
    return json.dumps(condition, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False)


def _spec(raw):
    try:
        parsed = AnalysisSpec.parse(raw)
    except SpecError as exc:
        raise AnalysisError(str(exc)) from None
    if parsed.tool != 'grouped_summary':
        raise AnalysisError('M2 only compares grouped_summary specifications.')
    return parsed.as_dict()


def _difference(before, after):
    left = {_canonical_condition(c): c for c in before}
    right = {_canonical_condition(c): c for c in after}
    counts_before = Counter(_canonical_condition(c) for c in before)
    counts_after = Counter(_canonical_condition(c) for c in after)
    removed = list((counts_before - counts_after).elements())
    added = list((counts_after - counts_before).elements())
    if len(removed) == 0 and len(added) == 1:
        return {'kind':'added', 'before':None, 'after':right[added[0]]}
    if len(removed) == 1 and len(added) == 0:
        return {'kind':'removed', 'before':left[removed[0]], 'after':None}
    if len(removed) == 1 and len(added) == 1:
        return {'kind':'replaced', 'before':left[removed[0]], 'after':right[added[0]]}
    raise AnalysisError('Challenge must add, remove, or replace exactly one filter condition; no simultaneous changes or unchanged specifications.')


def prepare_comparison(df, baseline_raw, challenged_raw):
    """Validate comparison contract without executing either analysis.

    This is appropriate for model-proposed pending definitions that require a
    separate user confirmation prior to calculation.
    """
    baseline = _spec(baseline_raw)
    challenged = _spec(challenged_raw)
    if baseline['arguments'] != challenged['arguments']:
        raise AnalysisError('Challenge must preserve grouping, metric, aggregation and every other analytical argument.')
    arguments = baseline['arguments']
    column(df, arguments['group'])
    if arguments['operation'] != 'count_rows':
        numeric(df, arguments['metric'])
    for c in baseline['filters'] + challenged['filters']:
        column(df, c['field'])
    difference = _difference(baseline['filters'], challenged['filters'])
    fingerprint = dataset_fingerprint(df)
    return {'dataset_fingerprint_sha256':fingerprint,
            'baseline_spec':baseline, 'challenged_spec':challenged,
            'changed_condition':difference,
            'confirmation_required':True,
            'explanation':'The two definitions answer different inclusion questions. A changed leader does not establish that the original calculation was wrong.'}


def _group_key(value):
    # No index-based matching; separate missing labels and text/numeric types.
    return (type(value).__name__, json.dumps(value, ensure_ascii=False, allow_nan=False))


def _leaders(rows):
    eligible = [r for r in rows if r['value'] is not None]
    if not eligible:
        return []
    high = max(r['value'] for r in eligible)
    return [r['group_value'] for r in eligible if r['value'] == high]


def _delta(before, after):
    if before is None or after is None:
        return None
    if type(before) is int and type(after) is int:
        return after-before   # Arbitrarily large exact integers.
    try:
        value = float(after) - float(before)
    except (OverflowError, ValueError):
        raise AnalysisError('Difference cannot be computed within supported numeric precision.') from None
    if not math.isfinite(value):
        raise AnalysisError('Difference is non-finite; comparison is unsupported at this numeric scale.')
    return value


def execute_comparison(df, baseline_raw, challenged_raw, *, expected_fingerprint=None):
    """Calculate both independently on the same dataframe after validation.

    Missing/absent groups remain distinct from a valid numeric zero. Evidence
    includes complete matching, even when all visible tables are truncated.
    """
    plan = prepare_comparison(df, baseline_raw, challenged_raw)
    if expected_fingerprint is not None and expected_fingerprint != plan['dataset_fingerprint_sha256']:
        raise AnalysisError('Dataset changed after comparison preview. Reconfirm definitions on the current dataset.')
    base_result, base_full = _execute_spec_core(df, plan['baseline_spec'], include_full_rows=True)
    chall_result, chall_full = _execute_spec_core(df, plan['challenged_spec'], include_full_rows=True)
    # M1 never returns a truncated preview as a source for calculations.
    before = {_group_key(r['group_value']): r for r in base_full}
    after = {_group_key(r['group_value']): r for r in chall_full}
    # Preserve baseline order; append newly appearing groups in challenged order.
    keys = list(before) + [k for k in after if k not in before]
    full_comparison = []
    for key in keys:
        b = before.get(key)
        a = after.get(key)
        bv = b['value'] if b else None
        av = a['value'] if a else None
        full_comparison.append({
            'group_value':(b or a)['group_value'],
            'baseline_present':b is not None,
            'challenged_present':a is not None,
            'baseline_value':bv,
            'challenged_value':av,
            'difference_challenged_minus_baseline':_delta(bv, av) if b and a else None,
            'baseline_row_count':b['row_count'] if b else None,
            'challenged_row_count':a['row_count'] if a else None,
            'baseline_non_missing_metric_count':b.get('non_missing_metric_count') if b else None,
            'challenged_non_missing_metric_count':a.get('non_missing_metric_count') if a else None,
        })
    display_limit = min(plan['baseline_spec']['display_limit'],
                        plan['challenged_spec']['display_limit'])
    base_leaders = _leaders(base_full)
    challenged_leaders = _leaders(chall_full)
    # Leadership is determined from complete results, not visible slices.
    def keys_for(items):
        return {_group_key(v) for v in items}
    leader_changed = keys_for(base_leaders) != keys_for(challenged_leaders)
    notices = [plan['explanation']]
    if any(isinstance(x, int) and abs(x)>2**53 for r in full_comparison
           for x in (r['baseline_value'],r['challenged_value'],r['difference_challenged_minus_baseline'])):
        notices.append('Exact large integers may be rounded by JavaScript viewers or spreadsheets; use JSON-safe integer parsing.')
    if len(full_comparison)>display_limit:
        notices.append('Comparison preview truncated; all groups were used for leader and difference calculations.')
    return {'status':'completed',
            'dataset_fingerprint_sha256':plan['dataset_fingerprint_sha256'],
            'changed_condition':plan['changed_condition'],
            'baseline_spec':plan['baseline_spec'],
            'challenged_spec':plan['challenged_spec'],
            'baseline':base_result, 'challenged':chall_result,
            'comparison':{'all_results':full_comparison,
                          'displayed_results':full_comparison[:display_limit],
                          'display':{'total_groups':len(full_comparison),
                                     'returned_groups':min(len(full_comparison),display_limit),
                                     'truncated':len(full_comparison)>display_limit,
                                     'limit':display_limit},
                          'baseline_leaders':base_leaders,
                          'challenged_leaders':challenged_leaders,
                          'leader_changed':leader_changed},
            'accounting':{'baseline':base_result['evidence']['accounting'],
                          'challenged':chall_result['evidence']['accounting']},
            'warnings':notices,
            'calculation_evidence':'Deterministic Python grouped_summary on the full selected rows; model explanations are not verified.'}
