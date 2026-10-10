"""Streamlit rendering only. The engine and comparison JSON are never rewritten."""
import json
import pandas as pd
import streamlit as st
from download_keys import evidence_key
from stage1_logic import two_group_difference
from presentation import (summary, comparison_summary, comparison_table, label, number,
                          metric_definition, spec_description, filter_description,chart_safe,display_rows,readable_measure,simple_group_table,visible_result_rows,important_notices,observed_period_label)


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
    """Five evidence-first tools: friendly result; original JSON stays intact."""
    tool=output.get('tool')
    ev=output.get('evidence',{})
    spec=ev.get('executed_spec',{})
    args=spec.get('arguments',{})
    info=spec_description(spec)
    account=ev.get('accounting',{})
    display=ev.get('display',{})
    rows=output.get('rows',[])
    st.subheader(heading)
    st.markdown('### '+summary(output))
    if tool=='grouped_summary':
        st.caption(f'**Measure:** {metric_definition(spec)} · **Grouped by:** {args.get("group")}')
    elif tool=='time_trend':
        st.caption(f'**Measure:** {metric_definition(spec)} · **Date column:** {args.get("date_column")} · '
                   f'**Date format:** {args.get("date_format")} · **Interval:** {args.get("frequency")}')
        st.caption('Only periods present in the data are shown; missing periods are not treated as zero.')
    elif tool=='correlation':
        st.caption(f'**Columns:** {args.get("x")} and {args.get("y")} · '
                   f'**Complete pairs:** {account.get("operation_exclusions",{}).get("complete_pairs",0):,}')
    elif tool=='filter_rows':
        st.caption(f'**Matching records:** {account.get("selected_rows",0):,} · '
                   f'**Displayed:** {len(rows):,} of {display.get("total_result_rows",len(rows)):,}')
    elif tool=='inspect_dataset':
        meta=output.get('metadata',{})
        missing=sum(int(row.get('missing',0)) for row in rows)
        st.caption(f'**Columns:** {meta.get("total_columns",len(rows)):,} · '
                   f'**Empty cells in displayed profiles:** {missing:,} · '
                   f'**Duplicate records:** {meta.get("duplicate_rows",0):,}')
        st.caption('Profiling describes structure and missing cells; it does not validate data accuracy.')
    if info['filters']:
        st.caption(f'{account.get("selected_rows",0):,} of {account.get("input_rows",0):,} records selected · '
                   +'Conditions: '+'; '.join(info['filters']))
    elif tool!='filter_rows':
        st.caption(f'Based on all {account.get("input_rows",0):,} records, with no filters.'
                   if account.get('selected_rows')==account.get('input_rows')
                   else f'{account.get("selected_rows",0):,} of {account.get("input_rows",0):,} records selected.')
    if model_tool:
        st.caption('Calculated values are reproducible; whether this calculation answers your intended question is not independently verified.')
    if tool=='grouped_summary':
        diff=two_group_difference(output)
        if diff and not diff['tie']:
            noun={'sum':'total','mean':'average','count_rows':'record count',
                  'min':'minimum','max':'maximum'}.get(args.get('operation'),'calculated value')
            st.markdown(f'**{label(diff["leader"])}’s {noun} is {number(diff["difference"])} higher.**')
    for notice in important_notices(output):
        st.warning(str(notice))
    if rows:
        visible=visible_result_rows(output,cap=12)
        st.dataframe(pd.DataFrame(visible,dtype=str),hide_index=True,use_container_width=True,
                     height=min(40+35*(len(visible)+1),340))
        if len(rows)>12:
            st.caption(f'Showing 12 of {len(rows):,} returned rows. Full values are in the original evidence.')
    if tool in ('grouped_summary','time_trend') and 2<=len(rows)<=8 and chart_safe(rows):
        axis='group_value' if tool=='grouped_summary' else 'period_start'
        measure=readable_measure(spec).capitalize()
        labels=[label(r.get(axis)) if tool=='grouped_summary' else observed_period_label(r.get(axis),args.get('frequency')) for r in rows]
        chart=pd.DataFrame({'Group':labels,measure:[r['value'] for r in rows]})
        if chart['Group'].is_unique:
            if tool=='time_trend':
                st.line_chart(chart,x='Group',y=measure,color='#087F78',height=220,use_container_width=True)
            else:
                st.bar_chart(chart,x='Group',y=measure,horizontal=True,color='#087F78',
                             height=min(80+50*len(rows),250),use_container_width=True)
    elif tool in ('grouped_summary','time_trend') and rows and not chart_safe(rows):
        st.caption('Chart omitted to avoid rounding exact large numbers or plotting missing values. The table retains original precision.')
    if display.get('truncated'):
        kind='matching records' if tool=='filter_rows' else 'results'
        st.warning(f'Only {display.get("returned_rows")} of {display.get("total_result_rows")} {kind} are shown. '
                   'Calculations use all eligible records, not the preview.')
    with st.expander('How this was calculated',expanded=False):
        source_definition(spec)
        accounting(ev)
        if tool=='grouped_summary' and rows:
            st.caption('Detailed group accounting, including record counts and missing numeric values:')
            st.dataframe(pd.DataFrame(display_rows(rows[:12]),dtype=str).rename(columns={
                'group_value':str(info['group']) if info['group'] is not None else 'Group',
                'value':readable_measure(spec).capitalize(),
                'row_count':'Records in group',
                'non_missing_metric_count':'Records with numeric values'}),hide_index=True,use_container_width=True)
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
