#!/usr/bin/env python3

"""LawDe.

Usage:
  lawde.py load [--path=<path>] <law>...
  lawde.py loadall [--path=<path>]
  lawde.py updatelist
  lawde.py -h | --help
  lawde.py --version

Examples:
  lawde.py load kaeaano

Options:
  --path=<path>  Path to laws dir [default: laws].
  -h --help     Show this screen.
  --version     Show version.

Duration Estimates:
  2-4 hours for total download

"""
import datetime
from pathlib import Path
import re
from io import BytesIO
import json
import shutil
import time
import zipfile
from xml.dom.minidom import parseString
from concurrent.futures import ThreadPoolExecutor, as_completed
import concurrent
from tqdm import tqdm

from docopt import docopt
import requests


class Lawde:
    BASE_URL = 'http://www.gesetze-im-internet.de'
    BASE_PATH = 'laws/'
    INDENT_CHAR = ' '
    INDENT = 2

    def __init__(self, path=BASE_PATH, lawlist='data/laws.json',
                 **kwargs):
        self.indent = self.INDENT_CHAR * self.INDENT
        self.path = Path(path)
        self.lawlist = lawlist

    def download_law(self, law):
        tries = 0
        while True:
            try:
                res = requests.get(f'{self.BASE_URL}/{law}/xml.zip')
            except Exception as e:
                tries += 1
                print(e)
                if tries > 3:
                    raise e
                else:
                    print(f"Sleeping {tries}" * 3)
                    time.sleep(tries * 3)
            else:
                break
        try:
            zipf = zipfile.ZipFile(BytesIO(res.content))
        except zipfile.BadZipfile:
            self.remove_law(law)
            return None
        return zipf

    def download_and_store(self, law):
        zipfile = self.download_law(law)
        if zipfile is not None:
            self.store(law, zipfile)
        return law, zipfile

    def load(self, laws):
        total = len(laws)
        print(f"Total laws to download: {total}")
        with ThreadPoolExecutor(max_workers=50) as executor:
            law_futures = {executor.submit(self.download_and_store, law): law for law in laws}
            for future in tqdm(as_completed(law_futures), total=total, desc="Downloading laws"):
                law = law_futures[future]
                try:
                    law, zipfile = future.result()
                except Exception as exc:
                    print(f'{law} generated an exception: {exc}')
                else:
                    if zipfile is not None:
                        pass

    def build_law_path(self, law):
        prefix = law[0]
        return self.path / prefix / law

    def remove_law(self, law):
        print(f"Removing {law}")
        law_path = self.build_law_path(law)
        shutil.rmtree(law_path, ignore_errors=True)

    def store(self, law, zipf):
        self.remove_law(law)
        law_path = self.build_law_path(law)
        # norm_date_re = re.compile('<norm builddate="\d+"')
        law_path.mkdir(parents=True)
        for name in zipf.namelist():
            if name.endswith('.xml'):
                xml = zipf.open(name).read()
                # xml = norm_date_re.sub('<norm', xml.decode('utf-8'))
                dom = parseString(xml.decode('utf-8'))
                xml = dom.toprettyxml(
                    encoding='utf-8',
                    indent=self.indent
                )
                if not name.startswith('_'):
                    law_filename = law_path / f'{law}.xml'
                else:
                    law_filename = name
                with open(law_filename, 'w', encoding='utf-8') as f:
                    f.write(xml.decode('utf-8'))
            else:
                zipf.extract(name, law_path)

    def get_all_laws(self):
        with open(self.lawlist) as f:
            return [law['slug'] for law in json.load(f)]

    def loadall(self):
        self.load(self.get_all_laws())

    def update_list(self):
        REGEX = re.compile(
            r'href="\./([^\/]+)/index.html"><abbr title="([^"]*)">([^<]+)</abbr>')

        laws = []
        for char in 'abcdefghijklmnopqrstuvwxyz0123456789':
            print(f"Loading part list {char}")
            try:
                response = requests.get(f'{self.BASE_URL}/Teilliste_{char.upper()}.html')
                html = response.content
            except Exception:
                continue
            html = html.decode('iso-8859-1')
            matches = REGEX.findall(html)
            for match in matches:
                laws.append({
                    'abbreviation': match[2].strip(),
                    'slug': match[0],
                    'name': match[1].replace('&quot;', '"')
                })
        with open(self.lawlist, 'w') as f:
            json.dump(laws, f, indent=4)


def main(arguments):
    nice_arguments = {}
    for k in arguments:
        if k.startswith('--'):
            nice_arguments[k[2:]] = arguments[k]
        else:
            nice_arguments[k] = arguments[k]
    lawde = Lawde(**nice_arguments)
    if arguments['load']:
        lawde.load(arguments['<law>'])
    elif arguments['loadall']:
        lawde.loadall()
    elif arguments['updatelist']:
        lawde.update_list()


if __name__ == '__main__':
    try:
        arguments = docopt(__doc__, version='LawDe 0.0.1')
        main(arguments)
    except KeyboardInterrupt:
        print('\nAborted')
