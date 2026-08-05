#!/bin/sh
exec python3 -c 'import pty,sys; raise SystemExit(pty.spawn(sys.argv[1:]))' \
  claude mcp login plugin:adant:adant
