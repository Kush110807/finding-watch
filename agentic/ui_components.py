"""Streamlit rendering only. The engine and comparison JSON are never rewritten."""
import json
import pandas as pd
import streamlit as st
from download_keys import evidence_key
from stage1_logic import two_group_difference
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
    """Conclusion-first rendering; never converts the original evidence."""
    st.subheader(heading)
    st.markdown('### '+summary(output))
    ev=output.get('evidence',{})
    spec=ev.get('executed_spec',{})
    info=spec_description(spec)
    acct=ev.get('accounting',{})
    tool=output.get('tool')
    if tool=='grouped_summary':
        st.caption(f'**Definition:** {info["metric"]} · by “{info["group"]}”')
    elif tool=='time_trend':
        st.caption('**Definition:** '+info['metric']+' · by '+str(spec.get('arguments',{}).get('frequency')))
    elif tool=='correlation':
        st.caption('**Definition:** Pearson correlation · '+str(spec.get('arguments',{}).get('x'))+
                   ' against '+str(spec.get('arguments',{}).get('y')))
    else:
        st.caption('**Definition:** '+('Matching records' if tool=='filter_rows' else 'Column and dataset inspection'))
    scope=f'{acct.get("selected_rows",0):,} selected of {acct.get("input_rows",0):,} records'
    if info['filters']:
        scope+=' · '+'; '.join(info['filters'])
    else:
        scope+=' · No filters'
    st.caption(scope)
    if model_tool:
        st.caption('This calculation is reproducible. Its relevance to your question and any model interpretation have not been independently verified.')
    diff=two_group_difference(output)
    if diff and not diff['tie']:
        st.caption(f'**Difference between the two groups:** {number(diff["difference"])} (same source-column units).')
    operation=acct.get('operation_exclusions',{})
    for key,desc in [('missing_metric_excluded_from_values','records had no numeric metric; they did not contribute to values'),
                     ('missing_date_excluded','records had no valid date and were excluded from time periods'),
                     ('excluded_incomplete_pairs_union','records lacked at least one correlation value')]:
        if operation.get(key):
            st.warning(f'{operation[key]:,} {desc}.')
    for warning in ev.get('warnings',[]):st.warning(str(warning))
    rows=output.get('rows',[])
    if rows:
        table=pd.DataFrame(display_rows(rows[:12]),dtype=str)
        friendly={'group_value': str(info['group']) if info['group'] is not None else 'Group',
                  'value':info['metric'],'period_start':'Period',
                  'non_missing_metric_count':'Records with numeric value',
                  'record_count':'Records','pearson_r':'Pearson correlation (r)',
                  'group_count':'Groups'}
        table=table.rename(columns=friendly)
        st.dataframe(table,hide_index=True,use_container_width=True,
                     height=min(40+35*(len(table)+1),420))
        if len(rows)>12:
            st.caption(f'Showing 12 of {len(rows):,} returned rows. All returned values remain in the evidence download.')
    if tool in ('grouped_summary','time_trend') and 2<=len(rows)<=8 and chart_safe(rows):
        axis='group_value' if tool=='grouped_summary' else 'period_start'
        chart=pd.DataFrame({'Label':[label(r.get(axis)) for r in rows],
                            'Calculated value':[r['value'] for r in rows]}).set_index('Label')
        st.bar_chart(chart,height=190)
    elif tool in ('grouped_summary','time_trend') and rows and not chart_safe(rows):
        st.caption('Chart omitted to prevent rounding large exact values or misrepresenting missing results. Use the precise table instead.')
    display=ev.get('display',{})
    if display.get('truncated'):
        st.warning(f'Only {display.get("returned_rows")} of {display.get("total_result_rows")} result rows were returned. The calculation used all selected records; undisplayed groups may change the ranking.')
    with st.expander('How this was calculated',expanded=False):
        source_definition(spec)
        accounting(ev)
        st.json(ev)
        st.json(output.get('metadata',{}))
        evidence_download(output,'analysis_result.json','Download original result JSON',
                          location=download_location,occurrence=download_occurrence)


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
