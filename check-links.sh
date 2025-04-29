#!/bin/bash

set -x

# if 223standard directory does not exist, clone the repo
if [ ! -d "223standard" ]; then
  git clone https://bas-im.emcs.cornell.edu/223/223standard.git
fi
cp stable_ids.json 223standard/publication
# otherwise, update the repo
pushd 223standard
git pull

pushd publication
uv venv --seed
uv pip install -r requirements.txt
. .venv/bin/activate && uv run bash build-documentation.sh

# generates 223p_publication.md
popd # publication
popd # 223standard
. .venv/bin/activate && python check-links.py 223standard/publication/223p_publication.md index.html
deactivate
