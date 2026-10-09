from pathlib import Path
import json
import hashlib
import pandas as pd
import streamlit as st
from engine import AnalysisError, load_csv, numeric_columns, run_tool
from comparisons import prepare_comparison, execute_comparison
from presentation import (metric_choices,group_candidates,missing_product_context,
                          filter_description,confirmed_comparison_matches)
from ui_components import analysis_result,comparison_result,source_definition,evidence_download

ROOT=Path(__file__).resolve().parent


def show_challenge_for_submitted_grouped(df, columns, baseline_output, baseline_binding, *,
                                         prefix, title, button_label):
    """An explicitly identified, submitted grouped finding is the ONLY baseline.

    Source choice is never inferred from an older result; each surface has its
    own widget and confirmation namespace to prevent accidental cross-binding.
    """
    if baseline_output.get('tool') != 'grouped_summary':
        return
    baseline_spec=baseline_output['evidence']['executed_spec']
    store_key=f'last_{prefix}_comparison'
    st.header('Challenge' if prefix=='manual' else 'Challenge clarified finding')
    st.caption('Change exactly one filter on this submitted result. The comparison runs only after confirmation.')
    with st.expander(title,expanded=False):
        st.caption('Baseline: '+baseline_binding['label'])
        conditions=baseline_spec['filters']
        options=(['Add condition'] if len(conditions)<8 else []) + (
            ['Remove condition','Replace condition'] if conditions else [])
        mode=st.selectbox('Change exactly one condition',options,key=f'm2_{prefix}_mode')
        updated=[dict(item) for item in conditions]
        index=None
        if mode in ('Remove condition','Replace condition'):
            index=st.selectbox('Condition to change',range(len(conditions)),
                format_func=lambda i:f'{i+1}: {conditions[i]}',key=f'm2_{prefix}_index')
        if mode!='Remove condition':
            field=st.selectbox('Challenged filter column',columns,key=f'm2_{prefix}_column')
            op=st.selectbox('Challenged filter operator',
                ['eq','ne','gt','ge','lt','le','contains','is_missing','not_missing'],
                key=f'm2_{prefix}_operator')
            condition={'field':field,'operator':op}
            if op not in ('is_missing','not_missing'):
                condition['value']=st.text_input('Challenged filter value',key=f'm2_{prefix}_value')
        if mode=='Add condition': updated.append(condition)
        elif mode=='Remove condition': updated.pop(index)
        else: updated[index]=condition
        challenged_spec={**baseline_spec,'filters':updated}
        try:
            plan=prepare_comparison(df,baseline_spec,challenged_spec)
        except AnalysisError as exc:
            st.info('Comparison definition is not ready: '+str(exc))
            return
        confirmed=st.session_state.get(store_key)
        active=confirmed_comparison_matches(confirmed,plan,baseline_binding)
        status_notice=st.empty()
        if active:
            status_notice.success('CONFIRMED — this exact comparison has been calculated and approved by you.')
        else:
            status_notice.warning('PENDING CONFIRMATION — these definitions have not been approved or calculated together.')
            if confirmed:
                st.info('Challenge edits are pending. The previous comparison is hidden until this exact definition is confirmed.')
        change=plan['changed_condition']
        st.caption('One changed condition: '+change['kind'])
        if change.get('before'):st.caption('Before: '+filter_description(change['before']))
        if change.get('after'):st.caption('After: '+filter_description(change['after']))
        source_definition(plan['baseline_spec'],'Baseline · submitted')
        source_definition(plan['challenged_spec'],'Challenge · '+('confirmed' if active else 'pending'))
        if st.checkbox('Show exact Challenge specifications',value=False,key=f'm2_{prefix}_show_specs'):
            st.json(plan['baseline_spec']);st.json(plan['challenged_spec'])
        if not active and st.button(button_label,key=f'm2_{prefix}_confirm'):
            try:
                result=execute_comparison(df,baseline_spec,challenged_spec,
                    expected_fingerprint=plan['dataset_fingerprint_sha256'])
                st.session_state[store_key]={
                    'plan':plan,'baseline_binding':baseline_binding,'result':result}
                active=True
                status_notice.success('CONFIRMED — comparison calculated from both exact definitions.')
            except AnalysisError as exc:
                st.error('Comparison could not be completed: '+str(exc))
    # Outside the Challenge expander: confirmed result remains easy to find,
    # and the evidence expander in comparison_result is not nested.
    record=st.session_state.get(store_key)
    if confirmed_comparison_matches(record,plan,baseline_binding):
        comparison_result(record['result'],heading='User-confirmed Challenge',
                          filename=f'{prefix}_comparison.json')

