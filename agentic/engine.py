"""Deterministic read-only analysis; only validated specifications are executed."""
import csv
import io
import math
import json
import hashlib
import re
import pandas as pd
from pandas.api.types import is_numeric_dtype, is_bool_dtype, is_integer_dtype
import numpy as np
from specs import AnalysisSpec, SpecError

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 100_000
MAX_COLUMNS = 100
NUMERIC_TEXT = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')
LEADING_ZERO = re.compile(r'^[+-]?0\d+(?:\.\d*)?(?:[eE][+-]?\d+)?$')
IDENTIFIER_NAME = re.compile(r'(?:^id$|(?:^|[_\s-])id$|identifier|postal|post.?code|pin.?code|zip|phone|mobile|account|sku|serial|reference|^code$|[_\s-]code$|date|time)',re.I)

class AnalysisError(ValueError):
    """Input error safe to show to user."""


def load_csv(raw: bytes) -> pd.DataFrame:
    if not raw or len(raw)>MAX_BYTES:
        raise AnalysisError('Upload a non-empty CSV no larger than 10 MiB.')
    try:
        text=raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise AnalysisError('Save the CSV with UTF-8 encoding.') from None
    if '\x00' in text:
        raise AnalysisError('The file contains null bytes; upload a text CSV.')
    try:
        reader=csv.reader(io.StringIO(text,newline=''),strict=True)
        header=next(reader,[])
        if not header or len(header)>MAX_COLUMNS:
            raise AnalysisError('CSV must have a header with 1–100 columns.')
        if any(not h.strip() for h in header) or len({h.strip() for h in header})!=len(header):
            raise AnalysisError('Column names must be non-empty and unique after trimming spaces.')
        count=0
        for row in reader:
            if not row:
                continue
            if len(row)!=len(header):
                raise AnalysisError(f'Record {count+2} has {len(row)} fields; expected {len(header)}.')
            count+=1
            if count>MAX_ROWS:
                raise AnalysisError('CSV exceeds 100,000 data rows.')
        if not count:
            raise AnalysisError('CSV has a header but no data rows.')
        # Initially read EVERYTHING as exact text to avoid losing leading zeroes
        # and to keep ambiguous identifiers out of numeric calculations.
        df=pd.read_csv(io.StringIO(text),dtype='string',keep_default_na=False,na_values=[''])
        df.columns=[h.strip() for h in header]
        kept=[]
        for name in df:
            values=df[name].dropna()
            if IDENTIFIER_NAME.search(name) or values.empty:
                kept.append(name)
                continue
            if not values.map(lambda v: bool(NUMERIC_TEXT.fullmatch(v)) and not bool(LEADING_ZERO.fullmatch(v))).all():
                kept.append(name)
                continue
            # Preserve potentially identifying big integral codes and avoid float rounding.
            if values.map(lambda v: bool(re.fullmatch(r'[+-]?\d{16,}',v))).any():
                kept.append(name)
                continue
            try:
                numeric_values=pd.to_numeric(df[name],errors='raise')
                if not numeric_values.dropna().map(lambda v: math.isfinite(float(v))).all():
                    kept.append(name)
                    continue
                df[name]=numeric_values
            except (ValueError,TypeError,OverflowError):
                kept.append(name)
        df.attrs['source_sha256']=hashlib.sha256(raw).hexdigest()
        df.attrs['text_columns']=kept
        df.attrs['parsing_policy']='Conservative: identifier-like names, leading-zero values, dates and mixed text stay text; other all-finite numeric columns parsed.'
        return df
    except (csv.Error,pd.errors.ParserError,pd.errors.EmptyDataError) as exc:
        raise AnalysisError('Malformed CSV. Check delimiters and quotation marks.') from exc


def dataset_fingerprint(df):
    if 'source_sha256' in df.attrs:
        return df.attrs['source_sha256']
    # Fallback for caller-generated DataFrames; source CSVs use the raw-byte hash.
    body={'columns':[str(c) for c in df.columns],
          'types':[str(df[c].dtype) for c in df],
          'data':df.to_json(orient='split',date_format='iso',double_precision=15)}
    return hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()


