"""M1: narrow, strictly validated, serialisable analysis contracts.

Specifications select only whitelisted read-only operations; no Python or SQL strings.
"""
from dataclasses import dataclass
from typing import Any, Mapping

ANALYTICAL_TOOLS = ('inspect_dataset', 'filter_rows', 'grouped_summary', 'time_trend', 'correlation')
OPERATORS = frozenset(('eq','ne','gt','ge','lt','le','contains','is_missing','not_missing'))
DATE_FORMATS = frozenset(('%Y-%m-%d','%d/%m/%Y','%m/%d/%Y'))
MAX_FILTERS = 8

class SpecError(ValueError):
    """Invalid analysis definition, safe to present to the user."""


def _string(value, label):
    if not isinstance(value, str) or not value or len(value) > 256:
        raise SpecError(f'{label} must be a non-empty string of at most 256 characters.')
    return value


def _mapping(value, label):
    if not isinstance(value, Mapping):
        raise SpecError(f'{label} must be an object.')
    return dict(value)


def _keys(obj, allowed, label):
    if any(not isinstance(key, str) for key in obj):
        raise SpecError(f'{label.capitalize()} field names must be strings.')
    unknown = sorted(obj.keys() - set(allowed))
    if unknown:
        raise SpecError(f'Unsupported {label} fields: {unknown}.')


@dataclass(frozen=True)
class AnalysisSpec:
    """Immutable normalized definition; source data and model prose are not part of the spec."""
    tool: str
    arguments: tuple[tuple[str, Any], ...]
    filters: tuple[tuple[tuple[str, Any], ...], ...]
    display_limit: int

    @classmethod
    def parse(cls, raw):
        obj = _mapping(raw, 'AnalysisSpec')
        _keys(obj, ('tool','arguments','filters','display_limit','spec_version'), 'specification')
        if obj.get('spec_version', 1) != 1 or type(obj.get('spec_version',1)) is not int:
            raise SpecError('Unsupported specification version. Only version 1 is supported.')
        tool = obj.get('tool')
        if tool not in ANALYTICAL_TOOLS:
            raise SpecError('Unsupported analysis tool.')
        arguments = _mapping(obj.get('arguments', {}), 'arguments')
        allowed = {
            'inspect_dataset': set(),
            'filter_rows': set(),
            'grouped_summary': {'group','metric','operation'},
            'time_trend': {'date_column','metric','operation','frequency','date_format'},
            'correlation': {'x','y'},
        }[tool]
        _keys(arguments, allowed, 'argument')
        defaults = {'grouped_summary':{'operation':'sum'},
                    'time_trend':{'operation':'sum','frequency':'month','date_format':'%Y-%m-%d'}}
        arguments = {**defaults.get(tool, {}), **arguments}
        required = {'grouped_summary': ('group',), 'time_trend': ('date_column',),
                    'correlation': ('x','y')}.get(tool, ())
        for key in required:
            _string(arguments.get(key), key)
        for key in ('metric','group','date_column','x','y'):
            if key in arguments and arguments[key] is not None:
                _string(arguments[key], key)
        if tool == 'grouped_summary':
            if arguments['operation'] not in ('sum','mean','min','max','count_rows'):
                raise SpecError('Unsupported grouped aggregation.')
        if tool == 'time_trend':
            if arguments['operation'] not in ('sum','mean','count_rows'):
                raise SpecError('Unsupported time aggregation.')
            if arguments['frequency'] not in ('day','week','month'):
                raise SpecError('Unsupported time frequency.')
            if not isinstance(arguments['date_format'], str) or arguments['date_format'] not in DATE_FORMATS:
                raise SpecError('Explicit date format is required.')
        if tool in ('grouped_summary','time_trend'):
            if arguments['operation'] != 'count_rows' and not arguments.get('metric'):
                raise SpecError('Numeric metric is required for this calculation.')
            if arguments['operation'] == 'count_rows' and arguments.get('metric') is not None:
                raise SpecError('Count of rows does not accept a metric.')
        raw_filters = obj.get('filters', [])
        if not isinstance(raw_filters,list) or len(raw_filters)>MAX_FILTERS:
            raise SpecError('Filters must be a list of at most eight conditions.')
        normalized=[]
        for f in raw_filters:
            f = _mapping(f, 'filter')
            _keys(f, ('field','operator','value'), 'filter')
            _string(f.get('field'), 'Filter field')
            if not isinstance(f.get('operator'), str) or f['operator'] not in OPERATORS:
                raise SpecError('Unsupported filter operator.')
            op=f['operator']
            if op in ('is_missing','not_missing'):
                if 'value' in f and f['value'] is not None:
                    raise SpecError('Missing-value filters take no value.')
                normalized.append((('field',f['field']),('operator',op)))
            else:
                if type(f.get('value')) not in (str,int,float,bool):
                    raise SpecError('Filter value must be text, number or boolean.')
                value=f['value']
                if isinstance(value,str) and len(value)>256:
                    raise SpecError('Filter text is too long.')
                import math
                if isinstance(value,float) and not math.isfinite(value):
                    raise SpecError('Filter value must be finite.')
                normalized.append((('field',f['field']),('operator',op),('value',value)))
        if tool=='filter_rows' and not normalized:
            raise SpecError('Row inspection requires at least one explicit filter.')
        default_limit=100
        limit=obj.get('display_limit', default_limit)
        if type(limit) is not int or not 1<=limit<=1000:
            raise SpecError('Display limit must be an integer from 1 to 1000.')
        return cls(tool,tuple(sorted(arguments.items())),tuple(normalized),limit)

    def as_dict(self):
        return {'spec_version':1,'tool':self.tool,'arguments':dict(self.arguments),
                'filters':[dict(f) for f in self.filters],'display_limit':self.display_limit}
