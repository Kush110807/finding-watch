from pathlib import Path
import json
import hashlib
import pandas as pd
import streamlit as st
from engine import AnalysisError, load_csv, numeric_columns, run_tool
from comparisons import prepare_comparison, execute_comparison
from presentation import (metric_choices,group_candidates,missing_product_context,
                          filter_description,confirmed_comparison_matches,clarification_definition,
                          same_numeric_grouping_explanation,grouping_phrase,
                          preview_display_table)
from ui_components import analysis_result,comparison_result,source_definition,evidence_download
from stage1_logic import suggested_questions, candidate_title
from stage2_logic import (calculated_choices, result_option_map, result_selection_key,
                          bind_selected_challenge_occurrence,
                          append_clarification_context, response_failure_kind)

ROOT=Path(__file__).resolve().parent


from challenge_ui import show_challenge


st.set_page_config(page_title='Finding Watch · BYTE',page_icon='📊',layout='centered',initial_sidebar_state='collapsed')
st.markdown("""<style>
:root {color-scheme:light}
.stApp {background:#FAF9F6;color:#172F44}
[data-testid="stHeader"] {background:#FAF9F6}
[data-testid="stSidebar"] {background:#F0F5F3}
.block-container {max-width:960px;padding-top:2.2rem;padding-bottom:4rem}
h1,h2,h3 {color:#172F44;letter-spacing:-.025em}
h1 {font-size:2.35rem!important;font-weight:740!important;margin-bottom:.2rem!important}
h2 {font-size:1.45rem!important}
[data-testid="stMetricValue"] {color:#172F44}
div.stButton > button[kind="primary"],div.stFormSubmitButton > button[kind="primary"] {
 background:#087F78;border-color:#087F78;color:white;font-weight:650}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:12px}
[data-testid="stExpander"] {border:1px solid #DFE5E1;border-radius:12px;background:#FDFDFA}
@media(max-width:640px){.block-container{padding-top:1.2rem;padding-left:1rem;padding-right:1rem}
 h1{font-size:1.9rem!important}}
</style>""",unsafe_allow_html=True)
st.title('Finding Watch')
st.markdown('**Understand your data. Test your findings.**')
st.caption('Upload a CSV or explore an example. Ask a question, see the calculated finding, and inspect the evidence when you need it.')

left,right=st.columns(2,vertical_alignment='bottom')
with left:
    use_demo=st.button('Try an example',type='primary',use_container_width=True)
with right:
    upload=st.file_uploader('Upload CSV',type=['csv'],key='stage1_upload',label_visibility='visible')
if use_demo:
    st.session_state['entry_mode']='example'
if upload is not None:
    sig=hashlib.sha256(upload.getvalue()).hexdigest()
    if sig!=st.session_state.get('entry_upload_hash'):
        st.session_state['entry_upload_hash']=sig
        st.session_state['entry_mode']='upload'
if upload is not None and st.session_state.get('entry_mode')=='example':
    if st.button('Use uploaded CSV instead',key='use_uploaded_csv'):
        st.session_state['entry_mode']='upload'
mode=st.session_state.get('entry_mode')
if mode not in ('example','upload'):
    st.info('Choose **Try an example** or **Upload CSV** to begin. Nothing is sent to Gemini without your consent.')
    st.stop()
try:
    if mode=='upload':
        if upload is None:
            st.info('Upload a CSV to continue, or try the bundled example.')
            st.stop()
        raw=upload.getvalue()
        filename=upload.name
    else:
        raw=(ROOT/'data/demo_sales.csv').read_bytes()
        filename='demo_sales.csv'
    df=load_csv(raw)
except AnalysisError as exc:
    st.error('Unable to load this CSV: '+str(exc))
    st.stop()
