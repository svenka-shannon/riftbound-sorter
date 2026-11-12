"""Third-party code vendored verbatim (see each file's licence).

hx711.py — gandalf15/HX711, HX711_Python3/hx711.py at commit
a2b72a0b44fc200112ecb25e11b60a5ee4ba7d56 (2023-02-07), BSD 3-Clause,
Copyright (c) 2017 Marcel Zak; licence text in LICENSE.hx711.
Vendored because the PyPI package named "hx711" is a different library
(Marco Roose) with an incompatible API. Do not edit hx711.py; adapt
hardware/loadcell.py instead. ONE local edit, marked "RIFTBOUND LOCAL EDIT"
in _read(): the not-ready timeout check (`== 50` could never trigger, so a
dead HX711 returned raw -1 instead of False). loadcell.py also rejects raw -1
on its own, so the guard holds even if this file is re-vendored.
"""
