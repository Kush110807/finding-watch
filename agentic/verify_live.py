"""M0: run three real local-provider requests on SYNTHETIC data only.

Uses the local .env implicitly through agent.configuration; never prints credentials,
raw provider exceptions, or private datasets. No automated 'model list = pass'.
"""
import argparse
import json
from pathlib import Path
from agent import ask, configuration, AgentError, safe_error
from engine import load_csv

SYNTHETIC = b'date,category,revenue\n2026-01-01,Coffee,10\n2026-01-02,Coffee,20\n2026-02-01,Snacks,5\n'
CASES = [
    ('group', 'Which category has the highest total revenue? Use sum of revenue grouped by category.',
     'grouped_summary', {'Coffee':30,'Snacks':5}),
    ('time', 'Show total revenue by month. Dates are in YYYY-MM-DD format.',
     'time_trend', {'2026-01-01':30,'2026-02-01':5}),
    ('clarification', 'Which column is best?', 'request_clarification', None),
]

def main():
    p=argparse.ArgumentParser(description='Actual (not mocked) Gemini M0 checks using synthetic data.')
    p.add_argument('--output',default='live_verification_local.json',help='Local synthetic-only log path. Inspect before sharing.')
    opts=p.parse_args()
    _,model=configuration()
    df=load_csv(SYNTHETIC)
    report={'model':model,'environment':'user local Windows, actual Gemini calls',
            'live_verified':False,'cases':[]}
    for label,question,expected_tool,expected_values in CASES:
        try:
            r=ask(df,question)
        except AgentError as exc:
            r={'status':'error','answer':str(exc),'trace':[]}
        except Exception as exc:
            r={'status':'error','answer':safe_error(exc),'trace':[]}
        calls=[{'tool':t['tool'],'arguments':t['arguments'],
                'result':t['result']} for t in r.get('trace',[])]
        tool_results=[x['result'] for x in calls if x['tool']==expected_tool and 'rows' in x['result']]
        observed=None
        if tool_results and expected_values is not None:
            rows=tool_results[-1]['rows']
            label_key='group_value' if label=='group' else 'period_start'
            observed={row[label_key]:row['value'] for row in rows}
        passed=(r.get('status')=='clarification' and label=='clarification' and
                any(c['tool']=='request_clarification' for c in calls)) if label=='clarification' else (
            r.get('status')=='evidence_available' and observed==expected_values)
        entry={'case':label,'question':question,'status':r.get('status'),
               'expected_tool':expected_tool,'observed':observed,'expected':expected_values,
               'passed':bool(passed),'tool_calls':calls,
               'model_explanation_unverified':r.get('answer','')}
        report['cases'].append(entry)
        print(f'{label}: {"PASS" if passed else "NOT VERIFIED"}; status={r.get("status")}; '
              f'tools={[t["tool"] for t in calls]}')
    report['live_verified']=all(c['passed'] for c in report['cases'])
    output=Path(opts.output)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print('All three provider checks passed:',report['live_verified'])
    print('Synthetic-only evidence saved to:',output)
    print('Inspect the saved JSON before sharing it. Never share .env or API keys.')

if __name__=='__main__':
    main()
