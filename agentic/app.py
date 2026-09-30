from pathlib import Path
import json
import pandas as pd
import streamlit as st
from engine import AnalysisError, load_csv, numeric_columns, run_tool

ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='BYTE Data Analyst',page_icon='📊',layout='wide')
st.title('BYTE Data Analyst')
st.caption('Phase 3 · Data analysis with Gemini')
st.info('Use the manual tools or ask Gemini to select tools. Persistent memory is not implemented yet.')
with st.sidebar:
    st.header('Dataset')
    source=st.radio('Data source',['Example sales','Upload CSV'])
    upload=st.file_uploader('Choose CSV',type=['csv'],disabled=source!='Upload CSV')
    st.caption('UTF-8, comma-separated, unique headers. Maximum 10 MiB, 100,000 rows and 100 columns. Empty fields count as missing.')
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
if st.button('Run analysis',type='primary',disabled=not ready):
    try:
        output=run_tool(df,labels[choice],args)
        st.subheader('Results')
        st.dataframe(pd.DataFrame(output['rows']),hide_index=True)
        st.json(output['metadata'])
        with st.expander('Tool evidence'):
            st.json({'tool':output['tool'],'arguments':args,'dataset_id':output['dataset_id']})
        st.download_button('Download result JSON',json.dumps(output,indent=2,allow_nan=False),'analysis_result.json','application/json')
    except AnalysisError as exc:
        st.error(str(exc))
st.divider()
st.subheader('Ask your dataset')
from agent import AgentError, ask, available_models, configuration
_, model = configuration()
st.caption(f'Model: {model}. Each question is independent; include all necessary context.')
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
    with st.spinner('Selecting tools and analysing…'):
        try:
            answer=ask(df,question)
            st.session_state['last_answer']={'dataset':raw,'response':answer}
        except AgentError as exc:
            st.session_state.pop('last_answer',None)
            st.error(str(exc))
saved=st.session_state.get('last_answer')
if saved and saved['dataset']!=raw:
    st.session_state.pop('last_answer',None)
    saved=None
if saved:
    answer=saved['response']
    st.caption('Status: '+answer['status'])
    st.write(answer['answer'])
    st.caption('Model explanation: check it against the computed evidence below.')
    for i,event in enumerate(answer['trace'],1):
        with st.expander(f"Tool {i}: {event['tool']}",expanded=True):
            st.json(event['arguments'])
            if 'rows' in event['result']:
                st.dataframe(pd.DataFrame(event['result']['rows']),hide_index=True)
                st.json(event['result']['metadata'])
            else: st.json(event['result'])
    st.download_button('Download AI analysis evidence',json.dumps(answer,indent=2,allow_nan=False),
        'ai_analysis.json','application/json')