source_hash=hashlib.sha256(raw).hexdigest()
cols=list(df.columns); nums=numeric_columns(df)
st.markdown(f'**{filename}**  ·  {len(df):,} records  ·  {len(cols)} columns')
with st.expander('Inspect dataset · sample and column information',expanded=False):
    st.caption('Dataset fingerprint: '+source_hash+' · Calculations use the full dataset, not just the preview.')
    st.dataframe(preview_display_table(df.head(30)),hide_index=True,use_container_width=True,height=240)
    if len(df)>30: st.caption('Sample shows 30 records; every calculation uses the full dataset.')
    if st.button('Profile all columns',key='profile_columns'):
        st.session_state['stage1_profile']={'fingerprint':source_hash,'output':run_tool(df,'inspect_dataset',{})}
    profile=st.session_state.get('stage1_profile')
    if profile and profile['fingerprint']==source_hash:
        st.dataframe(preview_display_table(pd.DataFrame(profile['output']['rows'])),hide_index=True,use_container_width=True)
        st.json(profile['output']['evidence'])
        evidence_download(profile['output'],'dataset_profile.json',location='stage1_profile')

st.header('What would you like to understand?')
st.caption('For more precise controls, open the sidebar (top-left) and choose Advanced · five manual analysis tools.')
suggestions=suggested_questions(cols,nums,df)
suggestion_map={item['question']:item for item in suggestions}
if st.session_state.get('stage1_suggestion_dataset')!=source_hash:
    st.session_state['stage1_suggestion_dataset']=source_hash
    st.session_state['stage1_question']=''
    st.session_state['suggested_question']=None
    st.session_state['stage1_active_suggestion']=None
with st.expander('Suggested questions · optional',expanded=False):
    if suggestions:
        st.caption('Choose an example based on the columns in this CSV. It will fill the question field, not run the analysis.')
        suggestion_choice=st.selectbox('Choose a suggested question',list(suggestion_map),
            index=None,placeholder='Choose a question',key='suggested_question')
        if st.button('Use this question',disabled=suggestion_choice is None,key='stage1_apply_suggestion'):
            st.session_state['stage1_question']=suggestion_choice
            st.session_state['stage1_active_suggestion']=suggestion_choice
            st.rerun()
        st.caption('Full suggestion: '+str(suggestion_choice) if suggestion_choice else 'Select a suggestion to see its complete wording here, including on a phone.')
    else:
        st.caption('No safe local question suggestion for these columns. Ask a custom question with Gemini consent, or use the advanced manual tools.')
with st.expander('Gemini connection and consent · optional',expanded=False):
    st.caption('Suggested questions run locally in Python. For a custom question, Gemini receives column names/types, your question, and relevant bounded tool outputs, which may include matching rows.')
    from agent import AgentError, ask, available_models, configuration
    _,model=configuration()
    st.caption('Configured model: '+model+'. Your private API key is read from your local configuration.')
    if st.button('Check provider models',key='check_models'):
        try: st.write(available_models())
        except AgentError as exc: st.error(str(exc))
    st.caption('To change the model, edit GEMINI_MODEL privately and restart. Model listing does not prove live inference.')
    consent=st.checkbox('I agree to send my question and relevant dataset information to Gemini.',key='gemini_consent')

def gemini_with_feedback(frame, submitted, *, baseline_spec=None, clarification_context=None):
    # A single Streamlit session cannot queue a second submission while its
    # first synchronous provider request is running. Cross-session requests
    # share the process-wide monotonic pacer in provider_reliability.py.
    if st.session_state.get('gemini_busy'):
        raise AgentError('A Gemini request is already in progress for this session.')
    st.session_state['gemini_busy']=True
    progress_box=st.empty()
    def progress(event):
        if event.get('event') == 'waiting':
            progress_box.info(f"Waiting {event['seconds']:g}s for Gemini request capacity…")
        elif event.get('event') == 'retrying':
            progress_box.info(f"Gemini request was interrupted ({event.get('http_status') or 'connection'}); "
                              f"retrying after {event['seconds']:g}s (attempt {event['attempt']})…")
    try:
        return ask(frame,submitted,baseline_spec=baseline_spec,
                   clarification_context=clarification_context,progress=progress)
    finally:
        progress_box.empty()
        st.session_state['gemini_busy']=False

