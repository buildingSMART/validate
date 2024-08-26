#!/bin/sh

echo ''
echo "*** Validate repository"
echo "Remote URL :" $(git remote get-url origin)
echo "Branch     :" $(git rev-parse --abbrev-ref HEAD)
echo "HEAD       :" $(git rev-parse --short HEAD)

echo ''
echo "*** Submodules"
git submodule foreach --recursive 'echo "Remote URL : $(git remote get-url origin)" && echo "Branch     : $(git rev-parse --abbrev-ref HEAD)" && echo "HEAD       : $(git rev-parse --short HEAD)" && echo ""'
