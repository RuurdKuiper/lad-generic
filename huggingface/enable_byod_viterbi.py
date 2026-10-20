#!/usr/bin/env python3
"""Update existing BYOD Spaces without uploading model weights."""
import argparse
import json
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

from publish_byod import MODELS, REPO_ROOT, make_space_bundle


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--namespace',choices=['Ruurd','Dovelove'],default='Ruurd')
    parser.add_argument('--include-gemma',action='store_true')
    parser.add_argument('--credential-name',help='Explicitly selected saved credential; verifies the account before writing')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT/'.env')
    if args.credential_name:
        from huggingface_hub.utils._auth import get_stored_tokens
        credential=get_stored_tokens().get(args.credential_name)
        if not credential:raise RuntimeError('The selected saved credential does not exist.')
        api=HfApi(token=credential)
    else:
        api=HfApi()
    if args.execute and api.whoami()['name'].casefold()!=args.namespace.casefold():
        raise RuntimeError(f'This rollout requires the {args.namespace} account.')
    if args.output is None:
        args.output=REPO_ROOT/'artifacts/bigram'/('dovelove_rollout' if args.namespace=='Dovelove' else 'byod_rollout')
    args.output.mkdir(parents=True,exist_ok=True)
    prepared=[]
    for spec in MODELS:
        if spec.space_name=='byod-gemma-2-9b' and args.namespace=='Ruurd' and not args.include_gemma:
            continue
        repo=f'{args.namespace}/{spec.space_name}'
        info=api.repo_info(repo,repo_type='space')
        config=json.loads(Path(hf_hub_download(repo,'space_model.json',repo_type='space',revision=info.sha,token=api.token)).read_text())
        if config['model_repo_id']!=f'{args.namespace}/{spec.model_name}':
            raise RuntimeError(f'Unexpected model configuration in {repo}.')
        destination=args.output/'bundles'/spec.space_name
        destination.mkdir(parents=True,exist_ok=True)
        make_space_bundle(spec,args.namespace,destination)
        # Retain each existing Space's links, visitor counter and model selection.
        config['bigram_enabled']=True
        (destination/'space_model.json').write_text(json.dumps(config,indent=2)+'\n')
        record=dict(space=repo,parent_revision=info.sha,private=info.private,
                    bundle=str(destination),model=spec.model_name)
        prepared.append(record)
    (args.output/'prepared.json').write_text(json.dumps(prepared,indent=2)+'\n')
    print(json.dumps(dict(prepared=prepared,execute=args.execute)),flush=True)
    if not args.execute:
        return
    deployed=[]
    for record in prepared:
        commit=api.upload_folder(repo_id=record['space'],repo_type='space',
            folder_path=record['bundle'],parent_commit=record['parent_revision'],
            commit_message='Enable PMI Viterbi with model-specific full-corpus scorer and shared BYOD interface')
        deployed.append(dict(**record,revision=commit.oid))
        (args.output/'deployment.json').write_text(json.dumps(deployed,indent=2)+'\n')
        print(json.dumps(deployed[-1]),flush=True)


if __name__=='__main__':
    main()