# Keep all existing tools in a secondary, collapsed workspace. This runs
# before the question form so any approved manual baseline can be explicitly
# selected as a follow-up without silent fallback.
labels={'Inspect dataset':'inspect_dataset','Filter rows':'filter_rows','Summarise groups':'grouped_summary',
        'Analyse time trends':'time_trend','Measure correlation':'correlation'}
saved_manual=st.session_state.get('last_manual')
manual_current=False
with st.sidebar:
    if st.toggle('Advanced · five manual analysis tools',value=False,key='show_advanced'):
        st.caption('Optional, local-only calculations. Choose exact columns and settings; you do not need an API key.')
        choice=st.selectbox('Analysis tool',list(labels),key='advanced_tool_choice')
        args={}; ready=True
        if choice=='Filter rows':
            args['field']=st.selectbox('Column',cols)
            args['operator']=st.selectbox('Condition',['eq','ne','gt','ge','lt','le','contains','is_missing','not_missing'],
                format_func=lambda x:{'eq':'Equals','ne':'Does not equal','gt':'Greater than','ge':'Greater than or equal',
                'lt':'Less than','le':'Less than or equal','contains':'Contains literal text','is_missing':'Is missing','not_missing':'Is not missing'}[x])
            if args['operator'] not in {'is_missing','not_missing'}: args['value']=st.text_input('Filter value')
            args['limit']=st.number_input('Maximum returned rows',min_value=1,max_value=1000,value=100)
            st.caption('Text comparisons are case-sensitive. Missing values do not match ordinary comparisons.')
        elif choice=='Summarise groups':
            args['group']=st.selectbox('Group by',cols)
            args['operation']=st.selectbox('Calculation',['sum','mean','min','max','count_rows'],format_func=lambda x:'Record count (rows)' if x=='count_rows' else {'sum':'Total','mean':'Average','min':'Minimum','max':'Maximum'}[x])
            if args['operation']!='count_rows':
                if nums: args['metric']=st.selectbox('Numeric metric',nums)
                else: st.warning('No numeric columns. Choose count_rows.'); ready=False
        elif choice=='Analyse time trends':
            args['date_column']=st.selectbox('Date column',cols)
            args['date_format']=st.selectbox('Exact date format',['%Y-%m-%d','%d/%m/%Y','%m/%d/%Y'])
            args['frequency']=st.selectbox('Time interval',['month','week','day'])
            args['operation']=st.selectbox('Calculation',['sum','mean','count_rows'],format_func=lambda x:'Record count (rows)' if x=='count_rows' else {'sum':'Total','mean':'Average'}[x])
            if args['operation']!='count_rows':
                if nums: args['metric']=st.selectbox('Numeric metric',nums)
                else: st.warning('No numeric columns. Choose count_rows.'); ready=False
            else: args['metric']=None
        elif choice=='Measure correlation':
            if len(nums)<2: st.warning('Two numeric columns are required.'); ready=False
            else:
                args['x']=st.selectbox('First numeric column',nums)
                args['y']=st.selectbox('Second numeric column',[c for c in nums if c!=args['x']])
        if choice in ('Summarise groups','Analyse time trends','Measure correlation'):
            with st.expander('Optional analysis filters (AND)'):
                conditions=st.number_input('Number of filters',min_value=0,max_value=3,value=0,step=1)
                if conditions:
                    args['filters']=[]
                for i in range(conditions):
                    fcol=st.selectbox(f'Filter {i+1} column',cols,key=f'filter_column_{i}')
                    op=st.selectbox(f'Filter {i+1} operator',['eq','ne','gt','ge','lt','le','contains','is_missing','not_missing'],key=f'filter_op_{i}')
                    filter_spec={'field':fcol,'operator':op}
                    if op not in ('is_missing','not_missing'):
                        filter_spec['value']=st.text_input(f'Filter {i+1} value',key=f'filter_value_{i}')
                    args['filters'].append(filter_spec)

        manual_submission={'fingerprint':source_hash,'tool':labels[choice],
                           'arguments':json.loads(json.dumps(args,default=str))}
        if st.button('Run analysis',type='primary',disabled=not ready):
            st.session_state.pop('last_manual_comparison',None)
            try:
                output=run_tool(df,labels[choice],args)
                st.session_state['last_manual']={'submission':manual_submission,'output':output,
                    'submission_occurrence':st.session_state.get('stage3_submission_serial',0)+1}
                st.session_state['stage3_submission_serial']=st.session_state['last_manual']['submission_occurrence']
            except AnalysisError as exc:
                st.session_state.pop('last_manual',None)
                st.error(str(exc))
        saved_manual=st.session_state.get('last_manual')
        manual_current=bool(saved_manual and saved_manual['submission']==manual_submission)
        if saved_manual:
            if not manual_current:
                st.warning('Pending edits: the previous result is hidden. Click Run analysis to submit the new settings. Old calculations have not changed.')
            else:
                analysis_result(saved_manual['output'],heading='Submitted calculation',
                                download_location='manual_result')
        # M2 Challenge always binds to the specific submitted output, not controls.
        if (manual_current and saved_manual['output']['tool']=='grouped_summary'):
            show_challenge(df,saved_manual['output'],
                {'kind':'manual','dataset':source_hash,'submission':saved_manual['submission'],
                 'label':'Manual calculation submitted with the settings above',
                 'occurrence':saved_manual.get('submission_occurrence')},
                prefix='manual')


