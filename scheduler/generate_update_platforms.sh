wget -q -O platforms.py http://hg.mozilla.org/build/tools/raw-file/default/lib/python/release/platforms.py
python generate_update_platforms.py
rm platforms.py
