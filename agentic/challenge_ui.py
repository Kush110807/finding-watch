"""Bounded, explicit Streamlit Challenge interaction and confirmation gate."""
import json
import pandas as pd
import streamlit as st
from engine import AnalysisError
from comparisons import prepare_comparison, execute_comparison
from challenge_logic import (identity, column_operators, categorical_values, parse_numeric,
                             changed_filters, parse_contains_text, FRIENDLY_OPERATORS, definition_line, unchanged_line)
from presentation import filter_description, confirmed_comparison_matches
from ui_components import comparison_result


def _condition_editor(df, prefix):
    field=st.selectbox('Column',list(df.columns),index=None,placeholder='Choose a column',
                       key=prefix+'_field')
    if field is None:
        return None
    ops=column_operators(df,field)
    if 'date' in field.casefold() or 'time' in field.casefold():
        st.caption('Date-like values are compared as exact CSV text. No date parsing is assumed.')
    operator=st.selectbox('Condition',list(ops),index=None,format_func=lambda op:FRIENDLY_OPERATORS[op],
                          placeholder='Choose a condition',key=prefix+'_operator_'+identity({'field':field}))
    if operator is None:
        return None
    condition={'field':field,'operator':operator}
    if operator in ('is_missing','not_missing'):
        st.caption('Missing means an empty CSV cell. An empty text value is different.')
        return condition
    # Contains is a substring operation, not a choice of existing whole cells.
    # Empty/blank input stays incomplete; no plan or calculation can be created.
    if operator=='contains':
        text=st.text_input('Text to find',placeholder='Enter part of the text',
                          key=prefix+'_contains_value_'+identity({'field':field,'operator':operator}))
        if not text.strip():
            return None
        condition['value']=parse_contains_text(text)
        return condition
    values=categorical_values(df,field)
    if values is not None:
        value_index=st.selectbox('Value',range(len(values)),index=None,
               format_func=lambda i:'(empty text)' if values[i]=='' else str(values[i]),
               placeholder='Choose an existing value',key=prefix+'_categorical_value_'+identity({'field':field,'operator':operator}))
        if value_index is None:
            return None
        condition['value']=values[value_index]
    else:
        numeric=pd.api.types.is_numeric_dtype(df[field])
        text=st.text_input('Value',key=prefix+'_input_value_'+identity({'field':field,'operator':operator}),placeholder='Enter a number' if numeric else 'Enter exact text')
        use_empty=False
        if not numeric:
            use_empty=st.checkbox('Use an empty text value (not a missing cell)',value=False,
                key=prefix+'_use_empty_'+identity({'field':field,'operator':operator}))
        if not text.strip() and not use_empty:
            return None
        condition['value']=parse_numeric(text) if numeric else ('' if use_empty else text)
    return condition


def show_challenge(df, baseline_output, baseline_binding, *, prefix):
    if baseline_output.get('tool')!='grouped_summary':
        return
    baseline_spec=baseline_output['evidence']['executed_spec']
    context=identity(baseline_binding)
    slot='s3_'+prefix
    editor_key=slot+'_editor'
    namespace=slot+'_'+context
    review_key=slot+'_review'
    completed_key='last_'+prefix+'_comparison' # preserve pre-existing confirmation storage
    if st.session_state.get(slot+'_context')!=context:
        st.session_state[slot+'_context']=context
        st.session_state.pop(review_key,None)
        st.session_state.pop(completed_key,None)
        st.session_state[editor_key]=False
    if not st.session_state.get(editor_key):
        if st.button('Test another condition',key=namespace+'_open'):
            st.session_state[editor_key]=True
            st.rerun()
        st.caption('See how this finding changes when you include different records.')
        return
    st.caption('See how this finding changes when you include different records.')
    st.markdown('**Choose one change**')
    existing=baseline_spec['filters']
    actions=(['Add condition'] if len(existing)<8 else [])+(['Replace condition','Remove condition'] if existing else [])
    action=st.selectbox('What would you like to change?', actions,index=None,
                        placeholder='Choose how to change the included records',key=namespace+'_action')
    index=None
    condition=None
    error=None
    if action in ('Replace condition','Remove condition'):
        index=st.selectbox('Existing condition',range(len(existing)),index=None,
                           format_func=lambda i:filter_description(existing[i]),
                           placeholder='Choose which condition',key=namespace+'_existing')
    if action in ('Add condition','Replace condition'):
        try:
            condition=_condition_editor(df,namespace)
        except AnalysisError as exc:
            error=str(exc)
    complete=bool(action and not error and
                  (action!='Remove condition' or index is not None) and
                  (action!='Replace condition' or index is not None) and
                  (action not in ('Add condition','Replace condition') or condition is not None))
    # This signature is calculated from the CURRENT controls on every rerun.
    # A changed control invalidates review and approval immediately.
    draft={'action':action,'index':index,'condition':condition,'complete':complete,'error':error}
    draft_token=json.dumps(draft,sort_keys=True,ensure_ascii=False,allow_nan=False,default=str)
    review=st.session_state.get(review_key)
    live=bool(review and review.get('context')==context and review.get('draft')==draft_token)
    if not live:
        st.session_state.pop(review_key,None)
        st.session_state.pop(completed_key,None)
        review=None
    if error:
        st.error(error)
    if st.button('Review comparison',type='primary',key=namespace+'_review_button',disabled=not complete):
        try:
            updated=changed_filters(existing,action,index=index,condition=condition)
            challenged={**baseline_spec,'filters':updated}
            plan=prepare_comparison(df,baseline_spec,challenged)
            st.session_state[review_key]={'plan':plan,'draft':draft_token,'context':context}
            st.rerun()
        except AnalysisError as exc:
            st.error('Change the condition and try again: '+str(exc))
    if review:
        if st.button('Edit condition',key=namespace+'_edit'):
            st.session_state.pop(review_key,None)
            st.session_state.pop(completed_key,None)
            st.rerun()
        plan=review['plan']
        record=st.session_state.get(completed_key)
        active=confirmed_comparison_matches(record,plan,baseline_binding)
        st.markdown('**'+('Completed comparison' if active else 'Review these definitions')+'**')
        left,right=st.columns(2)
        with left:
            st.caption('Original')
            st.markdown(definition_line(plan['baseline_spec']))
        with right:
            st.caption('Alternative')
            st.markdown(definition_line(plan['challenged_spec']))
        st.caption('Unchanged: '+unchanged_line(plan['baseline_spec']))
        if not active:
            st.info('Awaiting your confirmation. No comparison has been calculated.')
            if st.button('Confirm and compare',type='primary',key=namespace+'_confirm'):
                try:
                    result=execute_comparison(df,plan['baseline_spec'],plan['challenged_spec'],
                                  expected_fingerprint=plan['dataset_fingerprint_sha256'])
                except AnalysisError as exc:
                    st.error('Could not compare these conditions: '+str(exc)+' Change the condition and review again.')
                else:
                    st.session_state[completed_key]={'plan':plan,'baseline_binding':baseline_binding,'result':result}
                    st.rerun()
        else:
            comparison_result(record['result'],heading='User-confirmed Challenge',
                              filename=prefix+'_comparison.json',download_location=prefix+'_comparison')
    if st.button('Close condition editor',key=namespace+'_close'):
        st.session_state[editor_key]=False
        st.session_state.pop(review_key,None)
        st.session_state.pop(completed_key,None)
        st.rerun()
