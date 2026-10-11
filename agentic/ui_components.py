"""Streamlit rendering only. The engine and comparison JSON are never rewritten."""
import json
import pandas as pd
import streamlit as st
from download_keys import evidence_key
from stage1_logic import two_group_difference
from presentation import (summary, comparison_summary, comparison_table, label, number,
                          metric_definition, spec_description, filter_description,chart_safe,display_rows,readable_measure,simple_group_table,visible_result_rows,important_notices,detailed_group_table,preview_counts,time_chart_points)


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
        counts=preview_counts(output,cap=12)
        st.caption(f'**Matching records:** {counts["matched"]:,} · '
                   f'**Returned:** {counts["returned"]:,} · '
                   f'**Shown in table:** {counts["visible"]:,}')
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
        if tool=='time_trend':
            # Use actual observed period dates, not alphabetically sorted labels
            # ("Feb 2026" otherwise precedes "Jan 2026"). Temporal bars do not
            # interpolate or invent values for missing periods.
            time_points=time_chart_points(rows,args.get('frequency'))
            if time_points is not None:
                period_axis={'month':'Month','week':'Week starting','day':'Date'}.get(args.get('frequency'),'Period')
                chart=pd.DataFrame(time_points).rename(columns={'Period':period_axis,'Value':measure})
                st.bar_chart(chart,x=period_axis,y=measure,color='#087F78',height=220,
                             use_container_width=True)
        else:
            labels=[label(r.get(axis)) for r in rows]
            chart=pd.DataFrame({'Group':labels,measure:[r['value'] for r in rows]})
            if chart['Group'].is_unique:
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
            st.dataframe(pd.DataFrame(detailed_group_table(rows[:12],spec),dtype=str),
                         hide_index=True,use_container_width=True)
        st.json(ev)
        st.json(output.get('metadata',{}))
        evidence_download(output,'analysis_result.json','Download original result JSON',
                          location=download_location,occurrence=download_occurrence)

def comparison_result(result, *, heading='Confirmed comparison', filename='comparison.json',
                      download_location):
    """Stage 3 answer-first comparison, with raw JSON retained verbatim."""
    from challenge_logic import (conclusion, comparison_display_rows, definition_line,
                                 unchanged_line)
    st.subheader(heading)
    st.markdown('### '+conclusion(result))
    st.caption('Changing which records are included changes the question being answered; it does not prove the original result was wrong.')
    left,right=st.columns(2)
    with left:
        st.caption('Original')
        st.markdown(definition_line(result['baseline_spec']))
    with right:
        st.caption('Alternative')
        st.markdown(definition_line(result['challenged_spec']))
    st.caption('Unchanged: '+unchanged_line(result['baseline_spec']))
    a=result['accounting']['baseline']; b=result['accounting']['challenged']
    st.caption(f'**Records included:** original {a["selected_rows"]:,} of {a["input_rows"]:,}; '
               f'alternative {b["selected_rows"]:,} of {b["input_rows"]:,}. '
               f'Excluded by conditions: {a["excluded_by_filters"]:,} and {b["excluded_by_filters"]:,}.')
    st.dataframe(pd.DataFrame(comparison_display_rows(result),dtype=str),hide_index=True,use_container_width=True)
    c=result['comparison']
    for which,desc in [('baseline','original'),('challenged','alternative')]:
        omissions=result['accounting'][which].get('operation_exclusions',{})
        missing=omissions.get('missing_metric_excluded_from_values',0)
        if missing:
            st.warning(f'{missing:,} {desc} records had missing numeric values and were excluded from calculated values.')
        missing_groups=omissions.get('missing_group_labels_included',0)
        if missing_groups:
            st.warning(f'{missing_groups:,} {desc} records have no group label; they are kept as a separate group.')
    if c['display']['truncated']:
        st.warning(f'Only {c["display"]["returned_groups"]} of {c["display"]["total_groups"]} groups are shown. All groups were used for leader comparisons.')
    with st.expander('How this was compared',expanded=False):
        st.caption('Complete definitions, records and evidence. Exact integers and missing/absent groups are preserved in JSON.')
        source_definition(result['baseline_spec'],'Original definition')
        accounting(result['baseline']['evidence'])
        source_definition(result['challenged_spec'],'Alternative definition')
        accounting(result['challenged']['evidence'])
        for warning in result.get('warnings',[]): st.caption('Note: '+warning)
        st.json(result)
        evidence_download(result,filename,'Download comparison JSON',location=download_location)
