#!/usr/bin/env python3

import qlib
import argparse

prompt_formats = {s.lower():s for s in ('general','ChatML','Llama3')}

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--submit', '-w', action='store_true',
                       help='Submit the manifest')
    group.add_argument('--summarize', '-s', action='store_true',
                       help='Summarize the manifest')
    group.add_argument('--view', '-v', action='store_true',
                       help='View the manifest')
    group.add_argument('--list', '-L', action='store_true',
                       help='List registered models' )
    group.add_argument('--get-head', '-H', action='store_true',
                       help='Return the head commit id of the main branch of the repository.')

    parser.add_argument('--request-token', '-t', type=str, default=None,
                        help='Request token required to submit')
    parser.add_argument('--recommended', '-r', action='store_true',
                        help='Marks the model as recommended')
    parser.add_argument('--description', '-d', type=str,
                        help='Sets the model description')
    parser.add_argument('--prompt-format', '-p', default=None,
                        choices=tuple(prompt_formats.values()),
                        type=lambda s: prompt_formats.get(str(s).lower(),str(s)),
                        help='Sets the model prompt format string')
    parser.add_argument('--catalog-name', '-c', type=str, default=None,
                        help='Sets the catalog name for the model')
    parser.add_argument('--formal-name', '-n', type=str, default=None,
                        help='Sets the formal name for the model')
    parser.add_argument('repo_id', type=str, nargs='?',
                        help='Repository to generate manifest for')
    args = parser.parse_args()

    r = qlib.backyard.Requestor(args.request_token)

    if not args.repo_id:
        if args.list:
            print(r.get_models())
        else:
            for name in qlib.list_models():
                print(name)
        return

    if args.get_head:
        print(r.get_last_commit(args.repo_id))
        return

    m = qlib.QuantModel(args.repo_id)
    man = qlib.backyard.Manifest(m,
                                 args.recommended,
                                 args.description,
                                 args.prompt_format,
                                 args.catalog_name,
                                 args.formal_name)
    if args.submit:
        print(r.submit(man))
    elif args.summarize:
        man.summary()
    elif args.view:
        man.show()
    else:
        raise ValueError('invalid arguments')

if __name__ == '__main__':
    main()