def numeric_columns(df):
    return [c for c in df if is_numeric_dtype(df[c]) and not is_bool_dtype(df[c])]


def column(df,name):
    if not isinstance(name, str) or not name:
        raise AnalysisError('Column name must be non-empty text.')
    if name not in df.columns:
        raise AnalysisError(f'Unknown column: {name}')
    return df[name]


def numeric(df,name):
    s=column(df,name)
    if name not in numeric_columns(df):
        raise AnalysisError(f'{name} is text/ambiguous, not a validated numeric metric. Preserve identifiers; clean or explicitly convert a copy before upload.')
    if any(not math.isfinite(float(v)) for v in s.dropna()):
        raise AnalysisError(f'{name} contains non-finite values; clean these before analysis.')
    return s


def _safe_cell(value):
    """Serialize scalars WITHOUT forcing arbitrary precision Python ints to floats.

    pandas to_json / inferred float columns can silently lose huge integers,
    especially in the presence of null values. Keep Python ints through JSON.
    """
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if math.isnan(number):
            return None
        if not math.isfinite(number):
            raise AnalysisError('Calculation produced a non-finite value; numeric range is unsupported.')
        return number
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, str):
        return value
    raise AnalysisError('Unsupported result value type; cannot serialize without loss.')


def result(tool,frame,**metadata):
    rows=[{str(key):_safe_cell(val) for key,val in zip(frame.columns, record)}
          for record in frame.itertuples(index=False,name=None)]
    return {'tool':tool,'metadata':metadata,'rows':rows}


def _safe_aggregate(values, operation):
    """Accumulate integer sums in Python ints, never fixed-width numpy/pandas.

    Floating sums use math.fsum, rejecting overflow instead of making a
    seemingly valid but incorrect result. Means of integers above 2**53 are
    refused because conversion to float could silently destroy units.
    """
    valid = values.dropna()
    if valid.empty:
        return None
    if operation == 'min':
        return _safe_cell(valid.min())
    if operation == 'max':
        return _safe_cell(valid.max())
    integer = is_integer_dtype(values.dtype)
    if operation == 'sum' and integer:
        return sum(int(v) for v in valid)  # Python int has no 64-bit wraparound
    if operation == 'mean' and integer and any(abs(int(v)) > 2**53 for v in valid):
        raise AnalysisError('Integer mean exceeds the exact floating-point precision range (2**53). Rescale the metric or use sum/min/max.')
    try:
        total = math.fsum(float(v) for v in valid)
    except (ValueError, OverflowError):
        raise AnalysisError('Numeric accumulation exceeds supported finite precision; no result was produced.') from None
    if not math.isfinite(total):
        raise AnalysisError('Numeric accumulation is non-finite; no result was produced.')
    return total if operation == 'sum' else total / len(valid)


def inspect_dataset(df):
    table=pd.DataFrame([{'column':c,'dtype':str(df[c].dtype),
        'missing':int(df[c].isna().sum()),'unique_non_missing':int(df[c].nunique())} for c in df])
    return result('inspect_dataset',table,total_rows=len(df),total_columns=len(df.columns),
                  duplicate_rows=int(df.duplicated().sum()),
                  missing_policy='Only empty CSV fields are missing.')


