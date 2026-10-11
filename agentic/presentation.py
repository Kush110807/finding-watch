"""Pure presentation contracts for Finding Watch; never alters calculation evidence.

No money, product, order or unit semantics are inferred from column names.
UI callers must preserve the source JSON and require explicit user selection.
"""
from collections.abc import Mapping
from datetime import datetime


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
    return f'{verbs.get(operation, operation)} of “{metric}”'


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


def readable_measure(spec):
    """Brief metric phrase based only on the executed operation and column name.

    No currency or business units are inferred from a column name.
    """
    args=spec.get('arguments',{})
    operation=args.get('operation')
    metric=args.get('metric')
    if operation=='count_rows':
        return 'record count'
    prefix={'sum':'total','mean':'average','min':'minimum','max':'maximum'}.get(operation)
    if prefix is None or not isinstance(metric,str):
        return 'calculated value'
    return f'{prefix} {metric}'


def observed_period_label(period, frequency):
    """Display an actual observed engine period; never generate empty buckets."""
    try:
        date=datetime.strptime(period,'%Y-%m-%d')
        if frequency=='month':return date.strftime('%b %Y')
        if frequency=='week':return 'Week of '+date.strftime('%d %b %Y')
        return date.strftime('%d %b %Y')
    except (ValueError,TypeError):
        return str(period)



def time_chart_points(rows, frequency):
    """Observed time buckets ordered by their real start dates, not text labels.

    Missing months/weeks/days are never fabricated. Chart callers should use
    the datetime value as a *temporal* x-axis and should not interpolate gaps.
    Numeric values are kept as supplied; the caller applies chart_safe first.
    """
    if frequency not in ('month','week','day'):
        return None
    points=[]
    for row in rows:
        try:
            instant=datetime.strptime(row['period_start'],'%Y-%m-%d')
        except (KeyError,ValueError,TypeError):
            return None
        points.append({'Period':instant,'Value':row.get('value')})
    points.sort(key=lambda item:item['Period'])
    return points


def grouping_phrase(column):
    """Readable group labels without assuming product, quantity or units."""
    name=str(column).strip()
    common={'category':'categories','region':'regions','city':'cities'}
    return common.get(name.lower(),f'“{name}” values')


def clarification_definition(group, operation, metric=None):
    """Preview a user's explicit choice; not an executable model proposal."""
    if not group or not operation:
        return None
    args={'group':group,'operation':operation}
    if metric is not None:
        args['metric']=metric
    return f'Compare {grouping_phrase(group)} by {readable_measure({"arguments":args})}.'


def same_numeric_grouping_explanation(group, metric):
    if group is not None and metric is not None and group==metric:
        return (f'“{group}” is both the grouping column and the numeric measure. '
                'Each distinct numeric value becomes a group, then that same column is calculated within each group. '
                'Check that this is the comparison you want before submitting.')
    return None

def summary(output):
    """Readable facts from completed evidence, not model prose or guessing."""
    tool=output['tool']; rows=output.get('rows',[])
    evidence=output.get('evidence',{}); account=evidence.get('accounting',{})
    display=evidence.get('display',{}); spec=evidence.get('executed_spec',{})
    if tool=='inspect_dataset':
        columns=output.get('metadata',{}).get('total_columns',len(rows))
        return f'Dataset overview: {account.get("selected_rows",0):,} records across {columns:,} columns.'
    if tool=='filter_rows':
        return f'{account.get("selected_rows",0):,} records match the selected conditions.'
    if tool=='grouped_summary':
        if display.get('truncated'):
            return (f'{display.get("returned_rows",len(rows)):,} of '
                    f'{display.get("total_result_rows",len(rows)):,} groups shown. '
                    'A leading group cannot be established from a partial result.')
        valued=[r for r in rows if r.get('value') is not None]
        if not valued:
            return 'No numeric result is available for the selected groups.'
        highest=max(r['value'] for r in valued)
        leaders=[label(r.get('group_value')) for r in valued if r['value']==highest]
        measure=readable_measure(spec)
        if len(leaders)>1:
            return f'{", ".join(leaders)} tie for the highest {measure}.'
        return f'{leaders[0]} leads in {measure}.'
    if tool=='time_trend':
        frequency=spec.get('arguments',{}).get('frequency','period')
        n=display.get('total_result_rows',len(rows))
        if display.get('truncated'):
            return f'{len(rows)} of {n} observed time periods shown; the result is incomplete.'
        if not rows or not any(r.get('value') is not None for r in rows):
            return 'No numeric time-period result is available.'
        return f'{metric_definition(spec)} calculated across {n:,} observed {frequency} periods.'
    if tool=='correlation':
        usable=account.get('operation_exclusions',{}).get('complete_pairs',output.get('metadata',{}).get('complete_pairs',0))
        if rows and rows[0].get('pearson_r') is not None:
            return f'Pearson correlation: {number(rows[0]["pearson_r"])} using {usable:,} complete pairs.'
        return 'No valid Pearson correlation result is available.'
    return 'Calculation returned; inspect supporting evidence.'


