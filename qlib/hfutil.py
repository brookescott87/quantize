import sys
from pathlib import Path
import datetime
import clear_screen
import huggingface_hub
from typing import List

hfapi = huggingface_hub.HfApi()

class Uploader(object):
    def __init__(self, repo_id: str, folder_path: Path, max_retries:int = 0):
        self.repo_id = repo_id
        self.folder_path = folder_path
        self.max_retries = max_retries
        self.total_retries = 0
        self.repo_exists = hfapi.repo_exists(repo_id)
        self.start_time = None

    @property
    def elapsed(self):
        return datetime.datetime.now() - self.start_time if self.start_time else datetime.timedelta(0)
        
    def upload(self, message: str, allow_patterns:List[str], ignore_patterns:List[str]=None, *, skip=False):
        if skip:
            return True
        retries = 0
        finished = False

        if not self.repo_exists:
            hfapi.create_repo(self.repo_id, private = True, repo_type = 'model')
            self.repo_exists = True
        self.start_time = datetime.datetime.now()

        while not (finished or (self.max_retries and retries > self.max_retries)):
            clear_screen.clear()
            sys.stdout.write(f'{self.repo_id}: {message}')

            if retries:
                sys.stdout.write(f' (retry {retries}')
                if self.max_retries:
                    sys.stdout.write(f' of {self.max_retries}')
                sys.stdout.write(')')
            sys.stdout.write('\n')
            try:
                hfapi.upload_folder(repo_id=self.repo_id, folder_path=self.folder_path, commit_message=message,
                                    repo_type='model', allow_patterns=allow_patterns, ignore_patterns=ignore_patterns)
                finished = True
            except KeyboardInterrupt:
                print('\n*** Keyboard interrupt ***')
                break
            except RuntimeError:
                retries += 1
                print('Upload failed')

        self.total_retries += retries
        return finished
