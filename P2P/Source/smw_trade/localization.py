"""Bundled UI catalogs. Language selection never sends text to an external service."""
from pathlib import Path
import json, os, tempfile

class Localizer:
    def __init__(self,directory):
        self.folder=Path(__file__).with_name('locales')
        self.languages=json.loads((self.folder/'languages.json').read_text(encoding='utf8'))
        self.settings=Path(directory)/'ui-language.json';self.catalogs={}
        try:code=json.loads(self.settings.read_text(encoding='utf8')).get('language')
        except (OSError,ValueError):code='en'
        self.code=code if code in self.languages else 'en'

    def text(self,source):
        if self.code not in self.catalogs:
            self.catalogs[self.code]=json.loads((self.folder/(self.code+'.json')).read_text(encoding='utf8'))
        return self.catalogs[self.code].get(source,source)

    def set(self,code):
        if code not in self.languages:raise ValueError('Unsupported UI language')
        self.settings.parent.mkdir(parents=True,exist_ok=True)
        fd,temp=tempfile.mkstemp(prefix='ui-language-',suffix='.tmp',dir=self.settings.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf8') as stream:
                json.dump({'language':code},stream);stream.flush();os.fsync(stream.fileno())
            os.replace(temp,self.settings)
        finally:
            Path(temp).unlink(missing_ok=True)
        self.code=code