# Explicitly identified approved grouped results may be used as a model follow-up.
current_baselines={}
if (manual_current and saved_manual['output']['tool']=='grouped_summary'):
    current_baselines['Submitted manual grouped calculation']={
        'spec':saved_manual['output']['evidence']['executed_spec'],
        'source':'manual','submission':saved_manual['submission']}
prev_clarified=st.session_state.get('last_clarified')
if (prev_clarified and prev_clarified['dataset_fingerprint']==source_hash
        and prev_clarified['output']['tool']=='grouped_summary'):
    current_baselines['Clarified: '+prev_clarified['submitted_question'][:90]]={
        'spec':prev_clarified['output']['evidence']['executed_spec'],
        'source':'clarified','question':prev_clarified['submitted_question'],
        'chosen':prev_clarified['chosen']}
prev_answer=st.session_state.get('last_answer')
if (prev_answer and prev_answer.get('dataset_fingerprint')==source_hash
        and prev_answer['response'].get('status')=='evidence_available'):
    for i,event in enumerate(prev_answer['response'].get('trace',[]),1):
        evidence=event.get('result',{}).get('evidence',{})
        if evidence.get('calculation_status')=='completed' and evidence.get('executed_spec',{}).get('tool')=='grouped_summary':
            current_baselines[f'Gemini calculation {i}: '+prev_answer['submitted_question'][:75]]={
                'spec':evidence['executed_spec'],'source':'gemini',
                'question':prev_answer['submitted_question'],'trace_index':i}
baseline_label='No prior baseline'
if current_baselines:
    with st.expander('Use a previous finding for a follow-up Challenge · optional',expanded=False):
        baseline_set_id=hashlib.sha256(json.dumps(current_baselines,sort_keys=True,
            ensure_ascii=False).encode()).hexdigest()[:16]
        baseline_label=st.selectbox('Follow-up Challenge baseline (optional)',
            ['No prior baseline']+list(current_baselines),index=0,
            key='ai_baseline_source_'+baseline_set_id)
        if baseline_label!='No prior baseline':
            st.caption('Only this explicitly selected submitted grouped definition will be supplied to Gemini.')

with st.form('question_form'):
    question=st.text_input('Your question',max_chars=4000,key='stage1_question',
        placeholder='For example: Which category has the highest total of revenue?')
    submit=st.form_submit_button('Analyse',type='primary',use_container_width=True,
                                 disabled=bool(st.session_state.get('gemini_busy',False)))
