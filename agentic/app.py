from pathlib import Path
import json
import hashlib
import pandas as pd
import streamlit as st
from engine import AnalysisError, load_csv, numeric_columns, run_tool
from comparisons import prepare_comparison, execute_comparison

ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='BYTE Data Analyst',page_icon='📊',layout='wide')
st.title('BYTE Data Analyst')
st.caption('M2 candidate · Five analytical tools plus confirmation-gated Finding Challenge')
st.info('Use manual tools or Gemini. Comparisons change exactly one filter and run only after explicit confirmation. Persistent memory is not implemented.')
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
st.write(f'**{len(df):,} rows · {len(df.columns)} columns**')
with st.expander('Dataset preview',expanded=True):
    st.dataframe(df.head(100),hide_index=True)
    if len(df)>100: st.caption('Preview limited to the first 100 rows; analysis uses all rows.')
cols=list(df.columns); nums=numeric_columns(df)
labels={'Inspect dataset':'inspect_dataset','Filter rows':'filter_rows','Summarise groups':'grouped_summary',
        'Analyse time trends':'time_trend','Measure correlation':'correlation'}
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
    args['operation']=st.selectbox('Calculation',['sum','mean','min','max','count_rows'])
    if args['operation']!='count_rows':
        if nums: args['metric']=st.selectbox('Numeric metric',nums)
        else: st.warning('No numeric columns. Choose count_rows.'); ready=False
elif choice=='Analyse time trends':
    args['date_column']=st.selectbox('Date column',cols)
    args['date_format']=st.selectbox('Exact date format',['%Y-%m-%d','%d/%m/%Y','%m/%d/%Y'])
    args['frequency']=st.selectbox('Time interval',['month','week','day'])
    args['operation']=st.selectbox('Calculation',['sum','mean','count_rows'])
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
if saved_manual:
    if saved_manual['submission'] != manual_submission:
        st.caption('Analysis settings or dataset changed. The previous result is hidden; click Run analysis to submit the new settings.')
    else:
        output=saved_manual['output']
        st.subheader('Results — submitted analysis')
        st.caption('Dataset SHA-256: '+source_hash+' · Tool: '+output['tool'])
        st.dataframe(pd.DataFrame(output['rows']),hide_index=True)
        st.json(output['metadata'])
        with st.expander('Executed specification and calculation evidence'):
            st.json(output['evidence'])
        st.download_button('Download result JSON',json.dumps(output,indent=2,allow_nan=False),
                           'analysis_result.json','application/json')
# Manual M2: the previous SUBMITTED grouped analysis, never unsaved controls,
# is the only baseline. The changed definition is always previewed first.
if (saved_manual and saved_manual['submission']==manual_submission
        and saved_manual['output']['tool']=='grouped_summary'):
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
            st.write('Changed assumption:',manual_plan['changed_condition'])
            st.write('Baseline submitted specification')
            st.json(manual_plan['baseline_spec'])
            st.write('Challenged specification — pending confirmation')
            st.json(manual_plan['challenged_spec'])
            if st.button('Run confirmed manual comparison',key='m2_manual_confirm'):
                comparison=execute_comparison(df,baseline_spec,challenged_spec,
                    expected_fingerprint=manual_plan['dataset_fingerprint_sha256'])
                st.session_state['last_manual_comparison']={
                    'plan':manual_plan,'result':comparison,'baseline_submission':manual_submission}
        except AnalysisError as exc:
            st.caption('Comparison not ready: '+str(exc))
        stored_comparison=st.session_state.get('last_manual_comparison')
        if (stored_comparison and stored_comparison['baseline_submission']==manual_submission
                and stored_comparison['plan']==manual_plan):
            c=stored_comparison['result']
            st.subheader('Confirmed comparison — deterministic evidence')
            st.dataframe(pd.DataFrame(c['comparison']['displayed_results']),hide_index=True)
            st.write('All baseline leaders:',c['comparison']['baseline_leaders'])
            st.write('All challenged leaders:',c['comparison']['challenged_leaders'])
            st.caption('All groups are matched by value, not position. Absent groups are not zeros.')
            st.json(c)
            st.download_button('Download manual comparison JSON',
                json.dumps(c,indent=2,allow_nan=False), 'manual_comparison.json','application/json')

st.divider()
st.subheader('Ask your dataset')
from agent import AgentError, ask, available_models, configuration
_, model = configuration()
st.caption(f'Model: {model}. You can challenge the last submitted grouped result; other questions require their own context.')
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
    saved=None
if saved:
    answer=saved['response']
    st.caption('Submitted question: '+saved['submitted_question'])
    if question != saved['submitted_question']:
        st.warning('Unsubmitted question edits are pending. Evidence below belongs ONLY to the submitted question.')
    st.caption('Dataset SHA-256: '+saved['dataset_fingerprint'])
    st.caption('Status: '+answer['status'])
    st.write(answer['answer'])
    st.caption('Model explanation is NOT independently verified. Completed calculations appear in the tool evidence below; relevance to the question must be checked.')
    for i,event in enumerate(answer['trace'],1):
        with st.expander(f"Tool {i}: {event['tool']}",expanded=True):
            st.json(event['arguments'])
            if 'rows' in event['result']:
                st.dataframe(pd.DataFrame(event['result']['rows']),hide_index=True)
                st.json(event['result']['metadata'])
                st.json(event['result']['evidence'])
            else: st.json(event['result'])
    proposal=answer.get('pending_comparison')
    if proposal:
        st.warning('MODEL PROPOSAL — no comparison has been calculated or approved yet.')
        st.write('Changed condition:',proposal['changed_condition'])
        st.write('Baseline definition'); st.json(proposal['baseline_spec'])
        st.write('Challenged definition'); st.json(proposal['challenged_spec'])
        st.caption('Confirm only if both definitions accurately represent your intended questions.')
        if st.button('Confirm and run proposed comparison',key='m2_ai_confirm',
                     disabled=question!=saved['submitted_question']):
            try:
                comparison=execute_comparison(df,proposal['baseline_spec'],proposal['challenged_spec'],
                    expected_fingerprint=proposal['dataset_fingerprint_sha256'])
                st.session_state['last_ai_comparison']={
                    'proposal':proposal,'question':saved['submitted_question'],
                    'dataset_fingerprint':source_hash,'result':comparison}
            except AnalysisError as exc:
                st.error(str(exc))
        confirmed=st.session_state.get('last_ai_comparison')
        if (confirmed and confirmed['proposal']==proposal
                and confirmed['dataset_fingerprint']==source_hash
                and confirmed['question']==saved['submitted_question']):
            c=confirmed['result']
            st.subheader('User-confirmed comparison — deterministic calculations')
            st.dataframe(pd.DataFrame(c['comparison']['displayed_results']),hide_index=True)
            st.write('Baseline tied leaders:',c['comparison']['baseline_leaders'])
            st.write('Challenged tied leaders:',c['comparison']['challenged_leaders'])
            st.caption('Calculations verified by Python; model explanation is not verified.')
            with st.expander('Full comparison evidence'):
                st.json(c)
            st.download_button('Download confirmed comparison JSON',
                json.dumps(c,indent=2,allow_nan=False),'confirmed_comparison.json','application/json')
    st.download_button('Download AI analysis evidence',json.dumps(answer,indent=2,allow_nan=False),
        'ai_analysis.json','application/json')
