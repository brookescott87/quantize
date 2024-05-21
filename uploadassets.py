#!/usr/bin/env python

from pathlib import Path
import qlib

models = [mi.id for mi in qlib.hfapi.list_models(author='FaradayDotDev') if not mi.private]

upload_pattern = 'BackyardAI_*.png'

upload_folder = Path('assets')

for m in models:
    repo = qlib.Uploader(m, upload_folder)
    repo.upload('upload BackyardAI images', upload_pattern)