st.set_page_config(page_title='Finding Watch · BYTE',page_icon='📊',layout='wide')
st.markdown("""<style>
:root {color-scheme:light}
.stApp {background:#faf9f6;color:#172f44}
[data-testid="stHeader"] {background:#faf9f6}
[data-testid="stSidebar"] {background:#f0f5f3}
h1,h2,h3,[data-testid="stMarkdownContainer"] h1 {color:#172f44;letter-spacing:-.02em}
h1 {font-weight:750!important}
[data-testid="stMetricValue"] {color:#172f44}
div.stButton > button[kind="primary"], div.stFormSubmitButton > button[kind="primary"] {background:#087f78;border-color:#087f78;color:white}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:12px}
</style>""",unsafe_allow_html=True)
st.title('Finding Watch')
st.caption('Analyse  →  Challenge  →  Saved Findings (planned)')
st.markdown('Ask a question about your CSV, inspect the calculation, and challenge a result under **one changed filter**.')
with st.sidebar:
    st.header('Dataset')
    source=st.radio('Data source',['Example sales','Upload CSV'])
    upload=st.file_uploader('Choose CSV',type=['csv'],disabled=source!='Upload CSV')
    st.caption('UTF-8, comma-separated, unique headers. Maximum 10 MiB, 100,000 rows and 100 columns. Empty fields count as missing; leading-zero identifiers remain text.')
    st.caption('Manual tools work without a key. Uploads are not saved to disk. AI mode sends column names, types, your question and bounded tool results to Gemini.')
try:
    if source=='Upload CSV':
        if upload is None:
            st.info('Choose a CSV to begin.'); st.stop()
        raw=upload.getvalue()
    else:
        raw=(ROOT/'data/demo_sales.csv').read_bytes()
    df=load_csv(raw)
except AnalysisError as exc:
    st.error(str(exc)); st.stop()
source_hash=hashlib.sha256(raw).hexdigest()
st.caption(f'Current dataset · {len(df):,} records · {len(df.columns)} columns · Fingerprint {source_hash[:12]}…')
with st.expander('Preview dataset (first 100 records)',expanded=False):
    st.dataframe(df.head(100),hide_index=True)
    if len(df)>100: st.caption('Preview limited to the first 100 rows; analysis uses all rows.')
cols=list(df.columns); nums=numeric_columns(df)
labels={'Inspect dataset':'inspect_dataset','Filter rows':'filter_rows','Summarise groups':'grouped_summary',
        'Analyse time trends':'time_trend','Measure correlation':'correlation'}
st.header('Analyse')
st.caption('Choose one of five analytical tools. Results appear only after you click Run analysis.')
choice=st.selectbox('Analysis tool',list(labels))
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
        st.session_state['last_manual']={'submission':manual_submission,'output':output}
    except AnalysisError as exc:
        st.session_state.pop('last_manual',None)
        st.error(str(exc))
saved_manual=st.session_state.get('last_manual')
manual_current=bool(saved_manual and saved_manual['submission']==manual_submission)
if saved_manual:
    if not manual_current:
        st.warning('Pending edits: the previous result is hidden. Click Run analysis to submit the new settings. Old calculations have not changed.')
    else:
        analysis_result(saved_manual['output'],heading='Submitted calculation')
# M2 Challenge always binds to the specific submitted output, not controls.
if (manual_current and saved_manual['output']['tool']=='grouped_summary'):
    show_challenge_for_submitted_grouped(df,cols,saved_manual['output'],
        {'kind':'manual','dataset':source_hash,'submission':saved_manual['submission'],
         'label':'Manual calculation submitted with the settings above'},
        prefix='manual',title='Challenge this submitted grouped finding',
        button_label='Run confirmed manual comparison')


st.divider()
st.header('Ask your dataset')
st.caption('Gemini can suggest which tool to use. Calculations come from Python; model commentary is not independently verified.')
from agent import AgentError, ask, available_models, configuration
_, model = configuration()
st.caption('Configured model: '+model+' · An approved grouped result can be used as the baseline for a follow-up Challenge.')
with st.expander('Connection setup'):
    st.write('The API key is read privately from .env. Model listing checks access, not inference quota or tool compatibility.')
    if st.button('Check available models'):
        try:
            st.write(available_models())
        except AgentError as exc:
            st.error(str(exc))
    st.caption('To change models, set GEMINI_MODEL in your .env file and rerun. No automatic model switching.')
consent=st.checkbox('Use Gemini for this question: send the question, column names/types and analysis results (which may include matching rows).')
# Existing results may be used as a follow-up baseline ONLY if the user
# explicitly selects the exact submitted finding; never silently reuse one.
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
baseline_set_id=hashlib.sha256(json.dumps(current_baselines,sort_keys=True,
    ensure_ascii=False).encode()).hexdigest()[:16]
baseline_label=st.selectbox('Follow-up Challenge baseline (optional)',
    ['No prior baseline']+list(current_baselines),index=0,
    key='ai_baseline_source_'+baseline_set_id)
if baseline_label!='No prior baseline':
    st.caption('Only this explicitly selected submitted grouped definition will be supplied to Gemini.')
with st.form('question_form'):
    question=st.text_input('Question',max_chars=4000,placeholder='Which category has the highest total revenue?')
    submit=st.form_submit_button('Ask Gemini',disabled=not consent)
