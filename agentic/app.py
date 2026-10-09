from pathlib import Path
import json
import hashlib
import pandas as pd
import streamlit as st
from engine import AnalysisError, load_csv, numeric_columns, run_tool
from comparisons import prepare_comparison, execute_comparison
from presentation import metric_choices,group_candidates,missing_product_context,filter_description
from ui_components import analysis_result,comparison_result,source_definition,evidence_download

ROOT=Path(__file__).resolve().parent
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
# Manual M2: the previous SUBMITTED grouped analysis, never unsaved controls,
# is the only baseline. The changed definition is always previewed first.
if (saved_manual and saved_manual['submission']==manual_submission
        and saved_manual['output']['tool']=='grouped_summary'):
    st.header('Challenge')
    st.caption('Change exactly one filter. Two definitions are previewed before approval.')
    with st.expander('Challenge this submitted grouped finding', expanded=False):
        manual_plan=None
        baseline_spec=saved_manual['output']['evidence']['executed_spec']
        before_conditions=baseline_spec['filters']
        available_actions=(['Add condition'] if len(before_conditions)<8 else []) + (
            ['Remove condition','Replace condition'] if before_conditions else [])
        mode=st.selectbox('Change exactly one condition', available_actions, key='m2_manual_mode')
        challenged_conditions=[dict(c) for c in before_conditions]
        index=None
        if mode in ('Remove condition','Replace condition'):
            index=st.selectbox('Condition to change',range(len(before_conditions)),
                               format_func=lambda i:f'{i+1}: {before_conditions[i]}',key='m2_index')
        if mode!='Remove condition':
            fcol=st.selectbox('Challenged filter column',cols,key='m2_column')
            op=st.selectbox('Challenged filter operator',
                ['eq','ne','gt','ge','lt','le','contains','is_missing','not_missing'],key='m2_operator')
            condition={'field':fcol,'operator':op}
            if op not in ('is_missing','not_missing'):
                condition['value']=st.text_input('Challenged filter value',key='m2_value')
        if mode=='Add condition':
            challenged_conditions.append(condition)
        elif mode=='Remove condition':
            challenged_conditions.pop(index)
        else:
            challenged_conditions[index]=condition
        challenged_spec={**baseline_spec,'filters':challenged_conditions}
        try:
            manual_plan=prepare_comparison(df,baseline_spec,challenged_spec)
            st.warning('PENDING — comparison not calculated. Inspect both definitions before approving.')
            st.markdown('**Exactly one changed condition**')
            changed=manual_plan['changed_condition']
            st.caption('Change: '+changed['kind'])
            if changed.get('before'): st.caption('Before: '+filter_description(changed['before']))
            if changed.get('after'): st.caption('After: '+filter_description(changed['after']))
            source_definition(manual_plan['baseline_spec'],'Baseline · previously submitted')
            source_definition(manual_plan['challenged_spec'],'Challenge · pending approval')
            with st.expander('How the proposed definitions are structured'):
                st.json(manual_plan['baseline_spec'])
                st.json(manual_plan['challenged_spec'])
            if st.button('Run confirmed manual comparison',key='m2_manual_confirm'):
                comparison=execute_comparison(df,baseline_spec,challenged_spec,
                    expected_fingerprint=manual_plan['dataset_fingerprint_sha256'])
                st.session_state['last_manual_comparison']={
                    'plan':manual_plan,'result':comparison,'baseline_submission':manual_submission}
        except AnalysisError as exc:
            st.caption('Comparison not ready: '+str(exc))
        stored_comparison=st.session_state.get('last_manual_comparison')
        if stored_comparison and stored_comparison['plan'] != manual_plan:
            st.info('Pending Challenge edits — the earlier confirmed comparison is hidden until these definitions are confirmed.')
        if (stored_comparison and stored_comparison['baseline_submission']==manual_submission
                and stored_comparison['plan']==manual_plan):
            comparison_result(stored_comparison['result'],heading='User-confirmed Challenge',filename='manual_comparison.json')


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
with st.form('question_form'):
    question=st.text_input('Question',max_chars=4000,placeholder='Which category has the highest total revenue?')
    submit=st.form_submit_button('Ask Gemini',disabled=not consent)
