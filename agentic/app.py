from pathlib import Path
import json
import pandas as pd
import streamlit as st
from engine import AnalysisError, load_csv, numeric_columns, run_tool

ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='BYTE Data Analyst',page_icon='📊',layout='wide')
st.title('BYTE Data Analyst')
st.caption('Phase 2 · Local analysis workbench')
st.info('Run verified Python calculations below. AI chat and persistent memory arrive in later phases.')
with st.sidebar:
    st.header('Dataset')
    source=st.radio('Data source',['Example sales','Upload CSV'])
    upload=st.file_uploader('Choose CSV',type=['csv'],disabled=source!='Upload CSV')
    st.caption('UTF-8, comma-separated, unique headers. Maximum 10 MiB, 100,000 rows and 100 columns. Empty fields count as missing.')
    st.caption('No API key required. This version makes no model requests and does not save uploads.')
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
st.text_input('Ask in natural language',disabled=True,placeholder='AI tool selection will be connected in Phase 3')
