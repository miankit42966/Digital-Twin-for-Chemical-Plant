"""Local server entry point with a socket-friendly event loop on Windows."""
import argparse
import asyncio
import sys
from pathlib import Path

import uvicorn


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    config = uvicorn.Config('app.main:app', host=args.host, port=args.port, loop='none')
    # No subprocess transports are used by this app. SelectorEventLoop avoids
    # Windows Proactor's shutdown callback exception on an abruptly reset peer.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(uvicorn.Server(config).serve())


if __name__ == '__main__':
    main()