if submit:
    q=question.strip()
    if not q:
        st.warning('Enter a question, or select one of the suggestions above.')
    else:
        suggested=suggestion_map.get(q) if st.session_state.get('stage1_active_suggestion')==q else None
        st.session_state.pop('last_clarified',None)
        st.session_state.pop('last_ai_comparison',None)
        st.session_state.pop('clarify_method',None)
        st.session_state.pop('last_visible_ai_trace_index',None)
        st.session_state.pop('stage1_provider_error',None)
        st.session_state['stage2_response_serial']=st.session_state.get('stage2_response_serial',0)+1
        if suggested:
            st.session_state.pop('last_answer',None)
            try:
                st.session_state.pop('stage1_provider_error',None)
                output=run_tool(df,suggested['tool'],suggested['arguments'])
                st.session_state['stage1_local_answer']={
                    'fingerprint':source_hash,'question':q,'spec':suggested,'output':output,
                    'submission_occurrence':st.session_state['stage2_response_serial']}
            except AnalysisError as exc:
                st.session_state.pop('stage1_local_answer',None)
                st.error('Could not complete this calculation: '+str(exc))
        elif not consent:
            st.session_state.pop('last_answer',None)
            st.session_state.pop('stage1_local_answer',None)
            st.warning('This custom question needs Gemini to select a supported tool. Enable optional Gemini consent, or choose a suggested local question.')
        else:
            st.session_state.pop('stage1_local_answer',None)
            with st.spinner('Running supported calculations…'):
                try:
                    selected_baseline=current_baselines.get(baseline_label)
                    answer=gemini_with_feedback(df,q,baseline_spec=(selected_baseline or {}).get('spec'))
                    st.session_state.pop('stage1_provider_error',None)
                    st.session_state['last_answer']={'dataset_fingerprint':source_hash,
                        'submitted_question':q,'response':answer,'baseline_reference':selected_baseline}
                except AgentError as exc:
                    st.session_state.pop('last_answer',None)
                    st.session_state['stage1_provider_error']={'fingerprint':source_hash,'question':q,'message':str(exc)}
if st.session_state.get('stage1_provider_error',{}).get('fingerprint')==source_hash and st.session_state['stage1_provider_error']['question']==question:
    st.error('Gemini could not complete this request. Your question is preserved. Choose Analyse to retry, review optional connection settings, or use a local suggested question.')
    with st.expander('Provider error details'):st.write(st.session_state['stage1_provider_error']['message'])
local=st.session_state.get('stage1_local_answer')
if local and local['fingerprint']==source_hash:
    if local['question']!=question or st.session_state.get('stage1_active_suggestion')!=local['question']:
        st.info('Question edits are pending. The previously calculated result is hidden until you submit again.')
    else:
        analysis_result(local['output'],heading='Your calculated finding',download_location='stage1_local_result')
        if local['output']['tool']=='grouped_summary':
            show_challenge(df,local['output'],
                {'kind':'suggested','dataset':source_hash,'question':question,'spec':local['spec'],
                 'label':'Submitted local finding: '+question[:120],
                 'occurrence':local.get('submission_occurrence')},
                prefix='suggested')
saved=st.session_state.get('last_answer')
if saved and saved['dataset_fingerprint']!=source_hash:
    st.session_state.pop('last_answer',None)
    st.session_state.pop('last_clarified',None)
    saved=None
