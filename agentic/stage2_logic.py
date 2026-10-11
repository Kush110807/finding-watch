"""Pure Stage 2 view/state helpers. No inference, model routing, or calculation."""
import hashlib
import json
from stage1_logic import primary_candidates
from presentation import metric_definition, filter_description


def calculated_choices(trace):
    """Occurrence-identified choices from completed non-inspection operations.

    Inspection is retained as supporting detail when a substantive calculation
    exists. Identical calculations are separate trace occurrences.
    """
    choices=[]
    for position,event in primary_candidates(trace):
        output=event['result']
        spec=output.get('evidence',{}).get('executed_spec',{})
        args=spec.get('arguments',{})
        tool=output.get('tool')
        if tool=='grouped_summary':
            text=f'{metric_definition(spec)} by {args.get("group")}'
        elif tool=='time_trend':
            text=(f'{metric_definition(spec)} by {args.get("frequency")} · '
                  f'{args.get("date_column")} ({args.get("date_format")})')
        elif tool=='correlation':
            text=f'Pearson correlation · {args.get("x")} and {args.get("y")}'
        elif tool=='filter_rows':
            text='Matching records'
        else:
            text='Dataset profile'
        if spec.get('filters'):
            text+=' · '+ '; '.join(filter_description(c) for c in spec['filters'])
        else:
            text+=' · no filters'
        choices.append({'position':position,'label':f'Calculation {position}: {text}',
                        'event':event})
    return choices


# Keep the unselected option in the actual Streamlit widget choices.
# Streamlit 1.64.0 AppTest serializes displayed strings and can otherwise
# confuse a formatted integer option with the unselected placeholder.
RESULT_CHOICE_PROMPT = 'Choose a calculation'


def result_option_map(choices):
    """Unique, human-readable options bound to original 1-based trace positions.

    No result is picked by default.  Repeated identical calculations remain
    distinct because the trace occurrence is part of every label.
    """
    options={RESULT_CHOICE_PROMPT: None}
    for choice in choices:
        if not isinstance(choice.get('position'),int) or choice['position'] < 1:
            raise ValueError('Calculation trace positions must be positive integers.')
        label=choice['label']
        if not isinstance(label,str) or not label.strip() or label in options:
            raise ValueError('Calculation choices require distinct readable labels.')
        options[label]=choice
    return options


def bind_selected_challenge_occurrence(state, selection_scope, trace_position):
    """Invalidate selected-Gemini Challenge when its selected occurrence changes.

    A non-grouped selection must revoke an earlier grouped comparison too:
    the Challenge editor is not rendered for a non-grouped result and cannot
    perform its own context invalidation. A rerender with the same response
    scope and occurrence must leave a completed confirmation untouched.
    """
    if not isinstance(selection_scope,str) or not selection_scope:
        raise ValueError('The response selection scope must be nonempty.')
    if trace_position is not None and (type(trace_position) is not int or trace_position < 1):
        raise ValueError('The chosen trace position must be a positive integer or None.')
    binding=(selection_scope,trace_position)
    if state.get('stage2_challenge_selection_binding')==binding:
        return False
    for name in ('last_ai_selected_comparison', 's3_ai_selected_review',
                 's3_ai_selected_context', 's3_ai_selected_editor'):
        state.pop(name,None)
    state['stage2_challenge_selection_binding']=binding
    return True

def result_selection_key(dataset,question,response,serial=0):
    """Scope a selection to one dataset, original question and exact response.

    Serial distinguishes subsequent submits returning identical payloads; it
    is a UI state generation, never a measure of evidence correctness.
    """
    document=json.dumps([dataset,question,response,serial],sort_keys=True,
                        ensure_ascii=False,default=str,allow_nan=False)
    return 'stage2_result_choice_v2_'+hashlib.sha256(document.encode()).hexdigest()[:20]


def append_clarification_context(existing, new, max_chars=2000):
    """Keep explicit context through bounded follow-ups without parsing it."""
    if not isinstance(new,str) or not new.strip():
        raise ValueError('Enter clarification details before continuing.')
    if not isinstance(existing,str) and existing is not None:
        raise ValueError('Previous context is invalid.')
    combined=(existing.strip()+'\nAdditional clarification: '+new.strip()) if existing else new.strip()
    if len(combined)>max_chars:
        raise ValueError('The combined clarification exceeds 2,000 characters. Shorten it before continuing.')
    return combined


def response_failure_kind(response):
    """Classify UI recovery based on agent status and executed tool evidence."""
    trace=response.get('trace',[])
    if any(isinstance(event,dict) and isinstance(event.get('result'),dict)
           and event['result'].get('error') for event in trace):
        return 'calculation'
    if response.get('status')=='error':
        return 'provider'
    return 'needs_detail'
