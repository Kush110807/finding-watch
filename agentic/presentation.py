"""Pure presentation contracts for Finding Watch; never alters calculation evidence.

No money, product, order or unit semantics are inferred from column names.
UI callers must preserve the source JSON and require explicit user selection.
"""
from collections.abc import Mapping


def label(value):
    return '(missing group label)' if value is None else str(value)


def number(value):
    if value is None:
        return 'No numeric value'
    if type(value) is int:
        return f'{value:,}'
    if type(value) is float:
        return f'{value:,.10g}'
    return str(value)


def metric_definition(spec):
    args=spec.get('arguments', {})
    operation=args.get('operation')
    metric=args.get('metric')
    if operation=='count_rows':
        return 'Record count (rows)'
    verbs={'sum':'Total','mean':'Average','min':'Minimum','max':'Maximum'}
    return f'{verbs.get(operation, operation)} of “{metric}” (source column)'


def filter_description(condition):
    op={'eq':'equals','ne':'does not equal','gt':'is greater than','ge':'is at least',
        'lt':'is less than','le':'is at most','contains':'contains',
        'is_missing':'is missing','not_missing':'is not missing'}
    if not isinstance(condition, Mapping):
        return 'Invalid filter definition'
    text=f'“{condition.get("field", "?")}” {op.get(condition.get("operator"), "has unsupported operator")}'
    if condition.get('operator') not in ('is_missing','not_missing'):
        text+=f' {condition.get("value")!r}'
    return text


def spec_description(spec):
    args=spec.get('arguments', {})
    group=args.get('group')
    return {'group':group, 'metric':metric_definition(spec),
            'filters':[filter_description(f) for f in spec.get('filters',[])],
            'display_limit':spec.get('display_limit')}


def summary(output):
    """Conclusion derived exclusively from returned deterministic tool rows.

    Truncated grouped output cannot establish global leaders: their ordering is
    not a substitute for full result evidence.
    """
    tool=output['tool']; rows=output.get('rows',[])
    evidence=output.get('evidence',{}); account=evidence.get('accounting',{})
    display=evidence.get('display',{})
    if tool=='inspect_dataset':
        return f'Dataset contains {account.get("input_rows",output.get("metadata",{}).get("total_rows",0)):,} records and {len(rows)} displayed column profiles.'
    if tool=='filter_rows':
        return f'{account.get("selected_rows",0):,} records match the submitted conditions.'
    if tool=='grouped_summary':
        if display.get('truncated'):
            return f'{display.get("returned_rows",len(rows)):,} of {display.get("total_result_rows",len(rows)):,} groups displayed. Global leader cannot be confirmed from this preview.'
        valued=[r for r in rows if r.get('value') is not None]
        if not valued:
            return 'No numeric group result is available; the selected records may contain only missing metric values.'
        highest=max(r['value'] for r in valued)
        leaders=[label(r.get('group_value')) for r in valued if r['value']==highest]
        if len(leaders)>1:
            return f'{len(leaders)} groups tie for the highest {metric_definition(evidence.get("executed_spec",{})).lower()}: {", ".join(leaders)} ({number(highest)}).'
        return f'{leaders[0]} has the highest {metric_definition(evidence.get("executed_spec",{})).lower()}: {number(highest)}.'
    if tool=='time_trend':
        if display.get('truncated'):
            return f'{len(rows)} time periods displayed; no full-period ranking is claimed.'
        if not rows or not any(r.get('value') is not None for r in rows):
            return 'No numeric time-period result is available.'
        return f'{len(rows):,} time periods calculated. Values are shown below without assuming a trend direction.'
    if tool=='correlation':
        if rows and rows[0].get('pearson_r') is not None:
            return f'Pearson correlation r = {number(rows[0]["pearson_r"])}. Association does not establish causation.'
        return 'No valid numeric relationship result.'
    return 'Calculation returned; inspect supporting evidence.'


def comparison_summary(comparison):
    c=comparison['comparison']
    before=c['baseline_leaders']; after=c['challenged_leaders']
    def leaders(values):
        return ', '.join(label(v) for v in values) if values else 'No numeric leader'
    if c['leader_changed']:
        return f'Leading group changed: {leaders(before)} → {leaders(after)}.'
    return f'Leading group unchanged: {leaders(after)}.'


def comparison_table(comparison):
    out=[]
    for r in comparison['comparison']['displayed_results']:
        out.append({'Group':label(r['group_value']),
                    'All baseline':number(r['baseline_value']) if r['baseline_present'] else 'Absent group',
                    'Challenged':number(r['challenged_value']) if r['challenged_present'] else 'Absent group',
                    'Difference':number(r['difference_challenged_minus_baseline']) if r['difference_challenged_minus_baseline'] is not None else 'Not comparable'})
    return out


def metric_choices(columns, numeric):
    """Only actual numeric columns may be metrics. Never infer currency/units."""
    options={'Record count (rows)': {'operation':'count_rows','metric':None}}
    for col in numeric:
        options[f'Total of “{col}”']={'operation':'sum','metric':col}
        options[f'Average of “{col}”']={'operation':'mean','metric':col}
    return options


def group_candidates(columns, question):
    """Sort possible grouping columns for discovery; never choose one."""
    hints=('product','item','sku','category','brand','group','type') if 'product' in question.lower() else ()
    def rank(col):
        low=col.lower()
        return (0 if any(h in low for h in hints) else 1, columns.index(col))
    return sorted(columns,key=rank)


def missing_product_context(columns, question):
    q=question.casefold()
    return ('product' in q and not any('product' in c.casefold() for c in columns))


def chart_safe(rows):
    """Avoid converting exact >2**53 integer evidence into JS float charts."""
    return bool(rows) and all(type(r.get('value')) in (int,float)
                              and abs(r['value'])<=2**53 for r in rows)
