"""M2 synthetic live-provider smoke; NO secrets printed or stored.

A model proposal is NOT a successful comparison until the user inspects and
explicitly confirms definitions locally. This script runs no user datasets.
"""
import argparse
import json
from pathlib import Path
from agent import ask, configuration, AgentError, safe_error
from comparisons import execute_comparison
from engine import load_csv

SYNTHETIC=(b'category,status,revenue\nCoffee,completed,120\nCoffee,completed,90\n'
           b'Coffee,cancelled,300\nSnacks,completed,180\nSnacks,completed,100\n')
QUESTION=('Propose a grouped revenue sum comparison by category on this same dataset: '
          'baseline ALL records versus changed assumption status equals completed. '
          'You must only propose the two definitions using propose_grouped_comparison '
          'and wait for user confirmation. Do not run either calculation yet.')

def main():
    parser=argparse.ArgumentParser(description='Synthetic real Gemini proposal and opt-in confirmed deterministic comparison.')
    parser.add_argument('--output',default='live_comparison_local.json')
    parser.add_argument('--confirm',action='store_true',help='Offer an interactive confirmation prompt after showing definitions.')
    opts=parser.parse_args()
    _,model=configuration()
    df=load_csv(SYNTHETIC)
    report={'model':model,'status':'not_started','live_proposal_verified':False,
            'confirmed_calculation_verified':False,'synthetic_only':True}
    try:
        response=ask(df,QUESTION)
        report['status']=response['status']
        report['model']=response.get('model',model)
        report['tool_calls']=[{'tool':event['tool'],'arguments':event['arguments'],
                               'result':event['result']} for event in response['trace']]
        proposal=response.get('pending_comparison')
        if response['status']=='comparison_pending' and proposal:
            report['live_proposal_verified']=True
            report['proposal']=proposal
            print('Model proposed the following definitions; NO calculation approved yet:')
            print(json.dumps({'baseline_spec':proposal['baseline_spec'],
                              'challenged_spec':proposal['challenged_spec'],
                              'changed_condition':proposal['changed_condition']},indent=2))
            if opts.confirm:
                typed=input('Review both definitions. Type CONFIRM to run the synthetic comparison: ').strip()
                if typed=='CONFIRM':
                    result=execute_comparison(df,proposal['baseline_spec'],proposal['challenged_spec'],
                        expected_fingerprint=proposal['dataset_fingerprint_sha256'])
                    expected={'Coffee':(510,210,-300),'Snacks':(280,280,0)}
                    actual={r['group_value']:(r['baseline_value'],r['challenged_value'],
                            r['difference_challenged_minus_baseline'])
                            for r in result['comparison']['all_results']}
                    counts=(result['accounting']['baseline']['selected_rows'],
                            result['accounting']['challenged']['selected_rows'])
                    passed=(actual==expected and counts==(5,4)
                        and result['comparison']['baseline_leaders']==['Coffee']
                        and result['comparison']['challenged_leaders']==['Snacks'])
                    report['confirmed_calculation_verified']=passed
                    report['confirmed_calculation']=result
                    print('Golden comparison after confirmation:', 'PASS' if passed else 'FAILED')
                else:
                    print('No confirmation; no comparison calculation performed.')
        else:
            report['response_notice']=response.get('answer','No matching proposal. Do not count as live M2 success.')
            print('No valid M2 proposal. Status:',response['status'])
    except AgentError as exc:
        report['status']='error'
        report['redacted_error']=str(exc)
    except Exception as exc:
        report['status']='error'
        report['redacted_error']=safe_error(exc)
    Path(opts.output).write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print('Saved synthetic-only log:',opts.output)
    print('Inspect locally before sharing. Never share .env, API keys or raw provider errors.')

if __name__=='__main__':
    main()
