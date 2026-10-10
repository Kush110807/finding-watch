"""Pure Stage 1 display routing. Never authorizes model decisions or alters evidence."""
from collections.abc import Mapping

TOOL_NAMES = {'inspect_dataset': 'Dataset inspection', 'filter_rows': 'Matching records',
              'grouped_summary': 'Grouped summary', 'time_trend': 'Time analysis',
              'correlation': 'Numeric relationship'}


def suggested_questions(columns, numeric, frame):
    """Build bounded local examples from the CURRENT schema; never route free text."""
    proposals = []
    cols = list(columns)
    categoricals = [c for c in cols if c not in numeric and not any(
        hint in c.casefold() for hint in ('date', 'time', 'id', 'code'))]
    # Prefer a repeatable, low-cardinality grouping. This is a UI suggestion,
    # not an inferred business definition: the user explicitly submits it.
    groups = [c for c in categoricals if 1 < frame[c].nunique(dropna=False) <= min(30, max(2, len(frame)))]
    if groups:
        group = groups[0]
        preferred = sorted(numeric, key=lambda c: (0 if 'revenue' in c.casefold() else
                   1 if any(x in c.casefold() for x in ('amount', 'sales', 'units')) else 2, cols.index(c)))
        if preferred:
            metric = preferred[0]
            proposals.append({'question': f'Which {group} has the highest total of {metric}?',
                              'tool': 'grouped_summary', 'arguments': {'group':group,'metric':metric,'operation':'sum'}})
        proposals.append({'question': f'How many records are there for each {group}?',
                          'tool':'grouped_summary','arguments':{'group':group,'operation':'count_rows'}})
    for c in cols:
        if 'date' in c.casefold() or 'time' in c.casefold():
            proposals.append({'question':f'How many records are there each month by {c}?',
                              'tool':'time_trend','arguments':{'date_column':c,'date_format':'%Y-%m-%d',
                                                             'frequency':'month','operation':'count_rows'}})
            break
    return proposals[:3]


def calculated_trace_entries(trace):
    result=[]
    for index,event in enumerate(trace or [],1):
        if not isinstance(event,Mapping):continue
        output=event.get('result')
        if (isinstance(output,Mapping) and isinstance(output.get('rows'),list)
                and isinstance(output.get('evidence'),Mapping)
                and output['evidence'].get('calculation_status')=='completed'):
            result.append((index,event))
    return result


def primary_candidates(trace):
    """Inspection supports analysis; never choose among multiple candidates."""
    completed=calculated_trace_entries(trace)
    analytical=[entry for entry in completed if entry[1].get('tool')!='inspect_dataset']
    return analytical or completed


def candidate_title(index,event):
    output=event['result']
    spec=output.get('evidence',{}).get('executed_spec',{})
    args=spec.get('arguments',{})
    suffix=(', '.join(str(args[x]) for x in ('group','metric') if x in args and args[x] is not None))
    return f'{index}. {TOOL_NAMES.get(event.get("tool"), "Calculation")}' + (f' · {suffix}' if suffix else '')


def two_group_difference(output):
    """Exact value comparison for two complete, distinct, numeric groups."""
    if output.get('tool')!='grouped_summary':return None
    if output.get('evidence',{}).get('display',{}).get('truncated'):return None
    rows=output.get('rows',[])
    if len(rows)!=2 or any(type(row.get('value')) not in (int,float) for row in rows):return None
    if any(type(row['value']) is float and (row['value']!=row['value'] or abs(row['value'])==float('inf')) for row in rows):return None
    first,second=sorted(rows,key=lambda r:r['value'],reverse=True)
    return {'leader':first.get('group_value'),'runner_up':second.get('group_value'),
            'difference':first['value']-second['value'], 'tie':first['value']==second['value']}