def _condition(df,field,operator,value=None):
    s=column(df,field)
    if operator=='is_missing':
        return s.isna(),None
    if operator=='not_missing':
        return s.notna(),None
    if operator=='contains':
        if value is None:
            raise AnalysisError('Contains filter requires a text value.')
        return s.astype('string').str.contains(str(value),regex=False,na=False).fillna(False),value
    if not isinstance(operator,str) or operator not in ('eq','ne','gt','ge','lt','le'):
        raise AnalysisError('Unknown filter operator.')
    if field in numeric_columns(df):
        numeric(df,field)
        try:
            if type(value) is bool:
                raise ValueError
            value=float(value)
            if not math.isfinite(value):
                raise ValueError
        except (TypeError,ValueError,OverflowError):
            raise AnalysisError('Enter a finite numeric filter value.') from None
    elif is_bool_dtype(s):
        if str(value).lower() not in {'true','false'}:
            raise AnalysisError('Boolean filter value must be true or false.')
        value=str(value).lower()=='true'
    elif operator not in {'eq','ne'}:
        raise AnalysisError('Ordered comparisons require an unambiguous numeric column.')
    else:
        value=str(value)
    return (getattr(s,operator)(value) & s.notna()).fillna(False),value


def filter_rows(df,field,operator,value=None,limit=100):
    if type(limit) is not int or not 1<=limit<=1000:
        raise AnalysisError('Display limit must be an integer between 1 and 1000.')
    mask,normalized=_condition(df,field,operator,value)
    selected=df.loc[mask]
    out=result('filter_rows',selected.head(limit),matched_rows=len(selected),
               returned_rows=min(limit,len(selected)),truncated=len(selected)>limit,
               field=field,operator=operator,value=normalized)
    return out


def grouped_summary(df,group,metric=None,operation='sum'):
    column(df,group)
    if not isinstance(operation,str) or operation not in ('sum','mean','min','max','count_rows'):
        raise AnalysisError('Unsupported aggregation.')
    if df[group].nunique(dropna=False)>1000:
        raise AnalysisError('Choose a grouping column with at most 1,000 distinct values.')
    if operation!='count_rows':
        numeric(df,metric)
    if df.empty:
        raise AnalysisError('No selected rows match the filters.')
    rows=[]
    for label,part in df.groupby(group,dropna=False,sort=False):
        value=len(part) if operation=='count_rows' else _safe_aggregate(part[metric],operation)
        row={'group_value':_safe_cell(label), 'value':value, 'row_count':len(part)}
        if operation!='count_rows':
            row['non_missing_metric_count']=int(part[metric].count())
        rows.append(row)
    # Do not create a mixed nullable float column; values may exceed int64.
    rows.sort(key=lambda r:(r['value'] is None,-r['value'] if r['value'] is not None else 0))
    out=pd.DataFrame(rows,dtype=object)
    return result('grouped_summary',out,group_column=group,metric=metric,operation=operation,
                  policy='Missing group labels retained as null; missing metrics excluded; all-missing sums remain null.')


def time_trend(df,date_column,metric=None,frequency='month',date_format='%Y-%m-%d',operation='sum'):
    if not isinstance(date_format,str) or date_format not in ('%Y-%m-%d','%d/%m/%Y','%m/%d/%Y') or not isinstance(frequency,str) or frequency not in ('day','week','month'):
        raise AnalysisError('Select an explicit supported date format and frequency.')
    if not isinstance(operation,str) or operation not in ('sum','mean','count_rows'):
        raise AnalysisError('Unsupported time aggregation.')
    s=column(df,date_column)
    dates=pd.to_datetime(s.astype('string'),format=date_format,errors='coerce',exact=True)
    invalid=int((s.notna()&dates.isna()).sum())
    if invalid:
        raise AnalysisError(f'{invalid} non-empty dates do not match {date_format}. Correct the format or data.')
    if not dates.notna().any():
        raise AnalysisError('No valid dates to analyse.')
    tmp=pd.DataFrame({'period':dates.dt.to_period({'day':'D','week':'W-SUN','month':'M'}[frequency]).dt.start_time},index=df.index)
    if operation!='count_rows':
        tmp['metric']=numeric(df,metric)
    buckets=tmp.dropna(subset=['period']).groupby('period',sort=True)
    if buckets.ngroups>1000:
        raise AnalysisError('More than 1,000 time buckets; choose a coarser frequency.')
    rows=[]
    for period,part in buckets:
        value=len(part) if operation=='count_rows' else _safe_aggregate(part['metric'],operation)
        row={'period_start':period.strftime('%Y-%m-%d'),'value':value,'row_count':len(part)}
        if operation!='count_rows':
            row['non_missing_metric_count']=int(part['metric'].count())
        rows.append(row)
    out=pd.DataFrame(rows,dtype=object)
    return result('time_trend',out,date_column=date_column,metric=metric,operation=operation,
                  excluded_missing_dates=int(dates.isna().sum()),frequency=frequency,
                  date_format=date_format,
                  policy='Weeks start Monday; unobserved periods omitted, not assumed zero.')


