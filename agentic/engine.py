"""Deterministic, read-only analysis tools. No model or code execution."""
import csv
import io
import math
import json
import hashlib
import pandas as pd
from pandas.api.types import is_numeric_dtype, is_bool_dtype

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 100_000
MAX_COLUMNS = 100

class AnalysisError(ValueError):
    """An input problem safe to show to the user."""

def load_csv(raw: bytes) -> pd.DataFrame:
    if not raw or len(raw) > MAX_BYTES:
        raise AnalysisError('Upload a non-empty CSV no larger than 10 MiB.')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise AnalysisError('Save the CSV with UTF-8 encoding.') from None
    if '\x00' in text:
        raise AnalysisError('The file contains null bytes; upload a text CSV.')
    try:
        reader = csv.reader(io.StringIO(text, newline=''), strict=True)
        header = next(reader, [])
        if not header or len(header) > MAX_COLUMNS:
            raise AnalysisError('CSV must have a header with 1–100 columns.')
        if any(not h.strip() for h in header) or len(set(h.strip() for h in header)) != len(header):
            raise AnalysisError('Column names must be non-empty and unique after trimming spaces.')
        count = 0
        for row in reader:
            if not row:  # Match pandas blank-line handling.
                continue
            if len(row) != len(header):
                raise AnalysisError(f'Record {count + 2} has {len(row)} fields; expected {len(header)}.')
            count += 1
            if count > MAX_ROWS:
                raise AnalysisError('CSV exceeds 100,000 data rows.')
        if count == 0:
            raise AnalysisError('CSV has a header but no data rows.')
        # Only empty fields are missing. Preserve labels such as NA and NULL.
        df = pd.read_csv(io.StringIO(text), keep_default_na=False, na_values=[''])
        df.columns = [h.strip() for h in header]
        return df
    except (csv.Error, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise AnalysisError('Malformed CSV. Check delimiters and quotation marks.') from exc

def numeric_columns(df):
    return [c for c in df if is_numeric_dtype(df[c]) and not is_bool_dtype(df[c])]

def column(df, name):
    if name not in df.columns:
        raise AnalysisError(f'Unknown column: {name}')
    return df[name]

def numeric(df, name):
    s = column(df, name)
    if name not in numeric_columns(df):
        raise AnalysisError(f'{name} must be numeric; clean mixed text or currency symbols first.')
    if any(not math.isfinite(float(v)) for v in s.dropna()):
        raise AnalysisError(f'{name} contains infinite values; clean these before analysis.')
    return s

def result(tool, frame, **metadata):
    # JSON-safe boundary for future model integration; reject non-finite output.
    for c in frame.select_dtypes(include='number'):
        if any(not math.isfinite(float(v)) for v in frame[c].dropna()):
            raise AnalysisError('Calculation overflowed. Rescale the numeric values.')
    return {'tool': tool, 'metadata': metadata,
            'rows': json.loads(frame.to_json(orient='records', date_format='iso', double_precision=15))}

def inspect_dataset(df):
    table = pd.DataFrame([{'column': c, 'dtype': str(df[c].dtype),
        'missing': int(df[c].isna().sum()), 'unique_non_missing': int(df[c].nunique())} for c in df])
    return result('inspect_dataset', table, total_rows=len(df), total_columns=len(df.columns),
                  duplicate_rows=int(df.duplicated().sum()), missing_policy='Only empty CSV fields are missing.')

def filter_rows(df, field, operator, value=None, limit=100):
    s = column(df, field)
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise AnalysisError('Display limit must be an integer between 1 and 1000.')
    if operator == 'is_missing':
        mask = s.isna()
    elif operator == 'not_missing':
        mask = s.notna()
    elif operator == 'contains':
        mask = s.astype('string').str.contains(str(value), regex=False, na=False)
    elif operator in {'eq','ne','gt','ge','lt','le'}:
        if field in numeric_columns(df):
            numeric(df, field)
            try:
                value = float(value)
                if not math.isfinite(value):
                    raise ValueError()
            except (ValueError, TypeError):
                raise AnalysisError('Enter a finite numeric filter value.') from None
        elif is_bool_dtype(s):
            if str(value).lower() not in {'true','false'}:
                raise AnalysisError('Boolean filter value must be true or false.')
            value = str(value).lower() == 'true'
        elif operator not in {'eq','ne'}:
            raise AnalysisError('Ordered comparisons require a numeric column.')
        else:
            value = str(value)
        mask = getattr(s, operator)(value) & s.notna()
    else:
        raise AnalysisError('Unknown filter operator.')
    selected = df.loc[mask]
    return result('filter_rows', selected.head(limit), matched_rows=len(selected),
                  returned_rows=min(limit,len(selected)), truncated=len(selected)>limit,
                  field=field, operator=operator, value=value)

def grouped_summary(df, group, metric=None, operation='sum'):
    column(df, group)
    if operation not in {'sum','mean','min','max','count_rows'}:
        raise AnalysisError('Unsupported aggregation.')
    if df[group].nunique(dropna=False) > 1000:
        raise AnalysisError('Choose a grouping column with at most 1,000 distinct values.')
    gb = df.groupby(group, dropna=False, sort=False)
    if operation == 'count_rows':
        values = gb.size()
    else:
        numeric(df, metric)
        values = gb[metric].sum(min_count=1) if operation=='sum' else getattr(gb[metric],operation)()
    out = pd.DataFrame({'group_value':values.index, 'value':values.values})
    out['row_count'] = gb.size().values
    if operation != 'count_rows':
        out['non_missing_metric_count'] = gb[metric].count().values
    out = out.sort_values('value',ascending=False,na_position='last',kind='stable')
    return result('grouped_summary',out,group_column=group,metric=metric,operation=operation,
                  policy='Missing groups included; missing metric values excluded; all-missing sums remain null.')

def time_trend(df, date_column, metric, frequency='month', date_format='%Y-%m-%d', operation='sum'):
    formats={'%Y-%m-%d','%d/%m/%Y','%m/%d/%Y'}
    if date_format not in formats or frequency not in {'day','week','month'}:
        raise AnalysisError('Select a supported date format and frequency.')
    if operation not in {'sum','mean','count_rows'}:
        raise AnalysisError('Unsupported time aggregation.')
    s = column(df,date_column)
    dates = pd.to_datetime(s.astype('string'),format=date_format,errors='coerce',exact=True)
    invalid = int((s.notna() & dates.isna()).sum())
    if invalid:
        raise AnalysisError(f'{invalid} non-empty dates do not match {date_format}. Correct the format or data.')
    if not dates.notna().any():
        raise AnalysisError('No valid dates to analyse.')
    tmp = pd.DataFrame({'period':dates.dt.to_period({'day':'D','week':'W-SUN','month':'M'}[frequency]).dt.start_time})
    if operation!='count_rows':
        tmp['metric'] = numeric(df,metric)
    gb = tmp.dropna(subset=['period']).groupby('period',sort=True)
    vals = gb.size() if operation=='count_rows' else (gb.metric.sum(min_count=1) if operation=='sum' else gb.metric.mean())
    if len(vals)>1000:
        raise AnalysisError('More than 1,000 time buckets; choose a coarser frequency.')
    out = pd.DataFrame({'period_start':vals.index.strftime('%Y-%m-%d'),'value':vals.values,'row_count':gb.size().values})
    if operation!='count_rows':
        out['non_missing_metric_count'] = gb.metric.count().values
    return result('time_trend',out,date_column=date_column,metric=metric,operation=operation,
                  excluded_missing_dates=int(dates.isna().sum()),frequency=frequency,
                  policy='Weeks start Monday. Unobserved periods omitted, not assumed zero.')

def correlation(df, x, y):
    if x==y:
        raise AnalysisError('Choose two different numeric columns.')
    pair = pd.DataFrame({'x':numeric(df,x),'y':numeric(df,y)}).dropna()
    if len(pair)<3:
        raise AnalysisError('At least three complete pairs are required.')
    if pair.x.nunique()<2 or pair.y.nunique()<2:
        raise AnalysisError('Correlation is undefined for a constant column.')
    r=float(pair.x.corr(pair.y))
    if not math.isfinite(r):
        raise AnalysisError('Correlation could not be calculated; check numeric scale.')
    return result('correlation',pd.DataFrame([{'x':x,'y':y,'pearson_r':r}]),
                  complete_pairs=len(pair),excluded_rows=len(df)-len(pair),
                  caveat='Association is not causation. Small samples may be unstable.')

TOOLS = {f.__name__:f for f in [inspect_dataset,filter_rows,grouped_summary,time_trend,correlation]}
def run_tool(df, name, arguments):
    if name not in TOOLS:
        raise AnalysisError('Unknown tool.')
    try:
        payload=TOOLS[name](df,**arguments)
    except TypeError as exc:
        raise AnalysisError('Invalid tool arguments.') from exc
    payload['dataset_id']=hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()[:16]
    return payload