if submit and consent:
    st.session_state.pop('last_ai_comparison',None)
    st.session_state.pop('last_clarified',None)
    with st.spinner('Selecting tools and analysing…'):
        try:
            previous=st.session_state.get('last_answer')
            baseline_from_previous=None
            if previous and previous.get('dataset_fingerprint')==source_hash:
                for event in reversed(previous['response'].get('trace',[])):
                    evidence=event.get('result',{}).get('evidence',{})
                    if evidence.get('executed_spec',{}).get('tool')=='grouped_summary':
                        baseline_from_previous=evidence['executed_spec']
                        break
            if baseline_from_previous is None:
                previous_manual=st.session_state.get('last_manual')
                if (previous_manual and previous_manual['submission']['fingerprint']==source_hash
                        and previous_manual['output']['tool']=='grouped_summary'):
                    baseline_from_previous=previous_manual['output']['evidence']['executed_spec']
            answer=ask(df,question,baseline_spec=baseline_from_previous)
            st.session_state['last_answer']={'dataset_fingerprint':source_hash,'submitted_question':question,'response':answer}
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
    if status=='clarification':
        st.info('Clarification needed — no analysis has run for this question.')
        st.markdown('### Tell us what you want to compare')
        if answer.get('answer'):
            st.caption('Model clarification request (not an executable definition): '+answer['answer'])
        if missing_product_context(cols,submitted):
            st.warning('Your question mentions “product”, but this CSV has no column containing “product”. You may choose an existing grouping column, or upload a dataset that has product data. Choosing another column changes the question.')
        st.caption('Select an actual CSV column and what “best” means. Nothing is selected automatically.')
        metric_options=metric_choices(cols,nums)
        with st.form('clarify_definition'):
            group=st.selectbox('Which column should be compared?',group_candidates(cols,submitted),
                index=None,placeholder='Choose a column',key='clarify_group')
            measure=st.selectbox('Which calculation should define “best”?',list(metric_options),
                index=None,placeholder='Choose a calculation',key='clarify_metric')
            clarify_submit=st.form_submit_button('Analyse with my choices',type='primary',disabled=changed_question)
        if clarify_submit:
            if not group or not measure:
                st.error('Choose both a grouping column and a calculation before analysing.')
            else:
                chosen=metric_options[measure]
                chosen_args={'group':group,'operation':chosen['operation']}
                if chosen['metric'] is not None: chosen_args['metric']=chosen['metric']
                try:
                    output=run_tool(df,'grouped_summary',chosen_args)
                    st.session_state['last_clarified']={
                        'dataset_fingerprint':source_hash,'submitted_question':submitted,
                        'chosen':chosen_args,'output':output}
                except AnalysisError as exc:
                    st.session_state.pop('last_clarified',None)
                    st.error(str(exc))
        clarified=st.session_state.get('last_clarified')
        if (clarified and clarified['dataset_fingerprint']==source_hash
                and clarified['submitted_question']==submitted and not changed_question):
            if group is not None and measure is not None:
                expected={'group':group,'operation':metric_options[measure]['operation']}
                if metric_options[measure]['metric'] is not None:
                    expected['metric']=metric_options[measure]['metric']
                if clarified['chosen']==expected:
                    analysis_result(clarified['output'],heading='Calculated using your chosen definition',question=submitted)
                else:
                    st.warning('Clarification selections changed. Previous calculation hidden until you submit these choices.')
            else:
                st.warning('Clarification choices are now pending. Submit them to display an updated calculation.')
    elif status=='comparison_pending':
        st.warning('PENDING USER CONFIRMATION — no Challenge calculation has run.')
    elif status in ('error','limited','unverified'):
        st.error('Analysis not completed: '+str(answer.get('answer','No verified calculation available.')))
    else:
        st.caption('Python evidence is listed below. The model explanation remains unverified.')

    for i,event in enumerate(answer.get('trace',[]),1):
        result=event.get('result',{})
        if ('rows' in result and result.get('evidence',{}).get('calculation_status')=='completed'):
            analysis_result(result,heading=f'Calculation {i} · {event["tool"]}',model_tool=True,question=submitted)
        elif result.get('error'):
            st.error('Tool could not complete: '+str(result['error']))
    if status=='evidence_available' and answer.get('answer'):
        with st.expander('Gemini explanation · not independently verified'):
            st.write(answer['answer'])
    proposal=answer.get('pending_comparison')
    if proposal:
        st.subheader('Proposed Challenge · not yet approved')
        st.warning('These model-suggested definitions have not been calculated or approved.')
        changed=proposal['changed_condition']
        st.caption('Exactly one changed condition: '+changed['kind'])
        if changed.get('before'): st.caption('Before: '+filter_description(changed['before']))
        if changed.get('after'): st.caption('After: '+filter_description(changed['after']))
        source_definition(proposal['baseline_spec'],'Baseline · proposed definition')
        source_definition(proposal['challenged_spec'],'Challenge · proposed definition')
        with st.expander('Inspect both exact specifications before confirmation'):
            st.json(proposal['baseline_spec'])
            st.json(proposal['challenged_spec'])
        st.caption('Confirm only if BOTH definitions match the question you intended to ask.')
        if st.button('Confirm and run proposed comparison',key='m2_ai_confirm',
                     disabled=changed_question):
            try:
                comparison=execute_comparison(df,proposal['baseline_spec'],proposal['challenged_spec'],
                    expected_fingerprint=proposal['dataset_fingerprint_sha256'])
                st.session_state['last_ai_comparison']={
                    'proposal':proposal,'question':submitted,
                    'dataset_fingerprint':source_hash,'result':comparison}
            except AnalysisError as exc:
                st.error(str(exc))
        confirmed=st.session_state.get('last_ai_comparison')
        if (confirmed and confirmed['proposal']==proposal and not changed_question
                and confirmed['dataset_fingerprint']==source_hash
                and confirmed['question']==submitted):
            comparison_result(confirmed['result'],heading='User-confirmed comparison',filename='confirmed_comparison.json')
    with st.expander('How this response was produced'):
        st.caption('Original question, model status and tool trace. Tool results do not prove a model interpretation is correct.')
        st.json({'question':submitted,'status':status,'model':answer.get('model',model),
                 'trace':answer.get('trace',[]),'calculation_verified':answer.get('calculation_verified',False),
                 'explanation_verified':answer.get('explanation_verified',False)})
    evidence_download(answer,'ai_analysis.json','Download AI analysis evidence')

st.divider()
st.caption('Saved Findings · planned for a later milestone. Nothing is stored or revisited in this version.')
