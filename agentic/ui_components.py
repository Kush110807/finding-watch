"""Streamlit rendering only. The engine and comparison JSON are never rewritten."""
import json
import pandas as pd
import streamlit as st
from download_keys import evidence_key
from presentation import (summary, comparison_summary, comparison_table, label, number,
                          metric_definition, spec_description, filter_description,chart_safe,display_rows)


def evidence_download(data, filename, caption='Download complete, unmodified calculation evidence', *,
                      location, occurrence=0):
    """Download the original evidence without changing its JSON payload.

    Explicit widget identity is based on where a result is rendered, *not*
    its content. This is important for repeat calls returning equal results.
    """
    st.download_button(caption,json.dumps(data,indent=2,allow_nan=False,ensure_ascii=False),
                       filename,'application/json',key=evidence_key(location,occurrence))


def source_definition(spec, title='Submitted definition'):
    info=spec_description(spec)
    tool=spec.get('tool')
    args=spec.get('arguments',{})
    st.markdown(f'**{title}**')
    if tool=='inspect_dataset':
        st.caption('Operation: dataset structure and missing-value profile')
    elif tool=='filter_rows':
        st.caption('Operation: matching records (not an aggregate)')
    elif tool=='correlation':
        st.caption(f'Operation: Pearson correlation of “{args.get("x")}” and “{args.get("y")}”')
    elif tool=='time_trend':
        st.caption(f'Date: “{args.get("date_column")}” · Format: {args.get("date_format")} · Period: {args.get("frequency")} · Metric: {info["metric"]}')
    else:
        st.caption(f'Group: “{info["group"]}” · Metric: {info["metric"]}')
    if info['filters']:
        st.caption('Conditions (all apply): '+'; '.join(info['filters']))
    else:
        st.caption('Conditions: All records (no filters)')

def accounting(evidence):
    a=evidence.get('accounting',{})
    if a:
        st.caption(f'Input: {a.get("input_rows",0):,} records · Selected: {a.get("selected_rows",0):,} · Filtered out: {a.get("excluded_by_filters",0):,}')
    operation=a.get('operation_exclusions',{})
    for key,desc in (
        ('missing_group_labels_included','Rows with missing group labels (retained as an explicit group)'),
        ('missing_metric_excluded_from_values','Rows with missing numeric metrics (excluded only from values)'),
        ('missing_date_excluded','Rows with missing dates (excluded from time periods)'),
        ('excluded_incomplete_pairs_union','Rows missing at least one correlation value')):
        if operation.get(key): st.caption(f'{desc}: {operation[key]:,}')
    warnings=evidence.get('warnings',[])
    for warning in warnings:
        st.caption('Note: '+warning)


def analysis_result(output, *, heading='Calculated result', model_tool=False, question=None,
                    download_location, download_occurrence=0):
    st.subheader(heading)
    if question:
        st.caption('Submitted question: '+question)
    if model_tool:
        st.caption('Python tool calculation. Its relevance to the original question has not been independently verified.')
    st.markdown('### '+summary(output))
    ev=output.get('evidence',{})
    source_definition(ev.get('executed_spec',{}))
    accounting(ev)
    rows=output.get('rows',[])
    if rows:
        # Format exact Python int/null evidence BEFORE constructing pandas.
        # A pandas frame with [very_large_int, None] would otherwise coerce
        # the integer to an imprecise float before an after-the-fact fix.
        table=pd.DataFrame(display_rows(rows),dtype=str)
        st.dataframe(table,hide_index=True,use_container_width=True)
        st.caption('Table values are formatted from exact evidence before display; the JSON download preserves original numeric types and missing values.')
    if output['tool'] in ('grouped_summary','time_trend'):
        if chart_safe(rows[:30]) and len(rows)>=2:
            field='group_value' if output['tool']=='grouped_summary' else 'period_start'
            chart=pd.DataFrame({field:[label(r.get(field)) for r in rows[:30]],
                                'value':[r['value'] for r in rows[:30]]}).set_index(field)
            st.bar_chart(chart)
            if len(rows)>30: st.caption('Chart shows only the first 30 displayed groups/periods. Calculations used the full eligible dataset.')
        elif rows and not chart_safe(rows[:30]):
            st.caption('Chart omitted where values are missing or too large to display safely; refer to the exact result table and JSON.')
    display=ev.get('display',{})
    if display.get('truncated'):
        st.warning(f'Only {display.get("returned_rows")} of {display.get("total_result_rows")} result rows are displayed. The calculation did not use this truncated preview.')
    with st.expander('How this was calculated'):
        st.json(ev)
        st.json(output.get('metadata',{}))
    evidence_download(output,'analysis_result.json','Download result JSON',
                      location=download_location, occurrence=download_occurrence)


def comparison_result(result, *, heading='Confirmed comparison', filename='comparison.json',
                      download_location):
    st.subheader(heading)
    st.markdown('### '+comparison_summary(result))
    st.caption('Different record-inclusion assumptions answer different questions; a changed leader does not make the original calculation incorrect.')
    st.caption('Changed condition: '+str(result.get('changed_condition',{}).get('kind','')).title())
    diff=result.get('changed_condition',{})
    if diff.get('before'): st.caption('Before: '+filter_description(diff['before']))
    if diff.get('after'): st.caption('After: '+filter_description(diff['after']))
    a,b=st.columns(2)
    with a:
        source_definition(result['baseline_spec'],'Baseline · calculated')
        accounting(result['baseline']['evidence'])
    with b:
        source_definition(result['challenged_spec'],'Challenge · calculated')
        accounting(result['challenged']['evidence'])
    st.dataframe(pd.DataFrame(comparison_table(result)),hide_index=True,use_container_width=True)
    c=result['comparison']
    st.caption('Leaders based on all calculated groups, including any undisplayed groups: baseline = '
               +(', '.join(label(v) for v in c['baseline_leaders']) or 'none')
               +'; challenge = '+(', '.join(label(v) for v in c['challenged_leaders']) or 'none'))
    if c['display']['truncated']:
        st.warning(f'Comparison table truncated ({c["display"]["returned_groups"]} of {c["display"]["total_groups"]} groups). Conclusions and differences use the full result.')
    for warning in result.get('warnings',[]): st.caption('Note: '+warning)
    with st.expander('How this was calculated'):
        st.json(result)
    evidence_download(result,filename,'Download comparison JSON',location=download_location)