def visible_result_rows(output, cap=12):
    """Format precise original evidence scalars BEFORE DataFrame inference."""
    rows=output.get('rows',[])[:cap]
    spec=output.get('evidence',{}).get('executed_spec',{})
    args=spec.get('arguments',{})
    tool=output.get('tool')
    if tool=='grouped_summary':
        return simple_group_table(rows,spec)
    if tool=='time_trend':
        columns=unique_presentation_columns([('period_start','Period'),('value',metric_definition(spec))])
        return [{columns['period_start']:observed_period_label(row.get('period_start'),args.get('frequency')),
                 columns['value']:number(row.get('value'))} for row in rows]
    if tool=='correlation':
        return [{'First column':str(row.get('x')),'Second column':str(row.get('y')),
                 'Pearson correlation (r)':number(row.get('pearson_r'))} for row in rows]
    if tool=='inspect_dataset':
        return [{'Column':str(row.get('column')),
                 'Detected type':str(row.get('dtype')),
                 'Missing values':number(row.get('missing')),
                 'Distinct non-missing values':number(row.get('unique_non_missing'))} for row in rows]
    if tool=='filter_rows':
        return [{str(key):('Missing' if value is None else number(value)) for key,value in row.items()}
                for row in rows]
    return display_rows(rows)


def important_notices(output):
    """Material calculation exclusions only; avoids duplicating engine notices."""
    ev=output.get('evidence',{}); op=ev.get('accounting',{}).get('operation_exclusions',{})
    notices=[]
    for key,desc in (
        ('missing_group_labels_included','records have no group label and form a separate missing-label group'),
        ('missing_metric_excluded_from_values','records lack a numeric value; excluded from calculated values'),
        ('missing_date_excluded','records lack a date and were excluded from period calculations'),
        ('missing_metric_with_valid_date_excluded_from_values','records have a date but no numeric value; excluded from period values'),
        ('excluded_incomplete_pairs_union','records lack one or both correlation values and were excluded')):
        if op.get(key):notices.append(f'{op[key]:,} {desc}.')
    warnings=ev.get('warnings',[])
    for warning in warnings:
        if ('tie for highest' in warning or 'missing metric values' in warning or
            'missing date(s)' in warning or 'missing group label' in warning or
            'Pearson correlation is not evidence of causation' in warning or
            'Output display truncated' in warning):
            continue
        notices.append(warning)
    if output.get('tool')=='correlation':
        notices.append('Correlation measures association, not cause and effect.')
    return list(dict.fromkeys(notices))

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


def display_rows(rows):
    """Format ORIGINAL evidence scalars before pandas gets an opportunity to
    infer a float column from a large integer beside a null.

    Presentation strings are intentionally not numeric table data: the exact
    original evidence remains available for calculations and JSON downloads.
    """
    rendered=[]
    for record in rows:
        item={}
        for key,value in record.items():
            if key=='group_value':
                item[key]=label(value)
            elif value is None:
                item[key]='No numeric value' if key=='value' else 'Missing'
            elif type(value) is int:
                item[key]=number(value)
            elif type(value) is float:
                item[key]=number(value)
            else:
                item[key]=str(value)
        rendered.append(item)
    return rendered


def unique_presentation_columns(columns):
    """Map distinct evidence fields to distinct UI labels, even when names collide.

    The last (usually calculated) field keeps its natural label. Earlier fields
    receive role-qualified labels where needed. This operates only on the UI;
    original result keys and their JSON representation are never modified.
    """
    roles={'group_value':'group', 'period_start':'period', 'value':'calculated value',
           'row_count':'record count', 'non_missing_metric_count':'numeric count'}
    used=set()
    resolved={}
    for field,title in reversed(columns):
        candidate=str(title)
        if candidate in used:
            candidate=f'{candidate} ({roles.get(field, field.replace("_", " "))})'
        base=candidate
        index=2
        while candidate in used:
            candidate=f'{base} ({index})'
            index+=1
        used.add(candidate)
        resolved[field]=candidate
    return resolved


def group_column_labels(spec, *, detailed=False):
    """Human-readable, collision-safe grouped-result column headings."""
    group=spec.get('arguments',{}).get('group') or 'Group'
    columns=[('group_value',str(group)),('value',readable_measure(spec).capitalize())]
    if detailed:
        columns.extend([('row_count','Records in group'),
                        ('non_missing_metric_count','Records with numeric values')])
    return unique_presentation_columns(columns)


def simple_group_table(rows, spec):
    """Precisely formatted grouped values with two distinct display headings."""
    headings=group_column_labels(spec)
    return [{headings['group_value']:record['group_value'],
             headings['value']:record['value']} for record in display_rows(rows)]


def detailed_group_table(rows, spec):
    """Detailed accounting, formatted before pandas inference or column renaming."""
    rendered=display_rows(rows)
    keys=list(dict.fromkeys(key for row in rendered for key in row))
    labels=group_column_labels(spec,detailed=True)
    for key in keys:
        if key not in labels:
            labels[key]=key
    unique=unique_presentation_columns([(key,labels[key]) for key in keys])
    return [{unique[key]:row.get(key,'Missing') for key in keys} for row in rendered]


def preview_counts(output, *, cap=12):
    """Count matching, engine-returned and UI-visible rows separately.

    A result may be truncated once by the engine and again by the interface.
    These counts never depend on rows omitted from the engine response.
    """
    evidence=output.get('evidence',{})
    matches=evidence.get('accounting',{}).get('selected_rows',0)
    returned=len(output.get('rows',[]))
    return {'matched':matches,'returned':returned,'visible':min(returned,cap)}


def confirmed_comparison_matches(stored, plan, binding):
    """Approval status depends on the currently presented exact plan/baseline.

    This does not remove approved evidence from state; it prevents stale data
    from being presented as the result of edited controls or a different source.
    """
    return bool(stored and plan and stored.get('plan')==plan
                and stored.get('baseline_binding')==binding
                and stored.get('result',{}).get('status')=='completed')
