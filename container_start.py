"""Initialize a persistent volume once from preserved actual seed data."""
import os
import shutil
from pathlib import Path
from app import ROOT,serve

db=Path(os.environ.get('DB_PATH','/data/fx.sqlite3'))
db.parent.mkdir(parents=True,exist_ok=True)
if not db.exists():
    shutil.copy2(ROOT/'fx.sqlite3',db)
serve(port=int(os.environ.get('PORT','8000')),db_path=db,
      host=os.environ.get('BIND_HOST','0.0.0.0'),runtime=db.parent/'replay',
      public_origin=os.environ.get('PUBLIC_ORIGIN'))
