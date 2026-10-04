"""Serve the forecast review on localhost only: python serve_review.py."""
import argparse
import functools
import http.server
import pathlib

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);args=parser.parse_args()
    root=pathlib.Path(__file__).resolve().parent/'review'
    handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(root))
    server=http.server.ThreadingHTTPServer(('127.0.0.1',args.port),handler)
    print(f'Forecast review: http://127.0.0.1:{args.port}',flush=True)
    server.serve_forever()
