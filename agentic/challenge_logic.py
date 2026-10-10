"""Stage 3 presentation/input contracts; no new analytic operations.

The validated M2 comparison remains authoritative. No model prose is executed.
"""
import hashlib
import json
import math
import re
from pandas.api.types import is_numeric_dtype, is_bool_dtype
from engine import AnalysisError
from presentation import filter_description, metric_definition, label, number

FRIENDLY_OPERATORS = {'eq':'is', 'ne':'is not', 'gt':'is greater than',
                      'ge':'is at least', 'lt':'is less than', 'le':'is at most',
                      'contains':'contains text', 'is_missing':'is missing',
                      'not_missing':'is not missing'}


def identity(binding):
    """Stable per submitted finding, including the submission occurrence."""
    return hashlib.sha256(json.dumps(binding, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, default=str).encode('utf-8')).hexdigest()[:16]


def column_operators(df, field):
    if field not in df.columns:
        raise AnalysisError('Choose an existing dataset column.')
    s=df[field]
    if is_bool_dtype(s):
        return ('eq','ne','is_missing','not_missing')
    if is_numeric_dtype(s):
        return ('eq','ne','gt','ge','lt','le','is_missing','not_missing')
    return ('eq','ne','contains','is_missing','not_missing')


def categorical_values(df, field, cap=60):
    """Preserve concrete text/bool identities; None is not the empty string."""
    if field not in df.columns:
        raise AnalysisError('Choose an existing dataset column.')
    s=df[field]
    if is_numeric_dtype(s) and not is_bool_dtype(s):
        return None
    values=s.dropna().unique().tolist()
    values=[x.item() if hasattr(x,'item') else x for x in values]
    if len(values)>cap:
        return None
    return values


def parse_numeric(text):
    if not isinstance(text,str) or not text.strip():
        raise AnalysisError('Enter a number for this condition.')
    raw=text.strip()
    if re.fullmatch(r'[+-]?\d+',raw):
        value=int(raw)
        if abs(value)>2**53:
            raise AnalysisError('Numeric filter values larger than 2^53 are unsupported by the current comparison engine.')
        return value
    try:
        value=float(raw)
    except ValueError:
        raise AnalysisError('Enter a valid finite number.') from None
    if not math.isfinite(value) or abs(value)>2**53:
        raise AnalysisError('Enter a finite number within the supported comparison precision.')
    return value


def changed_filters(original, action, *, index=None, condition=None):
    """Construct exactly one declared add, remove, or replace operation."""
    existing=[dict(f) for f in original]
    if action=='Add condition':
        if len(existing)>=8:
            raise AnalysisError('A finding can contain at most eight conditions.')
        if condition is None:
            raise AnalysisError('Choose a complete condition before reviewing.')
        return existing+[dict(condition)]
    if action in ('Remove condition','Replace condition'):
        if type(index) is not int or index<0 or index>=len(existing):
            raise AnalysisError('Select the existing condition to change.')
        if action=='Remove condition':
            return existing[:index]+existing[index+1:]
        if condition is None:
            raise AnalysisError('Choose a complete replacement condition.')
        existing[index]=dict(condition)
        return existing
    raise AnalysisError('Choose one change: add, replace, or remove.')


def definition_line(spec):
    filters=spec.get('filters',[])
    return '; '.join(filter_description(f) for f in filters) if filters else 'All records'


def unchanged_line(spec):
    args=spec['arguments']
    return f'{metric_definition(spec)} by “{args["group"]}”'


def conclusion(result):
    """All leaders come from M2's complete group results, never display rows."""
    c=result['comparison']
    before=c['baseline_leaders']; after=c['challenged_leaders']
    def names(v):
        return ', '.join(label(x) for x in v)
    if not after:
        return 'No numeric leader can be established for the alternative.'
    if len(after)>1:
        return f'The alternative has a tie: {names(after)}.'
    if not before:
        return f'The alternative leads with {names(after)}; the original had no numeric leader.'
    if set(json.dumps(x,sort_keys=True,default=str) for x in before)!=set(json.dumps(x,sort_keys=True,default=str) for x in after):
        return f'The leader changes from {names(before)} to {names(after)}.'
    return f'{names(after)} remains the leader.'


def comparison_display_rows(result):
    """Format exact scalars BEFORE DataFrame inference; distinguish absent/null/zero."""
    group=str(result['baseline_spec']['arguments']['group']).replace('_',' ').capitalize()
    return [{group:label(r['group_value']),
             'Original':number(r['baseline_value']) if r['baseline_present'] else 'Absent group',
             'Alternative':number(r['challenged_value']) if r['challenged_present'] else 'Absent group',
             'Difference':number(r['difference_challenged_minus_baseline'])
                if r['difference_challenged_minus_baseline'] is not None else 'Not comparable'}
            for r in result['comparison']['displayed_results']]
