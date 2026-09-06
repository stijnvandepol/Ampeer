"""The passwords every account fixture in this suite creates a user with.

Deliberately visible and deliberately Dutch prose: these are not secrets, they
are strings that exist only to satisfy `MinimumLengthValidator`'s twelve
character floor. Before this module, the same two strings were retyped at
twenty-two call sites across eight test files, which is the smell
`backend/ampeer/settings/base.py` already names about `SUPPLY_PRICE.mid`: two
literals that must agree are one literal that will eventually differ.

A secret scanner matching on `password=` will flag the line below. That is by
design and not a false negative to chase: the flag is the point, one line the
project owner marks once, instead of the twenty-two GitGuardian raised across
the files that only ever imported this module.
"""

from __future__ import annotations

#: Twenty-four characters, clear of every twelve character minimum this suite
#: exercises. The one password most fixtures create a user with.
TEST_PASSWORD = "een-heel-lang-wachtwoord"

#: A second password, distinct from TEST_PASSWORD, for the tests that need two
#: different accounts to have two different passwords.
OTHER_PASSWORD = "een-ander-wachtwoord"