def correlation(df,x,y):
    if x==y:
        raise AnalysisError('Choose two different numeric columns.')
    pair=pd.DataFrame({'x':numeric(df,x),'y':numeric(df,y)}).dropna()
    for label in ('x','y'):
        if is_integer_dtype(pair[label].dtype) and any(abs(int(v))>2**53 for v in pair[label]):
            raise AnalysisError('Correlation would lose integer precision beyond 2**53; rescale the columns.')
    if len(pair)<3:
        raise AnalysisError('At least three complete pairs are required.')
    if pair.x.nunique()<2 or pair.y.nunique()<2:
        raise AnalysisError('Correlation is undefined for a constant column.')
    r=float(pair.x.corr(pair.y))
    if not math.isfinite(r):
        raise AnalysisError('Correlation could not be calculated; check numeric scale.')
    return result('correlation',pd.DataFrame([{'x':x,'y':y,'pearson_r':r}]),
                  complete_pairs=len(pair),excluded_rows=len(df)-len(pair),
                  caveat='Association is not causation; small samples may be unstable.')

TOOLS={f.__name__:f for f in (inspect_dataset,filter_rows,grouped_summary,time_trend,correlation)}


def execute_spec(df,raw_spec):
    """Run validated filters on the FULL dataframe; only display is truncated."""
    try:
        spec=AnalysisSpec.parse(raw_spec)
    except SpecError as exc:
        raise AnalysisError(str(exc)) from None
    definition=spec.as_dict()
    selected=df
    applied=[]
    # Sequential exclusion numbers are DISJOINT by construction; repeated or
    # overlapping predicates never double-count the same removed row.
    for cond in definition['filters']:
        before=len(selected)
        mask,normalized=_condition(selected,cond['field'],cond['operator'],cond.get('value'))
        selected=selected.loc[mask]
        applied.append({'field':cond['field'],'operator':cond['operator'],
                        **({'value':normalized} if 'value' in cond else {}),
                        'eligible_before':before,'eligible_after':len(selected),
                        'newly_excluded':before-len(selected)})
    n=len(selected)
    if n==0:
        raise AnalysisError('No rows match the filters; no analytical result was produced.')
    tool=spec.tool
    arguments=definition['arguments']
    warnings=[]
    accounting={'input_rows':len(df),'selected_rows':n,
                'excluded_by_filters':len(df)-n,'filters_sequential':applied,
                'operation_exclusions':{}}
    if tool=='filter_rows':
        payload=result('filter_rows',selected.head(spec.display_limit),matched_rows=n,
                       returned_rows=min(n,spec.display_limit),truncated=n>spec.display_limit)
    else:
        payload=TOOLS[tool](selected,**arguments)
    if tool=='grouped_summary':
        group=arguments['group']
        missing_groups=int(selected[group].isna().sum())
        exclusions=accounting['operation_exclusions']
        exclusions['missing_group_labels_excluded']=0
        exclusions['missing_group_labels_included']=missing_groups
        if missing_groups:
            warnings.append(f'{missing_groups} row(s) have a missing group label; grouped under null.')
        if arguments['operation']!='count_rows':
            missing=int(selected[arguments['metric']].isna().sum())
            exclusions['missing_metric_excluded_from_values']=missing
            if missing:
                warnings.append(f'{missing} row(s) have missing metric values; excluded from numeric calculations, not from group row counts.')
        vals=[row['value'] for row in payload['rows'] if row.get('value') is not None]
        if vals and vals.count(max(vals))>1:
            warnings.append('Multiple groups tie for highest value; result order is not a unique rank.')
    elif tool=='time_trend':
        date=arguments['date_column']
        dates=pd.to_datetime(selected[date].astype('string'),format=arguments['date_format'],errors='coerce',exact=True)
        missing_date=dates.isna()
        exclusions=accounting['operation_exclusions']
        exclusions['missing_date_excluded']=int(missing_date.sum())
        if arguments['operation']!='count_rows':
            miss_metric=selected[arguments['metric']].isna()
            exclusions['missing_metric_and_date_overlap']=int((miss_metric & missing_date).sum())
            exclusions['missing_metric_with_valid_date_excluded_from_values']=int((miss_metric & ~missing_date).sum())
            exclusions['excluded_from_numeric_values_union']=int((miss_metric|missing_date).sum())
        if missing_date.any():
            warnings.append(f'{int(missing_date.sum())} missing date(s) excluded from period counts.')
    elif tool=='correlation':
        xmiss=selected[arguments['x']].isna()
        ymiss=selected[arguments['y']].isna()
        exclusions=accounting['operation_exclusions']
        exclusions.update({'missing_x_only':int((xmiss & ~ymiss).sum()),
                           'missing_y_only':int((ymiss & ~xmiss).sum()),
                           'missing_both':int((xmiss&ymiss).sum()),
                           'excluded_incomplete_pairs_union':int((xmiss|ymiss).sum()),
                           'complete_pairs':int((~xmiss&~ymiss).sum())})
        warnings.append('Pearson correlation is not evidence of causation.')
    elif tool=='inspect_dataset':
        warnings.append('Dataset profile reflects selected rows only; columns and types remain unchanged.') if definition['filters'] else None
    if tool in ('grouped_summary','time_trend') and any(
            isinstance(row.get('value'), int) and not isinstance(row.get('value'),bool)
            and abs(row['value']) > 2**53 for row in payload['rows']):
        warnings.append('Large integer results are exact in JSON; some browser and spreadsheet displays may round values beyond 2**53.')
    total_result_rows=n if tool=='filter_rows' else len(payload['rows'])
    if total_result_rows>spec.display_limit:
        payload['rows']=payload['rows'][:spec.display_limit]
    display={'limit':spec.display_limit,'total_result_rows':total_result_rows,
             'returned_rows':len(payload['rows']), 'truncated':total_result_rows>spec.display_limit}
    if display['truncated']:
        warnings.append('Output display truncated; calculations used all selected records.')
    fingerprint=dataset_fingerprint(df)
    payload.update({'dataset_id':fingerprint[:16],
                    'evidence':{'dataset_fingerprint_sha256':fingerprint,
                                'executed_spec':definition,'accounting':accounting,
                                'display':display,'warnings':warnings,
                                'results':payload['rows'],
                                'calculation_status':'completed'}})
    return payload


def run_tool(df,name,arguments):
    if not isinstance(name,str) or name not in TOOLS:
        raise AnalysisError('Unknown tool.')
    if not isinstance(arguments,dict):
        raise AnalysisError('Tool arguments must be an object.')
    args=dict(arguments)
    filters=args.pop('filters',[])
    display_limit=args.pop('display_limit',None)
    if name=='filter_rows':
        try:
            condition={k:args.pop(k) for k in ('field','operator')}
        except KeyError:
            raise AnalysisError('Filter requires field and operator.') from None
        if 'value' in args:
            condition['value']=args.pop('value')
        if 'limit' in args:
            display_limit=args.pop('limit')
        if not isinstance(filters,list):
            raise AnalysisError('Filters must be a list of at most eight conditions.')
        filters=[*filters,condition]
    spec={'spec_version':1,'tool':name,'arguments':args,'filters':filters}
    if display_limit is not None:
        spec['display_limit']=display_limit
    return execute_spec(df,spec)