if submit and consent:
    # New question: do not preselect a business definition from an old clarification.
    for key in ('clarify_method','clarify_group','clarify_metric','clarify_context'):
        st.session_state.pop(key,None)
    st.session_state.pop('last_ai_comparison',None)
    st.session_state.pop('last_clarified',None)
    with st.spinner('Selecting tools and analysing…'):
        try:
            selected_baseline=current_baselines.get(baseline_label)
            answer=ask(df,question,baseline_spec=(selected_baseline or {}).get('spec'))
            st.session_state['last_answer']={'dataset_fingerprint':source_hash,'submitted_question':question,'response':answer,
                'baseline_reference':selected_baseline}
        except AgentError as exc:
            st.session_state.pop('last_answer',None)
            st.error(str(exc))
saved=st.session_state.get('last_answer')
if saved and saved['dataset_fingerprint']!=source_hash:
    st.session_state.pop('last_answer',None)
    st.session_state.pop('last_clarified',None)
    saved=None
if saved:
    answer=saved['response']
    submitted=saved['submitted_question']
    st.caption('Original submitted question: '+submitted)
    changed_question=(question!=submitted)
    if changed_question:
        st.warning('Pending question edits. This response belongs to the previous submitted question; send your new question to replace it.')
    status=answer.get('status','unverified')
    if status=='clarification' and not changed_question:
        st.info('Clarification needed — no analysis has run for this question.')
        st.markdown('### Clarify your original question')
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
            with st.form('clarify_definition'):
                group=st.selectbox('Which column should be compared?',group_candidates(cols,submitted),
                    index=None,placeholder='Choose a column',key='clarify_group')
                measure=st.selectbox('Which calculation should define “best”?',list(options),
                    index=None,placeholder='Choose a calculation',key='clarify_metric')
                clarify_submit=st.form_submit_button('Analyse with my choices',type='primary')
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
                            'chosen':definition,'output':output}
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
                        heading='Calculated from your explicit definition',question=submitted)
                    if clarified['output']['tool']=='grouped_summary':
                        show_challenge_for_submitted_grouped(df,cols,clarified['output'],
                            {'kind':'clarified','dataset':source_hash,'question':submitted,
                             'chosen':clarified['chosen'],
                             'label':'Explicitly clarified answer to: '+submitted[:120]},
                            prefix='clarified',title='Challenge this clarified grouped finding',
                            button_label='Run confirmed clarified comparison')
                else:
                    st.warning('Pending clarification edits — the previous calculation and Challenge are hidden until you submit.')
        elif method=='Explain the missing context (dates or other details)':
            st.caption('For example: “Dates are DD/MM/YYYY” or “compare records by week”. Your explanation is context for Gemini, not executable code.')
            with st.form('clarify_context_form'):
                details=st.text_area('Your clarification',max_chars=2000,key='clarify_context')
                contextual_submit=st.form_submit_button('Continue with original question and my clarification',type='primary')
            if contextual_submit:
                if not details.strip():
                    st.error('Enter the missing information before continuing.')
                elif not consent:
                    st.error('Enable Gemini consent to send contextual clarification.')
                else:
                    try:
                        with st.spinner('Reconsidering the original question with your clarification…'):
                            new_response=ask(df,submitted,clarification_context=details)
                        st.session_state.pop('last_clarified',None)
                        st.session_state.pop('last_ai_comparison',None)
                        st.session_state['last_answer']={'dataset_fingerprint':source_hash,
                            'submitted_question':submitted,'response':new_response,
                            'clarification_context':details,'baseline_reference':None}
                        st.rerun()
                    except AgentError as exc:
                        st.error(str(exc))
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
    elif status in ('error','limited','unverified'):
        st.error('Analysis not completed: '+str(answer.get('answer','No verified calculation available.')))
    else:
        st.caption('Python evidence is listed below. The model explanation remains unverified.')

    for i,event in enumerate(answer.get('trace',[]) if not changed_question else [],1):
        result=event.get('result',{})
        if ('rows' in result and result.get('evidence',{}).get('calculation_status')=='completed'):
            analysis_result(result,heading=f'Calculation {i} · {event["tool"]}',model_tool=True,question=submitted)
        elif result.get('error'):
            st.error('Tool could not complete: '+str(result['error']))
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
            comparison_result(confirmed['result'],heading='User-confirmed comparison',filename='confirmed_comparison.json')
    with st.expander('How this response was produced'):
        st.caption('Original question, model status and tool trace. Tool results do not prove a model interpretation is correct.')
        st.json({'question':submitted,'model_proposal_status_at_creation' if status=='comparison_pending' else 'model_status':status,
                 'model':answer.get('model',model),
                 'trace':answer.get('trace',[]),'calculation_verified':answer.get('calculation_verified',False),
                 'explanation_verified':answer.get('explanation_verified',False),
                 'user_clarification_context':saved.get('clarification_context'),
                 'explicit_baseline_reference':saved.get('baseline_reference')})
    evidence_download(answer,'ai_analysis.json',
        'Download original Gemini proposal JSON' if status=='comparison_pending' else 'Download AI analysis evidence')

st.divider()
st.caption('Saved Findings · planned for a later milestone. Nothing is stored or revisited in this version.')