if saved:
    answer=saved['response']
    submitted=saved['submitted_question']
    changed_question=(question!=submitted)
    if changed_question:
        st.session_state.pop('last_visible_ai_trace_index',None)
        st.info('The current question has changed. The earlier response is hidden until you submit this question.')
    status=answer.get('status','unverified')
    if status=='clarification' and not changed_question:
        st.info('A definition is needed before this question can be calculated.')
        st.markdown('### Clarify your original question')
        st.caption('Original question: '+submitted)
        if answer.get('answer'):
            st.caption('Gemini asked (not an executable definition): '+answer['answer'])
        if missing_product_context(cols,submitted):
            st.warning('Your question mentions “product”, but this CSV has no column containing “product”. You may choose an existing grouping column, or upload product-level data. Another column changes the question.')
        st.caption('Choose the kind of clarification you want to provide. Nothing is selected automatically.')
        method=st.radio('Clarification approach',
            ['Choose a grouping and calculation','Explain the missing context (dates or other details)'],
            index=None,key='clarify_method')
        if method=='Choose a grouping and calculation':
            options=metric_choices(cols,nums)
            # Ordinary widgets (not a Streamlit form) allow the definition and
            # the same-column warning to update BEFORE the explicit Analyse click.
            # Choosing a value never starts a calculation.
            st.caption('Choose what to compare. For example: '+ '; '.join(
                f'choose “{c}” to compare {grouping_phrase(c)}' for c in cols[:4])+'.')
            group=st.selectbox('What should the results be grouped by?',group_candidates(cols,submitted),
                index=None,placeholder='Choose a grouping column',key='clarify_group')
            measure=st.selectbox('What should be measured?',list(options),
                index=None,placeholder='Choose a calculation',key='clarify_metric')
            if group is not None and measure is not None:
                selected_choice=options[measure]
                st.markdown('**Your definition:** '+clarification_definition(
                    group,selected_choice['operation'],selected_choice['metric']))
                caveat=same_numeric_grouping_explanation(group,selected_choice['metric'])
                if caveat: st.warning(caveat)
            clarify_submit=st.button('Analyse with my choices',type='primary',key='submit_clarified_definition')
            if clarify_submit:
                if not group or not measure:
                    st.error('Choose both a grouping column and a calculation before analysing.')
                else:
                    selected=options[measure]
                    definition={'group':group,'operation':selected['operation']}
                    if selected['metric'] is not None:definition['metric']=selected['metric']
                    try:
                        output=run_tool(df,'grouped_summary',definition)
                        st.session_state['last_clarified']={
                            'dataset_fingerprint':source_hash,'submitted_question':submitted,
                            'chosen':definition,'output':output,
                            'submission_occurrence':st.session_state.get('stage3_submission_serial',0)+1}
                        st.session_state['stage3_submission_serial']=st.session_state['last_clarified']['submission_occurrence']
                    except AnalysisError as exc:
                        st.session_state.pop('last_clarified',None);st.error(str(exc))
            clarified=st.session_state.get('last_clarified')
            if clarified and clarified['dataset_fingerprint']==source_hash and clarified['submitted_question']==submitted:
                current_definition=None
                if group is not None and measure is not None:
                    selected=options[measure]
                    current_definition={'group':group,'operation':selected['operation']}
                    if selected['metric'] is not None:current_definition['metric']=selected['metric']
                if current_definition==clarified['chosen']:
                    analysis_result(clarified['output'],
                        heading='Calculated from your explicit definition',
                        download_location='clarified_result')
                    if clarified['output']['tool']=='grouped_summary':
                        show_challenge(df,clarified['output'],
                            {'kind':'clarified','dataset':source_hash,'question':submitted,
                             'chosen':clarified['chosen'],
                             'label':'Explicitly clarified answer to: '+submitted[:120],
                             'occurrence':clarified.get('submission_occurrence')},
                            prefix='clarified')
                else:
                    st.warning('Pending clarification edits — the previous calculation and Challenge are hidden until you submit.')
        elif method=='Explain the missing context (dates or other details)':
            st.caption('For example: “Dates are DD/MM/YYYY” or “compare records by week”. Your explanation is context for Gemini, not executable code.')
            with st.form('clarify_context_form'):
                details=st.text_area('Your clarification',max_chars=2000,
                                     key=f'clarify_context_{st.session_state.get("stage2_response_serial",0)}')
                contextual_submit=st.form_submit_button('Continue with original question and my clarification',type='primary')
            if contextual_submit:
                if not details.strip():
                    st.error('Enter the missing information before continuing.')
                elif not consent:
                    st.error('Enable Gemini consent to send contextual clarification.')
                else:
                    try:
                        combined_context=append_clarification_context(
                            saved.get('clarification_context'),details)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        try:
                            with st.spinner('Reconsidering the original question with your clarification…'):
                                new_response=gemini_with_feedback(df,submitted,clarification_context=combined_context)
                            st.session_state.pop('last_clarified',None)
                            st.session_state.pop('last_ai_comparison',None)
                            st.session_state.pop('stage1_provider_error',None)
                            st.session_state['stage2_response_serial']=st.session_state.get('stage2_response_serial',0)+1
                            st.session_state['last_answer']={'dataset_fingerprint':source_hash,
                                'submitted_question':submitted,'response':new_response,
                                'clarification_context':combined_context,'baseline_reference':None}
                            st.rerun()
                        except AgentError as exc:
                            st.error('Gemini could not process the clarification. Keep your original question and try again.')
                            with st.expander('Provider error details'):
                                st.write(str(exc))
    elif status=='clarification' and changed_question:
        st.info('The previous clarification is paused until you resubmit the edited question.')
    elif status=='comparison_pending' and not changed_question:
        proposal_for_status=answer.get('pending_comparison')
        old_confirm=st.session_state.get('last_ai_comparison')
        if (old_confirm and old_confirm.get('proposal')==proposal_for_status
                and old_confirm.get('question')==submitted
                and old_confirm.get('dataset_fingerprint')==source_hash
                and old_confirm.get('result',{}).get('status')=='completed'):
            st.caption('Gemini originally proposed the Challenge. The user-confirmed calculation is shown below.')
        else:
            st.warning('PENDING USER CONFIRMATION — the proposed Challenge has not been calculated.')
    elif status in ('error','limited','unverified') and not changed_question:
        problem='provider' if answer.get('provider_diagnostic') else response_failure_kind(answer)
        if problem=='calculation':
            st.error('The calculation could not be completed. Check column choices, filters, and any date format; correct the definition and retry Analyse or use the advanced local tools.')
        elif problem=='provider':
            st.error('Gemini could not complete this request. Retry Analyse or inspect connection settings; local suggested questions are also available.')
        else:
            st.info('No supported calculation was completed. Specify the grouping, measure, or date format and retry Analyse, or use a local tool.')
        with st.expander('Provider or calculation details'):
            st.write(str(answer.get('answer','No verified calculation available.')))
            diagnostic=answer.get('provider_diagnostic')
            if diagnostic:
                st.json(diagnostic)
                if diagnostic.get('partial_tools_completed'):
                    st.caption('Earlier tools may have calculated partial results, but this request did not finish. No final answer is verified.')
            for event in answer.get('trace',[]):
                detail=event.get('result',{})
                if isinstance(detail,dict) and detail.get('error'):
                    st.caption(str(detail['error']))
            st.caption('No previous finding is being shown as this answer. Tool failure and provider failure are different states.')

    if not changed_question and status=='evidence_available':
        choices=calculated_choices(answer.get('trace',[]))
        chosen=None
        selection_key=result_selection_key(source_hash,submitted,answer,
            st.session_state.get('stage2_response_serial',0))
        if len(choices)==1:
            chosen=(choices[0]['position'],choices[0]['event'])
        elif len(choices)>1:
            st.info('Several results are available. Choose one to view. Nothing is selected automatically.')
            options=result_option_map(choices)
            selected_label=st.selectbox('Which result would you like to see?',
                list(options),index=0,key=selection_key)
            matching=options[selected_label]
            chosen=(matching['position'],matching['event']) if matching else None
        # The selected occurrence drives Challenge approval even when the
        # chosen tool is NOT grouped_summary (and no Challenge UI is shown).
        # Identical rerenders preserve an already confirmed comparison.
        bind_selected_challenge_occurrence(st.session_state,selection_key,
            chosen[0] if chosen else None)
        if chosen:
            index,event=chosen
            analysis_result(event['result'],heading='Calculated finding',model_tool=True,
                            download_location='ai_primary_result',download_occurrence=index)
            st.session_state['last_visible_ai_trace_index']=index
            if event['result'].get('tool')=='grouped_summary':
                show_challenge(df,event['result'],
                    {'kind':'gemini','dataset':source_hash,'question':submitted,
                     'trace_index':index,'response_occurrence':st.session_state.get('stage2_response_serial',0),
                     'label':f'Selected Gemini calculation {index}'},prefix='ai_selected')
        else:
            st.session_state.pop('last_visible_ai_trace_index',None)
        with st.expander('Other calculations and execution details',expanded=False):
            st.caption('These are executed operations, not independent proof that the model understood your intent.')
            for i,event in enumerate(answer.get('trace',[]),1):
                result=event.get('result',{})
                st.markdown('**'+candidate_title(i,event)+'**' if isinstance(result,dict) and result.get('rows') is not None
                            else '**Tool event '+str(i)+'**')
                if result.get('error'): st.error(str(result['error']))
                else:
                    st.json(result)
                    if result.get('evidence',{}).get('calculation_status')=='completed':
                        evidence_download(result,f'calculation_{i}.json','Download this tool result JSON',
                                          location='ai_support_result',occurrence=i)
    elif not changed_question:
        with st.expander('Tool execution details',expanded=False):
            st.json(answer.get('trace',[]))
    if not changed_question and status=='evidence_available' and answer.get('answer'):
        with st.expander('Gemini explanation · not independently verified'):
            st.write(answer['answer'])
    proposal=answer.get('pending_comparison') if not changed_question else None
    if proposal:
        confirmed_before=st.session_state.get('last_ai_comparison')
        ai_confirmed=bool(confirmed_before and confirmed_before.get('proposal')==proposal
            and confirmed_before.get('question')==submitted
            and confirmed_before.get('dataset_fingerprint')==source_hash
            and confirmed_before.get('result',{}).get('status')=='completed')
        st.subheader('Confirmed Challenge · originally proposed by Gemini' if ai_confirmed else 'Proposed Challenge · awaiting approval')
        if ai_confirmed:
            st.success('CONFIRMED — these exact definitions were approved and calculated.')
        else:
            st.warning('PENDING — these model-suggested definitions have not been calculated or approved.')
        changed=proposal['changed_condition']
        st.caption('Exactly one changed condition: '+changed['kind'])
        if changed.get('before'): st.caption('Before: '+filter_description(changed['before']))
        if changed.get('after'): st.caption('After: '+filter_description(changed['after']))
        source_definition(proposal['baseline_spec'],
                          'Baseline · confirmed definition' if ai_confirmed else 'Baseline · proposed definition')
        source_definition(proposal['challenged_spec'],
                          'Challenge · confirmed definition' if ai_confirmed else 'Challenge · proposed definition')
        with st.expander('Inspect both exact specifications ('+('confirmed' if ai_confirmed else 'pending')+')'):
            st.json(proposal['baseline_spec'])
            st.json(proposal['challenged_spec'])
        if not ai_confirmed:
            st.caption('Confirm only if BOTH definitions match the question you intended to ask.')
        if not ai_confirmed and st.button('Confirm and run proposed comparison',key='m2_ai_confirm'):
            try:
                comparison=execute_comparison(df,proposal['baseline_spec'],proposal['challenged_spec'],
                    expected_fingerprint=proposal['dataset_fingerprint_sha256'])
                st.session_state['last_ai_comparison']={
                    'proposal':proposal,'question':submitted,
                    'dataset_fingerprint':source_hash,'result':comparison}
                st.rerun()
            except AnalysisError as exc:
                st.error(str(exc))
        confirmed=st.session_state.get('last_ai_comparison')
        if ai_confirmed and confirmed:
            comparison_result(confirmed['result'],heading='User-confirmed comparison',
                              filename='confirmed_comparison.json',download_location='ai_comparison')
    if not changed_question:
        with st.expander('How this response was produced'):
            st.caption('Original question, model status and tool trace. Tool results do not prove a model interpretation is correct.')
            st.json({'question':submitted,'model_proposal_status_at_creation' if status=='comparison_pending' else 'model_status':status,
                 'model':answer.get('model',model),
                 'trace':answer.get('trace',[]),'calculation_verified':answer.get('calculation_verified',False),
                 'explanation_verified':answer.get('explanation_verified',False),
                 'user_clarification_context':saved.get('clarification_context'),
                 'explicit_baseline_reference':saved.get('baseline_reference')})
            evidence_download(answer,'ai_analysis.json',
            'Download original Gemini proposal JSON' if status=='comparison_pending' else 'Download AI analysis evidence',
            location='ai_response')



