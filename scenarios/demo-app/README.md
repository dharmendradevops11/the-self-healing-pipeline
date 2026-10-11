# demo-app

A tiny Python app with one deliberate bug (`src/auth.py`): `get_display_name` crashes for first-time users who
have no profile. One test fails on purpose. The pipeline's job is to find the cause, propose the fix and open a
pull request. Use it to see every stage work before you point the pipeline at a real repository.
